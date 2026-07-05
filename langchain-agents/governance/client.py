"""Cliente de governança genérico e configurável.

Não é acoplado a nenhuma plataforma. Ele:

  1. Registra a identidade do agente.
  2. Emite eventos de auditoria (tool calls, decisões, resultado) — cada evento
     vai para a plataforma (se configurada) e SEMPRE para uma trilha local em
     JSONL, de modo que a governança seja auditável mesmo offline.
  3. Avalia políticas antes de uma ação, com fallback local via policies.yaml.

Para integrar a QUALQUER plataforma (ex.: Cohort), você não muda código — só
define as env vars de rota/auth. Ver docs/GUIA.md, seção "Integração".

Env relevantes:
  GOVERNANCE_URL         base da plataforma (vazio = só local)
  AGENT_CREDENTIAL       segredo de auth
  GOV_AUTH_STYLE         bearer | header | query | none            (default bearer)
  GOV_AUTH_HEADER        nome do header quando style=header/query  (default Authorization)
  GOV_REGISTER_PATH      default /agents/register
  GOV_EVENTS_PATH        default /agents/{agent_id}/events
  GOV_POLICY_PATH        default /policy/evaluate
  GOV_HEARTBEAT_PATH     default /agents/{agent_id}/heartbeat
  GOV_SHUTDOWN_PATH      default /agents/{agent_id}/shutdown
  GOV_TOKEN_FIELD        campo do token na resposta de registro     (default session_token)
  GOV_POLICY_ALLOW_FIELD campo booleano de decisão na resposta      (default allow)
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import yaml

from .identity import AgentIdentity


@dataclass
class PolicyDecision:
    allow: bool
    reason: str = ""

    def __bool__(self) -> bool:
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

        # Rotas configuráveis (permitem apontar para o contrato do Cohort).
        self.paths = {
            "register": os.getenv("GOV_REGISTER_PATH", "/agents/register"),
            "events": os.getenv("GOV_EVENTS_PATH", "/agents/{agent_id}/events"),
            "policy": os.getenv("GOV_POLICY_PATH", "/policy/evaluate"),
            "heartbeat": os.getenv("GOV_HEARTBEAT_PATH", "/agents/{agent_id}/heartbeat"),
            "shutdown": os.getenv("GOV_SHUTDOWN_PATH", "/agents/{agent_id}/shutdown"),
        }
        self.auth_style = os.getenv("GOV_AUTH_STYLE", "bearer").lower()
        self.auth_header = os.getenv("GOV_AUTH_HEADER", "Authorization")
        self.token_field = os.getenv("GOV_TOKEN_FIELD", "session_token")
        self.allow_field = os.getenv("GOV_POLICY_ALLOW_FIELD", "allow")

        audit_dir = audit_dir or os.getenv("AUDIT_DIR", "./audit")
        self._audit_path = Path(audit_dir) / f"{identity.agent_id}.jsonl"
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

        self._seq = 0
        self.session_token: Optional[str] = None

    def _path(self, key: str) -> str:
        return self.paths[key].format(agent_id=self.identity.agent_id, run_id=self.run_id)

    # ── ciclo de vida ────────────────────────────────────────────────
    def register(self) -> dict:
        manifest = {
            **self.identity.to_manifest(),
            "run_id": self.run_id,
            "sdk": "governed-langchain/0.1",
        }
        self.emit("agent.register", {"manifest": manifest}, level="info")
        resp = self._post(self._path("register"), manifest)
        if resp is not None:
            self.session_token = resp.get(self.token_field) or resp.get("token")
        return resp or {"status": "local-only", "agent_id": self.identity.agent_id}

    def heartbeat(self, status: str = "healthy") -> None:
        self.emit("agent.heartbeat", {"status": status}, level="debug")
        self._post(self._path("heartbeat"), {"status": status})

    def shutdown(self, status: str = "completed") -> None:
        self.emit("agent.shutdown", {"status": status}, level="info")
        self._post(self._path("shutdown"), {"status": status})

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
        resp = self._post(self._path("policy"), body)
        if resp is not None and self.allow_field in resp:
            decision = PolicyDecision(bool(resp[self.allow_field]), resp.get("reason", ""))
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
        pol_path = Path(__file__).parent / "policies.yaml"
        if not pol_path.exists():
            return PolicyDecision(True, "default-allow (sem política local)")
        rules = yaml.safe_load(pol_path.read_text(encoding="utf-8")) or {}
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
        with self._audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._post(self._path("events"), record, audit=False)

    # ── transporte ───────────────────────────────────────────────────
    def _auth(self, headers: dict, params: dict) -> None:
        if not self.api_key or self.auth_style == "none":
            return
        if self.auth_style == "bearer":
            headers[self.auth_header] = f"Bearer {self.api_key}"
        elif self.auth_style == "header":
            headers[self.auth_header] = self.api_key
        elif self.auth_style == "query":
            params[self.auth_header] = self.api_key

    def _post(self, path: str, body: dict, audit: bool = True) -> Optional[dict]:
        if not self.base_url:
            return None
        headers = {"Content-Type": "application/json"}
        params: dict = {}
        self._auth(headers, params)
        url = f"{self.base_url}{path}"
        try:
            r = requests.post(url, json=body, headers=headers, params=params, timeout=8)
            r.raise_for_status()
            return r.json() if r.content else {}
        except Exception as exc:  # noqa: BLE001 — governança nunca deve derrubar o agente
            if audit:
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
