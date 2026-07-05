"""Cenários de avaliação do Banking Benchmark Agent.

capability: a engine de benchmark decide corretamente?
purpose:    o agente, ponta-a-ponta, cumpre o objetivo descrito na tarefa?
"""
from core.evaluation import Scenario

EVALS = [
    Scenario(
        name="menor-taxa-lidera-credito-pessoal",
        category="capability",
        tool="benchmark_products",
        tool_input={"category": "credito_pessoal", "dimension": "apr_pct"},
        asserts=[
            {"path": "leader", "equals": "NeoBank Gama"},
            {"path": "lower_is_better", "equals": True},
            {"path": "ranking.0.competitiveness_score", "gte": 99},
        ],
    ),
    Scenario(
        name="maior-cashback-lidera-cartao",
        category="capability",
        tool="benchmark_products",
        tool_input={"category": "cartao_credito", "dimension": "cashback_pct"},
        asserts=[
            {"path": "leader", "equals": "Banco Beta"},
            {"path": "lower_is_better", "equals": False},
        ],
    ),
    Scenario(
        name="dimensao-invalida-retorna-erro",
        category="capability",
        tool="benchmark_products",
        tool_input={"category": "conta_digital", "dimension": "inexistente"},
        asserts=[{"path": "error", "contains": "inexistente"}],
    ),
    Scenario(
        name="lookup-por-product-id",
        category="capability",
        tool="get_product_metrics",
        tool_input={"product_id": "gama-cp"},
        asserts=[
            {"path": "institution", "equals": "NeoBank Gama"},
            {"path": "apr_pct", "lte": 4.0},
        ],
    ),
    Scenario(
        name="proposito-recomenda-menor-juros",
        category="purpose",
        task=("Faça o benchmark de crédito pessoal e recomende a melhor opção "
              "para quem prioriza menor taxa de juros."),
        asserts=[
            {"contains": "NeoBank Gama"},   # deve destacar o líder de menor APR
            {"contains": "apr_pct"},        # deve ter usado a dimensão certa
        ],
    ),
]
