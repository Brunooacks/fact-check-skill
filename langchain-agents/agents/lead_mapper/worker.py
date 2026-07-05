"""Entrypoint do agente de mapeamento de leads/oportunidades (Veltrix)."""
from __future__ import annotations

from pathlib import Path

from core.worker import GovernedWorker
from .tools import TOOLS, demo_plan

SYSTEM_PROMPT = """Você é o Lead Mapper Agent da Veltrix Platform.
Sua responsabilidade é encontrar empresas que usam intensivamente APIs de IA e
qualificá-las como prospects para a Veltrix (plataforma de governança de agentes).

Diretrizes:
- Use as ferramentas para descobrir, enriquecer e pontuar empresas — não invente dados.
- Priorize sinais que aumentam a necessidade de governança: muitos agentes em
  produção, multi-vendor de IA, setor regulado e alto volume de chamadas.
- Entregue uma lista priorizada de oportunidades (hot/warm/cold) com a justificativa
  de cada uma e o ângulo de abordagem para a Veltrix.
"""

DEFAULT_TASK = (
    "Mapeie prospects que usam muito APIs de IA e gere as oportunidades mais "
    "quentes para a Veltrix Platform, com score e ângulo de abordagem."
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
