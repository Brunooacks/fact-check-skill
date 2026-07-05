"""Entrypoint do Compliance/Risk Agent."""
from __future__ import annotations

from pathlib import Path

from core.worker import GovernedWorker
from .tools import TOOLS, demo_plan

SYSTEM_PROMPT = """Você é o Compliance/Risk Agent.
Sua responsabilidade é auditar a execução dos outros agentes e classificar o risco.

Diretrizes:
- Use as ferramentas para ler as trilhas de auditoria; não invente eventos.
- Sinalize decisões de política negadas, erros de runtime e possível PII.
- Entregue um relatório de compliance com nível de risco por agente e um veredito
  geral (low/medium/high), destacando o que exige atenção humana.
"""

DEFAULT_TASK = (
    "Audite as trilhas de execução dos agentes e gere um relatório de compliance "
    "com o nível de risco de cada um."
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
