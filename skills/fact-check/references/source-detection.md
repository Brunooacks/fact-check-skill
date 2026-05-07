# Detectando fontes declaradas / Detecting declared sources

The extractor's `declared_source_hint` catches the obvious cases. This file covers the messy ones.

## Where authors actually put sources

In rough frequency order across executive materials:

1. **Inline parenthetical** — `(IBGE, 2024)`, `(McKinsey 2023)`, `(SUSEP)`. Most common in memos.
2. **Footnote markers** — `¹`, `²`, `[1]`, `*` — with the source defined at the bottom of the slide/page.
3. **Chart legend or caption** — "Fonte: BCB" / "Source: Federal Reserve".
4. **Slide of references** — common at the end of decks. Often labeled "Fontes / References / Bibliography / Methodology".
5. **Inline phrases** — "segundo a SUSEP", "according to McKinsey", "per Bloomberg".
6. **Hyperlinked text** — the URL is embedded but not visible in extracted text. Watch for this when verifying.

## Heuristics for messy cases

- **Source on a different slide.** Slide 12 has a number; slide 38 has the references list. Check the references page when you can't find a source near the claim.
- **Multiple claims, one source.** "Fonte para todos os números desta seção: X". A section header source applies to every claim under it until a new one appears.
- **Implied source from context.** A page titled "Resultados financeiros 2024 — Empresa X" implies the company is the source for its own numbers. That's Tier 4 by default.
- **Chart with axis label as source.** "% YoY (BCB)" in a chart subtitle — that's a declared source for the chart's data.

## What is *not* a declared source

- A logo on the slide. Logos are decoration; an actual source attribution must be a textual claim.
- A footer with "Confidential / Property of Acme Inc.". That's ownership, not provenance.
- "As reported in the press" with no specific outlet. Too vague.
- "Industry reports" without naming any. Too vague.

## When `declared_source_hint` is null

Look harder before marking `not_verifiable`:

1. Re-read the block before and after the claim's location.
2. Check the document's first slide and last 2-3 slides for a methodology/sources page.
3. If the claim is in a chart, check the chart's caption and legend.
4. If you find the source in a different block, edit the verdict's `declared_source` field — the extractor's hint is a starting point, not the final answer.

## Quick rules of thumb

- Gov.br / federal domains → Tier 1, treat as authoritative.
- A consultancy mentioned without a specific report title → suspicious. Real citations include the report name and year.
- "Estimativa interna" / "internal estimate" → out of scope for verification; mark `not_verifiable` with a note.
- A number with three decimal places and no source → high hallucination risk (alert A5 in v1).
