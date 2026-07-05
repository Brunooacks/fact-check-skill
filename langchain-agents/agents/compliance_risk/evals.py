"""Cenários de avaliação do Compliance/Risk Agent."""
import json

from core.evaluation import Scenario

_DENIED = json.dumps({"event": "policy.decision", "level": "warning",
                      "payload": {"action": "tool:x", "allow": False, "reason": "bloqueado"}})
_CLEAN = json.dumps({"event": "tool.end", "level": "info",
                     "payload": {"output": "{\"leader\": \"NeoBank Gama\"}"}})
_PII = json.dumps({"event": "tool.end", "level": "info",
                   "payload": {"output": "contato do lead: joao.silva@empresa.com"}})
_ERROR = json.dumps({"event": "tool.error", "level": "error",
                     "payload": {"error": "conexão recusada"}})

EVALS = [
    Scenario(
        name="politica-negada-eleva-risco",
        category="capability",
        tool="assess_output_risk",
        tool_input={"record_json": _DENIED},
        asserts=[
            {"path": "risk_level", "one_of": ["medium", "high"]},
            {"path": "flags", "contains": "policy_denied"},
        ],
    ),
    Scenario(
        name="saida-limpa-e-baixo-risco",
        category="capability",
        tool="assess_output_risk",
        tool_input={"record_json": _CLEAN},
        asserts=[
            {"path": "risk_level", "equals": "low"},
            {"path": "risk_score", "lte": 0},
        ],
    ),
    Scenario(
        name="detecta-pii",
        category="capability",
        tool="assess_output_risk",
        tool_input={"record_json": _PII},
        asserts=[{"path": "flags", "contains": "possible_pii"}],
    ),
    Scenario(
        name="detecta-erro-de-runtime",
        category="capability",
        tool="assess_output_risk",
        tool_input={"record_json": _ERROR},
        asserts=[{"path": "flags", "contains": "runtime_error"}],
    ),
    Scenario(
        name="proposito-gera-relatorio-de-compliance",
        category="purpose",
        task="Audite as trilhas dos agentes e gere um relatório de compliance com o risco de cada um.",
        asserts=[
            {"contains": "overall_risk_level"},
            {"contains": "findings"},
        ],
    ),
]
