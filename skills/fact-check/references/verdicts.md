# Veredictos — taxonomia / Verdict taxonomy

Reference for stage 3 of the workflow. The MVP uses only the four verdicts marked **[MVP]**; the rest are documented for v1 and future iterations.

## MVP verdicts

### ✅ `confirmed` — Confirmado **[MVP]**

The declared source was accessed. Value, time period, geography, and methodology all match the claim.

> *Use only when the source genuinely says the same thing the document says. Similarity is not a match.*

**PT example:** Claim diz "PIB brasileiro cresceu 3,4% em 2024" e o site do IBGE confirma exatamente esses 3,4% para o ano-calendário 2024.

**EN example:** Claim says "US unemployment was 4.1% in Dec 2024" and the BLS release confirms 4.1% for that month.

### 🔴 `contradictory` — Contraditório **[MVP]**

The declared source was accessed and says something materially different from the claim.

> *This is the most valuable verdict to surface — the reader is about to publish something that contradicts its own source. Be specific about what differs.*

**PT example:** Documento diz "12,4%" atribuído à SUSEP; SUSEP reporta 9,8%. Diferença material no mesmo recorte.

**EN example:** Document says "30% of users", source says "30% of paying customers" — different population, materially different claim.

### 🔒 `source_inaccessible` — Fonte inacessível **[MVP]**

A source is declared but cannot be read: paywall, dead link, login wall, file not public, redirect loop.

> *Do not fall back to a third-party source for verification — that creates false confidence. Mark inaccessible and let the human investigate.*

**Common causes:** Bloomberg/FT/WSJ paywalls, McKinsey/Gartner gated downloads, internal SharePoint links, link rot.

### ⚫ `not_verifiable` — Não verificável **[MVP]**

No source is declared in the document, or no plausible source could be found via search, or the claim is too vague to test (e.g., "líder de mercado").

> *If you found a plausible source via web search, attach it as `suggested_source` but **do not** promote the verdict. The absence of a declared source is the finding.*

## v1 verdicts (post-MVP)

### 🟢 `confirmed_with_caveat` — Confirmado com ressalva

Source matches the claim, but with a non-material difference: rounding (12.4% vs 12.43%), a slightly different but comparable cut (FY vs CY), wording that translates the source rather than quoting it.

### 🟡 `partial` — Parcial

Part of the claim matches the source, part does not. Example: "BCB lowered Selic to 10.75% in Jan 2025" — Selic level confirmed, date is wrong (was December).

### ⚠️ `outdated` — Desatualizado

Source supports the claim *as of its publication*, but the indicator has materially moved since. Example: a 2022 inflation figure that's still cited in a 2025 deck.

### 🚫 `out_of_scope` — Fora de escopo

The claim depends on private/internal data that isn't publicly verifiable. Mark and move on. In MVP, fold this into `not_verifiable` with a note "depende de dados internos / depends on internal data".

## Alerts (non-exclusive flags, can coexist with any verdict)

These are out of scope for MVP. Documented here for v1 planners only.

| Code | Label | Description |
|---|---|---|
| A1 | Citation out of context | Real source, but framing distorts what it actually claims. |
| A2 | Weak source | Source is in a low tier for the type of claim (see `source-tiers.md`). |
| A3 | Stale source | Source older than the freshness threshold for its category. |
| A4 | Doubtful attribution | Quote attributed to an author/institution whose authorship couldn't be confirmed. |
| A5 | Hallucination smell | Patterns of fabrication: oddly specific numbers without citation, vague report titles ("a recent McKinsey study"), authors that don't exist. |

## Decision rules

1. **Default to `not_verifiable` rather than `confirmed`.** False confirmations are the most damaging error mode (PRD M3: keep this rate ≤ 2%).
2. **If recorte differs (geography/period/methodology) → `contradictory`, not `confirmed`.** Even if the number is similar.
3. **Inaccessible ≠ not verifiable.** They mean different things and demand different actions from the reader.
4. **One verdict per claim.** If you're torn between two, pick the more conservative (closer to `not_verifiable`).
