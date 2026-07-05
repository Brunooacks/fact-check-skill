"""Ferramentas do agente de mapeamento de leads/oportunidades para a Veltrix.

Foco: encontrar empresas que usam MUITO APIs de IA (portanto candidatas naturais
a uma plataforma de governança de agentes) e qualificá-las como prospects.

Dataset SIMULADO e determinístico. Troque o corpo das funções por chamadas às
suas fontes reais (enriquecimento firmográfico, sinais de uso de IA, CRM).
"""
from __future__ import annotations

import json
from typing import List

from langchain_core.tools import tool

# Universo simulado de empresas com sinais de uso de IA.
_COMPANIES = [
    {"company": "FinPay", "sector": "fintech", "employees": 420, "ai_api_calls_month": 9_500_000,
     "ai_vendors": ["openai", "anthropic"], "agents_in_prod": 12, "regulated": True, "region": "BR"},
    {"company": "HealthLoop", "sector": "healthtech", "employees": 180, "ai_api_calls_month": 3_200_000,
     "ai_vendors": ["anthropic"], "agents_in_prod": 5, "regulated": True, "region": "BR"},
    {"company": "ShopWave", "sector": "ecommerce", "employees": 900, "ai_api_calls_month": 14_000_000,
     "ai_vendors": ["openai", "google"], "agents_in_prod": 20, "regulated": False, "region": "LATAM"},
    {"company": "LegalMind", "sector": "legaltech", "employees": 60, "ai_api_calls_month": 1_100_000,
     "ai_vendors": ["anthropic", "openai"], "agents_in_prod": 8, "regulated": True, "region": "BR"},
    {"company": "EduSpark", "sector": "edtech", "employees": 240, "ai_api_calls_month": 600_000,
     "ai_vendors": ["openai"], "agents_in_prod": 2, "regulated": False, "region": "LATAM"},
    {"company": "InsureCore", "sector": "insurtech", "employees": 1300, "ai_api_calls_month": 7_800_000,
     "ai_vendors": ["anthropic", "google"], "agents_in_prod": 16, "regulated": True, "region": "BR"},
]


@tool
def discover_companies(sector: str = "any", min_ai_calls: int = 1_000_000) -> str:
    """Descobre empresas com uso intensivo de APIs de IA.

    sector: filtra por setor (ex.: 'fintech', 'healthtech') ou 'any' para todos.
    min_ai_calls: volume mínimo de chamadas mensais a APIs de IA para considerar
    a empresa "AI-heavy". Retorna JSON com as empresas que passam no filtro.
    """
    s = sector.strip().lower()
    found = [
        c for c in _COMPANIES
        if (s in ("any", "", "all") or c["sector"] == s) and c["ai_api_calls_month"] >= min_ai_calls
    ]
    found.sort(key=lambda c: c["ai_api_calls_month"], reverse=True)
    return json.dumps({"count": len(found), "companies": found}, ensure_ascii=False)


@tool
def enrich_company(company: str) -> str:
    """Enriquece uma empresa com sinais adicionais relevantes para governança de IA."""
    for c in _COMPANIES:
        if c["company"].lower() == company.strip().lower():
            enriched = dict(c)
            enriched["governance_signals"] = {
                "multi_vendor": len(c["ai_vendors"]) > 1,
                "high_agent_footprint": c["agents_in_prod"] >= 10,
                "regulated_industry": c["regulated"],
                "est_monthly_ai_spend_usd": round(c["ai_api_calls_month"] * 0.000_6, 2),
            }
            return json.dumps(enriched, ensure_ascii=False)
    return json.dumps({"error": "empresa não encontrada", "company": company}, ensure_ascii=False)


@tool
def score_prospect(company: str) -> str:
    """Pontua o fit de uma empresa como prospect da Veltrix (governança de agentes).

    Score 0-100 baseado em: volume de uso de IA, nº de agentes em produção,
    multi-vendor (complexidade de governança) e se é setor regulado (necessidade
    de compliance). Retorna score, tier (hot/warm/cold) e a justificativa.
    """
    target = next((c for c in _COMPANIES if c["company"].lower() == company.strip().lower()), None)
    if target is None:
        return json.dumps({"error": "empresa não encontrada", "company": company}, ensure_ascii=False)

    # Componentes normalizados (0-1) → pesos.
    vol = min(target["ai_api_calls_month"] / 15_000_000, 1.0)
    agents = min(target["agents_in_prod"] / 20, 1.0)
    multi = 1.0 if len(target["ai_vendors"]) > 1 else 0.4
    reg = 1.0 if target["regulated"] else 0.5

    score = round((vol * 30 + agents * 30 + multi * 20 + reg * 20), 1)
    tier = "hot" if score >= 75 else "warm" if score >= 50 else "cold"
    reasons = []
    if agents >= 0.5:
        reasons.append(f"{target['agents_in_prod']} agentes em produção — alta superfície de governança")
    if multi == 1.0:
        reasons.append(f"multi-vendor ({', '.join(target['ai_vendors'])}) exige política unificada")
    if reg == 1.0:
        reasons.append(f"setor regulado ({target['sector']}) — compliance obrigatório")
    if vol >= 0.5:
        reasons.append(f"{target['ai_api_calls_month']:,} chamadas/mês a APIs de IA")

    return json.dumps({
        "company": target["company"],
        "sector": target["sector"],
        "region": target["region"],
        "prospect_score": score,
        "tier": tier,
        "rationale": reasons,
        "recommended_offer": "Veltrix Platform — governança e auditoria de agentes de IA",
    }, ensure_ascii=False)


TOOLS: List = [discover_companies, enrich_company, score_prospect]


def demo_plan(task: str) -> list:
    """Plano determinístico p/ modo stub: descobre, enriquece e pontua o topo."""
    t = task.lower()
    sector = next((c["sector"] for c in _COMPANIES if c["sector"] in t), "any")
    # Empresa-alvo p/ enriquecer e pontuar = a de maior uso de IA no filtro.
    pool = [c for c in _COMPANIES if sector in ("any",) or c["sector"] == sector]
    top = max(pool, key=lambda c: c["ai_api_calls_month"])["company"]
    return [
        ("discover_companies", {"sector": sector, "min_ai_calls": 1_000_000}),
        ("enrich_company", {"company": top}),
        ("score_prospect", {"company": top}),
    ]
