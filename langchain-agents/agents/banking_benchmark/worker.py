"""Entrypoint do agente de benchmarking de produtos bancários."""
from __future__ import annotations

from pathlib import Path

from core.worker import GovernedWorker
from .tools import TOOLS, demo_plan

SYSTEM_PROMPT = """Você é o Banking Benchmark Agent.
Sua responsabilidade é comparar produtos bancários entre instituições e produzir
um benchmark objetivo e acionável.

Diretrizes:
- Use as ferramentas para obter métricas reais; nunca invente números.
- Sempre indique o líder de cada dimensão e o porquê (score de competitividade).
- Aponte trade-offs (ex.: menor taxa vs. menor prazo).
- Encerre com uma recomendação clara para o perfil descrito na tarefa.
"""

DEFAULT_TASK = (
    "Faça o benchmark de crédito pessoal entre as instituições disponíveis e "
    "recomende a melhor opção para um cliente que prioriza menor taxa de juros."
)


def build() -> GovernedWorker:
    return GovernedWorker(
        identity_path=Path(__file__).parent / "identity.yaml",
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        demo_plan=demo_plan,
        default_task=DEFAULT_TASK,
    )


if __name__ == "__main__":
    build().main()
