# O que é um claim verificável / What counts as a verifiable claim

The extractor flags candidates liberally. You triage in stage 3. This file is the rubric.

## Keep (verify these)

| Type | PT example | EN example |
|---|---|---|
| Numerical indicator with unit | "Mercado cresceu 12,4% em 2024" | "Margin expanded 320 bps in Q3" |
| Monetary value | "R$ 4,2 bilhões em prêmios" | "$1.8B in revenue" |
| Date or period of an event | "Adquiriu Y em 2023" | "IPO'd in March 2024" |
| Attributed citation | "Segundo a McKinsey..." | "According to BLS..." |
| Quote attributed to a person | "Lula disse que..." | "Powell stated..." |
| Authorship/job title in factual context | "Fulano, CEO da X desde 2022" | "Jane Doe, COO of Y" |
| Ranking or superlative with concrete basis | "Maior banco da AL por ativos" | "Largest US retailer by revenue" |
| Quantified comparison | "3x maior que concorrentes" | "twice the EBITDA of peers" |

## Drop (these are not claims for this skill)

| Type | Why drop |
|---|---|
| Qualitative judgment | "O mercado está aquecido" — opinion, no factual core. |
| Strategic narrative | "A estratégia da concorrência é frágil" — opinion. |
| Forecasts without a model attribution | "Vamos crescer muito" — no source possible. |
| Hypotheticals | "Se a Selic cair..." — conditional, not a claim. |
| Generic illustrations | "Um exemplo seria..." — narrative device. |
| Restated company values/mission | "Acreditamos em transparência" — corporate boilerplate. |
| Decorative numbers | A page number, slide count, agenda item. |

## Edge cases

- **Forecasts WITH attribution.** "Itaú projeta IPCA de 4,5% para 2026" → keep (the forecast itself is the source's claim, even if the future is uncertain).
- **Round numbers in narrative.** "Cerca de 80% dos clientes..." with no source → keep as `numeric` candidate; will likely become `not_verifiable`.
- **Industry truisms.** "O cliente brasileiro prefere..." → drop unless attributed to a specific study.
- **Math-derived numbers.** "Combinando A e B obtemos C." → if A and B are sourced and C is arithmetic, only verify A and B.
- **Trademarks/brand names in factual context.** "Lançou o produto X em 2024" → keep as `date_event`. "X é marca registrada" → drop.

## Why err on the side of keeping

The dominant failure mode of this skill (per PRD M3) is **false confirmations**, not false rejections. Keeping a borderline candidate just means it ends up classified as `not_verifiable` — which is harmless. Skipping a real claim means a hallucinated number reaches the executive — which is the whole problem we're trying to solve.

When in doubt: keep it.
