"""Cenários de avaliação do Lead Mapper Agent."""
from core.evaluation import Scenario

EVALS = [
    Scenario(
        name="descobre-apenas-ai-heavy",
        category="capability",
        tool="discover_companies",
        tool_input={"sector": "any", "min_ai_calls": 5_000_000},
        asserts=[
            {"path": "count", "gte": 3},
            {"path": "companies.0.company", "equals": "ShopWave"},  # maior uso de IA
        ],
    ),
    Scenario(
        name="fintech-regulada-e-hot",
        category="capability",
        tool="score_prospect",
        tool_input={"company": "FinPay"},
        asserts=[
            {"path": "tier", "equals": "hot"},
            {"path": "prospect_score", "gte": 75},
        ],
    ),
    Scenario(
        name="baixo-uso-nao-e-hot",
        category="capability",
        tool="score_prospect",
        tool_input={"company": "EduSpark"},
        asserts=[
            {"path": "tier", "one_of": ["warm", "cold"]},
            {"path": "prospect_score", "lte": 74.9},
        ],
    ),
    Scenario(
        name="enriquecimento-traz-sinais-de-governanca",
        category="capability",
        tool="enrich_company",
        tool_input={"company": "InsureCore"},
        asserts=[
            {"path": "governance_signals.regulated_industry", "equals": True},
            {"path": "governance_signals.multi_vendor", "equals": True},
        ],
    ),
    Scenario(
        name="proposito-gera-oportunidade-quente",
        category="purpose",
        task="Mapeie prospects que usam muito APIs de IA e gere a oportunidade mais quente para a Veltrix.",
        asserts=[
            {"contains": "hot"},
            {"contains": "Veltrix"},
        ],
    ),
]
