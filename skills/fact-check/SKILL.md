---
name: fact-check
description: Audit factual claims and sources in executive materials (decks, memos, board reports, proposals) — input is .docx, .pptx, .pdf, or a URL, output is a bilingual PT/EN diagnostic that classifies every claim as Confirmed, Contradictory, Not verifiable, or Source inaccessible. Use this whenever the user asks to verify, fact-check, audit, validate sources, double-check numbers, or check citations in a document, presentation, or report — even when they don't explicitly use the word "fact-check". Trigger for prompts like "audita este deck", "verifica os números deste memo", "check the sources in this presentation", "is this report accurate", or any drag-and-drop of an executive document with a request to review it. Do NOT use for general writing/editing tasks, plagiarism checks, or legal review.
---

# Fact-check skill

You are auditing an executive material for factual integrity. The user wrote it (often with AI assistance) and is about to circulate it to senior stakeholders. Your job is **diagnosis, not rewriting**. Every claim becomes a row with a verdict; the human decides what to fix.

## Why this skill exists

Materials produced with AI assistance carry three risks: hallucinated numbers/citations, sources that exist but say something different, and outdated indicators. The reviewer's time is usually wasted re-checking each claim manually. This skill produces a structured report that lets the reviewer attack only the rows that need attention.

## When you trigger

Run the full workflow whenever the input is a `.docx`, `.pptx`, `.pdf`, or URL and the user asks to verify, audit, fact-check, validate sources, or double-check anything in it. If the user only asks to summarize or rewrite, **do not run** this skill — defer to the normal flow.

## Setup (one time)

The skill ships with a Python toolbelt. Before the first run on a machine, install dependencies:

```bash
pip install -r ~/.claude/skills/fact-check/requirements.txt
```

If `pytesseract` (OCR) fails on a scanned PDF, the user also needs the Tesseract binary (`brew install tesseract` on macOS, `apt install tesseract-ocr` on Debian-likes). Tell the user this only if OCR is actually needed and fails — don't preemptively block.

If a `~/.claude/skills/fact-check/config.yaml` exists, the scripts read overrides from it. Otherwise sensible defaults apply.

## The workflow

You orchestrate four stages. Python scripts do the deterministic work (parsing, regex extraction, rendering). You do the judgment work (deciding what's verifiable, finding sources, assigning verdicts).

### Stage 1 — Ingest

Run the ingester to extract text and a location map.

```bash
python ~/.claude/skills/fact-check/scripts/ingest.py <input> --out /tmp/fact-check/ingest.json
```

`<input>` is a path to `.docx`/`.pptx`/`.pdf` or an `http(s)://` URL. The output JSON has the shape:

```json
{
  "source": "deck.pdf",
  "kind": "pdf",
  "language_guess": "pt",
  "blocks": [
    {"id": "p3", "location": "page 3", "text": "..."},
    {"id": "p4", "location": "page 4", "text": "..."}
  ],
  "warnings": []
}
```

For `.pptx` and `.pdf`, location is `slide N` or `page N`. For `.docx`, it's `paragraph N` (with heading context when available). For URLs, it's the section heading or `body`. If a PDF has no extractable text, the ingester invokes Tesseract OCR automatically and adds a `warnings` entry.

If the ingester returns warnings about unreadable content or missing OCR binary, surface them to the user immediately — don't try to verify a half-extracted document.

### Stage 2 — Extract claim candidates

Run the extractor on the ingest output.

```bash
python ~/.claude/skills/fact-check/scripts/extract_claims.py /tmp/fact-check/ingest.json --out /tmp/fact-check/claims.json
```

This produces a list of **candidate** claims. The script is intentionally liberal — it flags anything that *might* be verifiable so you don't miss things. Your job in stage 3 is to triage.

A candidate looks like:

```json
{
  "id": "c-001",
  "block_id": "p3",
  "location": "page 3",
  "text_excerpt": "O mercado brasileiro de seguros cresceu 12,4% em 2024 segundo a SUSEP.",
  "candidate_kind": "numeric_with_attribution",
  "declared_source_hint": "SUSEP"
}
```

`candidate_kind` is one of: `numeric`, `numeric_with_attribution`, `date_event`, `citation`, `named_entity_factual`. Use it to decide how aggressively to verify (numeric_with_attribution is high-priority; citation always needs source verification; named_entity_factual is lowest).

### Stage 3 — Verify (this is your work)

Iterate over the candidates. For each one:

1. **Decide if it's truly verifiable.** Drop qualitative/opinion claims ("o mercado está aquecido"), hypotheticals, narrative framing. Keep facts, numbers, dates, attributions. When in doubt, keep it — diagnosing too much is fine; diagnosing too little is the failure mode.

2. **Find the declared source.** Check: footnote on the same block, citation inline, slide of references at the end, table caption, chart legend. Read references/source-detection.md if you need help with edge cases.

3. **Verify against the source.**
   - **If declared source is accessible**: use `WebFetch` on the URL and confirm the claim *exactly* — value, time period, geography, methodology. A claim citing "Brazil 2024" against a source reporting "LatAm 2023" is a mismatch even if the number is similar. This is the most common failure pattern, so be deliberate about it.
   - **If declared source is inaccessible** (paywall, 404, requires login): do NOT try to verify against a third-party source — that creates false confidence. Mark verdict as 🔒 `source_inaccessible`.
   - **If no declared source**: run `WebSearch` to look for a plausible source. If you find one and it confirms the claim, attach it as `suggested_source` but the verdict stays ⚫ `not_verifiable` (no declared source means no accountability — surfacing this is the whole point of the skill).

4. **Assign a verdict** from the MVP taxonomy:

   | Verdict | When to use |
   |---|---|
   | ✅ `confirmed` | Source declared and accessed; value, period, geography, and methodology all match. |
   | 🔴 `contradictory` | Source declared and accessed; says something materially different from the claim. |
   | 🔒 `source_inaccessible` | Source declared but you couldn't read it (paywall, dead link, login wall). |
   | ⚫ `not_verifiable` | No source declared, or no plausible source found, or the claim is too vague to test. |

   Stick to these four for MVP. The full taxonomy (Partial, Outdated, Confirmed-with-ressalva, etc.) is in references/verdicts.md but is not in scope yet.

5. **Record evidence.** Always note: the URL you consulted, a short quote (under 15 words) showing what the source actually says, and a one-line explanation of your judgment.

### Stage 4 — Render the report

Once you've graded every candidate worth keeping, write your verdicts to `/tmp/fact-check/verdicts.json` in this shape:

```json
{
  "source": "deck.pdf",
  "language": "pt",
  "verdicts": [
    {
      "id": "c-001",
      "location": "page 3",
      "claim": "Mercado brasileiro de seguros cresceu 12,4% em 2024 (SUSEP).",
      "verdict": "contradictory",
      "declared_source": "SUSEP",
      "consulted_url": "https://www.gov.br/susep/...",
      "evidence_quote": "crescimento de 9,8% no exercício de 2024",
      "judgment": "SUSEP reporta 9,8%, não 12,4%. Diferença material."
    }
  ]
}
```

Then run:

```bash
python ~/.claude/skills/fact-check/scripts/render_report.py /tmp/fact-check/verdicts.json --out /tmp/fact-check/report
```

This emits two files: `report.md` (the bilingual diagnostic the user reads) and `report.json` (for pipeline integration). Tell the user where both files are.

## Output contract

The markdown report **must** contain these sections in order, with bilingual headers:

```
# Fact-check report — {source}

## Sumário executivo / Executive summary
- Claims totais / Total claims: N
- Confirmados / Confirmed: N
- Contraditórios / Contradictory: N    ← critical row, bold if > 0
- Fonte inacessível / Source inaccessible: N
- Não verificáveis / Not verifiable: N

## Alertas críticos / Critical alerts
(only the contradictory + source_inaccessible rows, with location)

## Tabela completa / Full table
(every claim, every verdict, with location, declared source, evidence URL, quote)

## Metodologia / Methodology
(one paragraph: which sources you consulted, when, and any limitations)
```

The body text of each row is in the **document's language** (detected by the ingester). Headers and verdict labels are bilingual. This keeps the report readable for the original author without forcing translation of the substance.

## Modes

- **Default (online)**: uses `WebSearch` and `WebFetch` for verification. Good for almost all cases.
- **Offline mode**: when the user says "modo offline", "sensitive content", "don't search the web", or the document has confidentiality markers (CONFIDENCIAL, INTERNAL ONLY, RESTRICTED), skip all web calls. Verify only against sources whose URLs are *declared in the document itself*, and mark everything else `not_verifiable` with a note that the offline mode was active. Tell the user this clearly in the report's Methodology section.

If the user hasn't asked for offline mode and you don't see confidentiality markers, default to online. Don't ask permission for each web call — that defeats the workflow.

## Failure modes to avoid

- **Confirming based on similarity, not match.** If the document says "Brazil 12.4% in 2024" and you find a source saying "12% in 2023", that's not confirmed. It's contradictory or partial. The whole point of this skill is to catch these.
- **Verifying against a re-quote.** If you land on a news article that itself cites the original report, follow through to the original. Re-quotes drift.
- **Skipping the location field.** Every verdict needs the page/slide/paragraph. Without it, the human can't act on the report.
- **Inventing a "suggested_source" when none was declared.** Surfacing the absence of a source is more valuable than papering over it. Mark `not_verifiable` and let the human decide whether to add a citation.
- **Quoting more than 15 words from any source.** Stick to short, marked quotes.

## When to refuse or escalate

- The document is private/internal data with no public source path → mark relevant claims `out_of_scope` (not in MVP verdicts; for now, classify as `not_verifiable` with a note "depends on internal data").
- The document is more than ~80 claims and the user wants it in 5 minutes → tell them the realistic time budget and offer to sample (e.g., "I can audit the 30 most prominent numerical claims in 5 minutes; full pass will take ~15 minutes").
- Ingestion fails entirely (corrupt file, password-protected) → report the error and stop. Don't fake a partial diagnosis.

## Reference material

- `references/verdicts.md` — Full taxonomy with examples (MVP uses subset).
- `references/source-tiers.md` — Hierarchy of source quality (Tier 1 official → Tier 5 untrusted).
- `references/source-detection.md` — Heuristics for finding declared sources in messy documents.
- `references/claim-extraction.md` — What counts as a verifiable claim and what doesn't.

Read these only when you hit an edge case — the SKILL.md alone is sufficient for most documents.
