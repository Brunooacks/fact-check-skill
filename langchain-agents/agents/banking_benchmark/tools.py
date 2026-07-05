"""Ferramentas do agente de benchmarking de produtos bancários.

Os dados são um dataset SIMULADO e determinístico (não há chamadas a APIs reais
de bancos). Basta trocar o corpo de cada função por uma chamada HTTP à sua fonte
de dados real — a assinatura das tools e a governança permanecem idênticas.
"""
from __future__ import annotations

import json
from typing import List

from langchain_core.tools import tool

# Catálogo simulado: taxas/tarifas por instituição e categoria.
_CATALOG = {
    "credito_pessoal": [
        {"institution": "Banco Alfa", "product_id": "alfa-cp", "apr_pct": 4.2, "monthly_fee": 0.0, "max_term_months": 48, "grace_days": 30},
        {"institution": "Banco Beta", "product_id": "beta-cp", "apr_pct": 3.8, "monthly_fee": 12.9, "max_term_months": 36, "grace_days": 15},
        {"institution": "NeoBank Gama", "product_id": "gama-cp", "apr_pct": 3.5, "monthly_fee": 0.0, "max_term_months": 24, "grace_days": 45},
        {"institution": "Banco Delta", "product_id": "delta-cp", "apr_pct": 5.1, "monthly_fee": 0.0, "max_term_months": 60, "grace_days": 30},
    ],
    "cartao_credito": [
        {"institution": "Banco Alfa", "product_id": "alfa-cc", "annual_fee": 0.0, "cashback_pct": 0.5, "intl_spread_pct": 4.0, "rewards": True},
        {"institution": "Banco Beta", "product_id": "beta-cc", "annual_fee": 240.0, "cashback_pct": 1.5, "intl_spread_pct": 2.0, "rewards": True},
        {"institution": "NeoBank Gama", "product_id": "gama-cc", "annual_fee": 0.0, "cashback_pct": 1.0, "intl_spread_pct": 0.0, "rewards": False},
    ],
    "conta_digital": [
        {"institution": "Banco Alfa", "product_id": "alfa-cd", "monthly_fee": 0.0, "yield_cdi_pct": 100, "free_transfers": True, "atm_withdrawals_free": 4},
        {"institution": "NeoBank Gama", "product_id": "gama-cd", "monthly_fee": 0.0, "yield_cdi_pct": 105, "free_transfers": True, "atm_withdrawals_free": 8},
        {"institution": "Banco Delta", "product_id": "delta-cd", "monthly_fee": 9.9, "yield_cdi_pct": 90, "free_transfers": False, "atm_withdrawals_free": 2},
    ],
}

# Para cada dimensão, se "menor é melhor".
_LOWER_IS_BETTER = {"apr_pct", "monthly_fee", "annual_fee", "intl_spread_pct"}


@tool
def list_banking_products(category: str) -> str:
    """Lista produtos bancários de uma categoria com suas métricas.

    category: uma de 'credito_pessoal', 'cartao_credito', 'conta_digital'.
    Retorna JSON com a lista de produtos e seus atributos.
    """
    products = _CATALOG.get(category.strip().lower())
    if products is None:
        return json.dumps({"error": "categoria desconhecida", "available": list(_CATALOG)}, ensure_ascii=False)
    return json.dumps({"category": category, "products": products}, ensure_ascii=False)


@tool
def get_product_metrics(product_id: str) -> str:
    """Retorna as métricas detalhadas de um produto específico pelo product_id."""
    for products in _CATALOG.values():
        for p in products:
            if p["product_id"] == product_id.strip().lower():
                return json.dumps(p, ensure_ascii=False)
    return json.dumps({"error": "product_id não encontrado", "product_id": product_id}, ensure_ascii=False)


@tool
def benchmark_products(category: str, dimension: str) -> str:
    """Ranqueia os produtos de uma categoria por uma dimensão numérica.

    category: 'credito_pessoal' | 'cartao_credito' | 'conta_digital'.
    dimension: atributo numérico a comparar (ex.: 'apr_pct', 'cashback_pct',
    'yield_cdi_pct', 'annual_fee'). Retorna um ranking com score 0-100 de
    competitividade e o líder da categoria.
    """
    products = _CATALOG.get(category.strip().lower())
    if products is None:
        return json.dumps({"error": "categoria desconhecida", "available": list(_CATALOG)}, ensure_ascii=False)
    dim = dimension.strip()
    valued = [p for p in products if isinstance(p.get(dim), (int, float))]
    if not valued:
        dims = sorted({k for p in products for k, v in p.items() if isinstance(v, (int, float))})
        return json.dumps({"error": f"dimensão '{dim}' inexistente", "numeric_dimensions": dims}, ensure_ascii=False)

    values = [p[dim] for p in valued]
    lo, hi = min(values), max(values)
    lower_better = dim in _LOWER_IS_BETTER
    span = (hi - lo) or 1.0

    ranked = []
    for p in valued:
        raw = (hi - p[dim]) / span if lower_better else (p[dim] - lo) / span
        ranked.append({
            "institution": p["institution"],
            "product_id": p["product_id"],
            dim: p[dim],
            "competitiveness_score": round(raw * 100, 1),
        })
    ranked.sort(key=lambda r: r["competitiveness_score"], reverse=True)
    return json.dumps({
        "category": category,
        "dimension": dim,
        "lower_is_better": lower_better,
        "leader": ranked[0]["institution"],
        "ranking": ranked,
    }, ensure_ascii=False)


TOOLS: List = [list_banking_products, get_product_metrics, benchmark_products]

# Dimensão default para benchmark por categoria (usado no plano determinístico).
_DEFAULT_DIM = {
    "credito_pessoal": "apr_pct",
    "cartao_credito": "cashback_pct",
    "conta_digital": "yield_cdi_pct",
}


def demo_plan(task: str) -> list:
    """Plano determinístico p/ modo stub: escolhe categoria a partir da tarefa."""
    t = task.lower()
    category = next((c for c in _CATALOG if c.replace("_", " ") in t or c in t), "credito_pessoal")
    return [
        ("list_banking_products", {"category": category}),
        ("benchmark_products", {"category": category, "dimension": _DEFAULT_DIM[category]}),
    ]
