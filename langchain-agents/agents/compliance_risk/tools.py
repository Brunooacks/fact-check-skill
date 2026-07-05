"""Ferramentas do Compliance/Risk Agent.

Este agente fecha o ciclo de governança: lê as trilhas de auditoria que os
outros agentes gravam (JSONL em AUDIT_DIR), avalia risco em cada evento/saída e
emite um relatório de compliance. É um bom caso de teste para uma plataforma de
governança porque exercita policy-checks, leitura de trilha e classificação de risco.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List

from langchain_core.tools import tool

# Sinais de risco detectáveis num único evento/saída.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def _audit_dir() -> Path:
    return Path(os.getenv("AUDIT_DIR", "./audit"))


def _risk_level(score: int) -> str:
    return "high" if score >= 60 else "medium" if score >= 30 else "low"


@tool
def assess_output_risk(record_json: str) -> str:
    """Avalia o risco de um evento/saída de agente (um registro JSON da trilha).

    Detecta: política negada, erro de runtime e possível PII (e-mail/CPF).
    Retorna score 0-100, risk_level (low/medium/high) e as flags encontradas.
    """
    try:
        rec = json.loads(record_json)
    except Exception:  # noqa: BLE001
        return json.dumps({"error": "record_json inválido"}, ensure_ascii=False)

    event = str(rec.get("event", ""))
    level = str(rec.get("level", ""))
    payload = rec.get("payload", {})
    blob = json.dumps(payload, ensure_ascii=False).lower()

    flags, score = [], 0
    if event == "policy.decision" and payload.get("allow") is False:
        flags.append("policy_denied"); score += 50
    if level == "error" or event.endswith(".error"):
        flags.append("runtime_error"); score += 40
    if _EMAIL.search(blob):
        flags.append("possible_pii"); score += 30
    if _CPF.search(blob):
        flags.append("possible_pii_cpf"); score += 30

    score = min(score, 100)
    return json.dumps({
        "event": event,
        "risk_score": score,
        "risk_level": _risk_level(score),
        "flags": sorted(set(flags)),
    }, ensure_ascii=False)


def _summarize(agent_id: str = "all") -> dict:
    """Sumariza as trilhas de auditoria (helper puro, sem LangChain)."""
    out = []
    for f in sorted(_audit_dir().glob("*.jsonl")):
        aid = f.stem
        if agent_id not in ("all", "", aid):
            continue
        events, tools, denials, errors = 0, set(), 0, 0
        role = ""
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            events += 1
            role = rec.get("role", role)
            ev = rec.get("event", "")
            pl = rec.get("payload", {})
            if ev == "tool.start" and pl.get("tool"):
                tools.add(pl["tool"])
            if ev == "policy.decision" and pl.get("allow") is False:
                denials += 1
            if rec.get("level") == "error" or ev.endswith(".error"):
                errors += 1
        out.append({
            "agent_id": aid, "role": role, "events": events,
            "tools_used": sorted(tools), "policy_denials": denials, "runtime_errors": errors,
        })
    return {"audit_dir": str(_audit_dir()), "count": len(out), "agents": out}


@tool
def read_audit_trail(agent_id: str = "all") -> str:
    """Lê as trilhas de auditoria em AUDIT_DIR e sumariza a atividade dos agentes.

    agent_id: um agent_id específico ou 'all'. Retorna, por agente, contagem de
    eventos, ferramentas usadas, políticas negadas e erros de runtime.
    """
    return json.dumps(_summarize(agent_id), ensure_ascii=False)


@tool
def generate_compliance_report(agent_id: str = "all") -> str:
    """Gera um relatório de compliance agregando risco por agente a partir das trilhas.

    Combina a leitura da trilha com a pontuação de risco e retorna, por agente, um
    risk_level e as findings, além de um overall_risk_level consolidado.
    """
    summary = _summarize(agent_id)
    findings = []
    worst = 0
    for a in summary["agents"]:
        score = a["policy_denials"] * 50 + a["runtime_errors"] * 40
        score = min(score, 100)
        worst = max(worst, score)
        notes = []
        if a["policy_denials"]:
            notes.append(f"{a['policy_denials']} política(s) negada(s)")
        if a["runtime_errors"]:
            notes.append(f"{a['runtime_errors']} erro(s) de runtime")
        if not notes:
            notes.append("sem violações detectadas na trilha")
        findings.append({
            "agent_id": a["agent_id"], "role": a["role"],
            "risk_score": score, "risk_level": _risk_level(score), "notes": notes,
        })
    return json.dumps({
        "report": "agent_compliance",
        "agents_audited": summary["count"],
        "overall_risk_level": _risk_level(worst),
        "findings": findings,
    }, ensure_ascii=False)


TOOLS: List = [assess_output_risk, read_audit_trail, generate_compliance_report]


def demo_plan(task: str) -> list:
    """Plano determinístico p/ modo stub: lê trilha e gera relatório de compliance."""
    return [
        ("read_audit_trail", {"agent_id": "all"}),
        ("generate_compliance_report", {"agent_id": "all"}),
    ]
