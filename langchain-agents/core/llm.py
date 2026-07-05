"""Factory de LLM para os agentes LangChain.

Padrão: Claude (Anthropic). Se não houver ANTHROPIC_API_KEY, cai para um
StubChatModel determinístico — o suficiente para exercitar identidade,
ferramentas e governança sem gastar tokens nem depender de rede.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class StubChatModel(BaseChatModel):
    """LLM falso e determinístico. Marca `is_stub=True`.

    Não executa tool-calling real — o worker detecta o stub e roda um plano
    determinístico de ferramentas, mantendo a trilha de governança íntegra.
    """

    is_stub: bool = True

    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        text = (
            "[STUB LLM] Sem ANTHROPIC_API_KEY — executando plano determinístico. "
            "Configure a chave para usar o Claude com raciocínio real."
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    @property
    def _llm_type(self) -> str:
        return "stub-chat-model"


def build_llm(model: Optional[str] = None, temperature: float = 0.0) -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = model or os.getenv("LLM_MODEL", "claude-sonnet-5")
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if provider == "anthropic" and api_key:
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model=model, temperature=temperature, max_tokens=2048)
        setattr(llm, "is_stub", False)
        return llm

    return StubChatModel()


def is_stub(llm: Any) -> bool:
    return bool(getattr(llm, "is_stub", False))
