"""Cliente de governança genérico.

Não é acoplado a nenhuma plataforma específica. Ele:

  1. Registra a identidade do agente (POST {GOVERNANCE_URL}/agents/register).
  2. Emite eventos de auditoria (tool calls, decisões, resultado) — cada evento
     vai para a plataforma (se configurada) e SEMPRE para uma trilha local
     em JSONL, de modo que a governança seja auditável mesmo offline.
  3. Avalia políticas antes de uma ação (POST {GOVERNANCE_URL}/policy/evaluate),
     com um fallback local via arquivo de políticas.

Se GOVERNANCE_URL estiver vazio, tudo funciona localmente — ideal para plugar
depois na SUA plataforma só trocando a env var.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

from .identity import AgentIdentity


@dataclass
class PolicyDecision:
    allow: bool
    reason: str = ""

    def __bool__(self) -> bool:  # permite `if decision:`
        return self.allow


class GovernanceError(RuntimeError):
    """Levantado em modo strict quando a plataforma recusa registro/policy."""


class GovernanceClient:
    def __init__(
        self,
        identity: AgentIdentity,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        audit_dir: Optional[str] = None,
        strict: Optional[bool] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self.identity = identity
        self.base_url = (base_url or os.getenv("GOVERNANCE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("AGENT_CREDENTIAL", "")
        self.strict = strict if strict is not None else _envbool("GOVERNANCE_STRICT")
        self.run_id = run_id or f"run-{identity.instance_id[:12]}"

        audit_dir = audit_dir or os.getenv("AUDIT_DIR", "./audit")
        self._audit_path = Path(audit_dir) / f"{identity.agent_id}.jsonl"
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

        self._seq = 0
        self.session_token: Optional[str] = None

    # ── ciclo de vida ────────────────────────────────────────────────
    def register(self) -> dict:
        """Apresenta a identidade do agente à plataforma."""
        manifest = {
            **self.identity.to_manifest(),
            "run_id": self.run_id,
            "sdk": "governed-langchain/0.1",
        }
        self.emit("agent.register", {"manifest": manifest}, level="info")
        resp = self._post("/agents/register", manifest)
        if resp is not None:
            self.session_token = resp.get("session_token") or resp.get("token")
        return resp or {"status": "local-only", "agent_id": self.identity.agent_id}

    def heartbeat(self, status: str = "healthy") -> None:
        self.emit("agent.heartbeat", {"status": status}, level="debug")
        self._post(f"/agents/{self.identity.agent_id}/heartbeat", {"status": status})

    def shutdown(self, status: str = "completed") -> None:
        self.emit("agent.shutdown", {"status": status}, level="info")
        self._post(f"/agents/{self.identity.agent_id}/shutdown", {"status": status})

    # ── política / guardrails ────────────────────────────────────────
    def check_policy(self, action: str, context: Optional[dict] = None) -> PolicyDecision:
        context = context or {}
        body = {
            "agent_id": self.identity.agent_id,
            "run_id": self.run_id,
            "action": action,
            "context": context,
            "risk_tier": self.identity.risk_tier,
        }
        resp = self._post("/policy/evaluate", body)
        if resp is not None and "allow" in resp:
            decision = PolicyDecision(bool(resp["allow"]), resp.get("reason", ""))
        else:
            decision = self._local_policy(action, context)
        self.emit(
            "policy.decision",
            {"action": action, "allow": decision.allow, "reason": decision.reason},
            level="info" if decision.allow else "warning",
        )
        if not decision.allow and self.strict:
            raise GovernanceError(f"Política negou '{action}': {decision.reason}")
        return decision

    def _local_policy(self, action: str, context: dict) -> PolicyDecision:
        """Fallback: lê governance/policies.yaml (opcional). Default = allow."""
        pol_path = Path(__file__).parent / "policies.yaml"
        if not pol_path.exists():
            return PolicyDecision(True, "default-allow (sem política local)")
        rules = yaml_safe_load(pol_path)
        # Bloqueia ferramenta fora do allowlist da própria identidade.
        tool = context.get("tool")
        if tool and self.identity.allowed_tools and tool not in self.identity.allowed_tools:
            return PolicyDecision(False, f"tool '{tool}' fora do allowlist da identidade")
        for rule in rules.get("deny", []):
            if rule.get("action") in (action, "*") and _matches(rule, context):
                return PolicyDecision(False, rule.get("reason", "negado por política local"))
        return PolicyDecision(True, "permitido por política local")

    # ── auditoria ────────────────────────────────────────────────────
    def emit(self, event_type: str, payload: dict, level: str = "info") -> None:
        self._seq += 1
        record = {
            "seq": self._seq,
            "ts": _now_iso(),
            "agent_id": self.identity.agent_id,
            "instance_id": self.identity.instance_id,
            "run_id": self.run_id,
            "role": self.identity.role,
            "event": event_type,
            "level": level,
            "payload": payload,
        }
        # Trilha local — sempre.
        with self._audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        # Plataforma — best-effort.
        self._post(f"/agents/{self.identity.agent_id}/events", record, audit=False)

    # ── transporte ───────────────────────────────────────────────────
    def _post(self, path: str, body: dict, audit: bool = True) -> Optional[dict]:
        if not self.base_url:
            return None
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}{path}"
        try:
            r = requests.post(url, json=body, headers=headers, timeout=8)
            r.raise_for_status()
            return r.json() if r.content else {}
        except Exception as exc:  # noqa: BLE001 — governança nunca deve derrubar o agente
            if audit:
                # Evita recursão: grava só na trilha local.
                self._seq += 1
                with self._audit_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({
                        "seq": self._seq, "ts": _now_iso(), "event": "governance.transport_error",
                        "level": "warning", "payload": {"url": url, "error": str(exc)},
                    }, ensure_ascii=False) + "\n")
            if self.strict:
                raise GovernanceError(f"Falha ao contatar governança em {url}: {exc}") from exc
            return None


# ── helpers ──────────────────────────────────────────────────────────
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _envbool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _matches(rule: dict, context: dict) -> bool:
    when = rule.get("when", {})
    return all(context.get(k) == v for k, v in when.items())


def yaml_safe_load(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
