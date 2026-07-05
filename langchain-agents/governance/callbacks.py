"""Ponte entre o LangChain e a governança.

Um callback handler que transforma cada passo do agente (chamada de LLM, chamada
de ferramenta, ação, resposta final) em um evento de auditoria no GovernanceClient.
É assim que a plataforma "enxerga" tudo o que o agente faz em runtime.
"""
from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from .client import GovernanceClient

# Limita tamanho de payloads para não inflar a trilha.
_MAX = 2000


def _clip(value: Any) -> Any:
    s = value if isinstance(value, str) else str(value)
    return s if len(s) <= _MAX else s[:_MAX] + f"…[+{len(s) - _MAX} chars]"


class GovernanceCallbackHandler(BaseCallbackHandler):
    def __init__(self, client: GovernanceClient) -> None:
        self.client = client

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.client.emit("llm.start", {"prompts": [_clip(p) for p in prompts]}, level="debug")

    def on_llm_end(self, response, **kwargs):
        try:
            text = response.generations[0][0].text
        except Exception:  # noqa: BLE001
            text = ""
        self.client.emit("llm.end", {"output": _clip(text)}, level="debug")

    # Nota: os eventos tool.start/end/blocked são emitidos pelo policy-gate
    # (core.worker._gate_tool), que também FAZ CUMPRIR a decisão de política
    # antes de a ferramenta rodar. Aqui ficam apenas LLM e ações do agente.

    def on_agent_action(self, action, **kwargs):
        self.client.emit(
            "agent.action",
            {"tool": action.tool, "input": _clip(action.tool_input)},
        )

    def on_agent_finish(self, finish, **kwargs):
        self.client.emit(
            "agent.finish",
            {"output": _clip(finish.return_values.get("output", ""))},
        )
