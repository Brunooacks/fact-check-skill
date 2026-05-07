# Hierarquia de fontes / Source tiers

Used to judge source quality. Not enforced as a hard score in MVP — surfaced as context in the Methodology section when relevant.

## Tier 1 — Oficial / Official

The primary record. Use these whenever they exist.

- Statistical bureaus: IBGE (BR), Eurostat (EU), BLS (US), ONS (UK), INSEE (FR)
- Central banks: BCB, ECB, Federal Reserve, Bank of England
- Multilaterals: IMF, World Bank, OECD, WHO, UNCTAD
- Securities regulators: SEC, CVM, FCA, ESMA
- Publicly filed company documents: 10-K, 20-F, formulários de referência (CVM)

## Tier 2 — Acadêmico/Institucional / Academic & Institutional

Peer-reviewed or institution-stamped. Quality varies — prefer original publications over working papers.

- Peer-reviewed journals
- Working papers from NBER, BIS, IMF research, ECB working paper series
- Strategy consultancies: McKinsey Global Institute, BCG, Bain, Deloitte Insights
- Industry analysts: Gartner, Forrester, IDC, Euromonitor

## Tier 3 — Imprensa estabelecida / Established press

Reliable for events, less so for derived numbers (which are often re-quotes — chase the original).

- Financial: FT, WSJ, The Economist, Reuters, Bloomberg
- BR: Folha, Estadão, Valor Econômico, O Globo
- Trade press appropriate to the domain (e.g., Lloyd's List for shipping)

## Tier 4 — Outros / Other

Mixed reliability.

- Company own-site claims (valid for facts about the company itself, suspect for market sizing)
- Industry associations (often advocacy-tinged — note the affiliation)
- Specialized blogs by named experts in the field

## Tier 5 — Não confiável / Untrusted

- Anonymous aggregators
- "Top 10" listicle sites
- Auto-generated content
- Forum posts presented as fact

## How to apply in MVP

For now: just record what you found. The Methodology section of the report should mention the tier of the consulted source if it's Tier 4 or 5 — that's a soft warning the reader should consider.

In v1, alert **A2 — Weak source** will fire automatically when a tier-4/5 source is used to back a quantitative claim.

## Configurability (v1)

A future `~/.claude/skills/fact-check/sources.config` will let projects:

- Add domain-specific Tier 1 sources (e.g., ANBIMA for Brazilian fixed income, IATA for aviation traffic).
- Promote/demote tiers for a specific use case (a marketing brief might trust trade press more; a regulatory filing demands Tier 1).
