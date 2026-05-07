#!/usr/bin/env python3
"""Extract candidate verifiable claims from an ingest.json file.

Liberal extractor: flags anything that *might* be verifiable. The model triages
in stage 3 of the workflow. Better to over-flag than under-flag.

Usage:
    python extract_claims.py <ingest.json> [--out OUTPUT_JSON]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Patterns are intentionally liberal. False positives are filtered by the model later.
NUMBER_PATTERN = re.compile(
    r"""
    (?<![\w\.\-])
    (?:
        (?:R\$|US\$|\$|€|£)\s?\d[\d\.\,]*\s?(?:bilh\w+|milh\w+|mi|bi|tri|trillion|billion|million|k|M|B)?
        | \d+[\.,]\d+\s?(?:%|p\.p\.|pontos?\spercentuais|bps|basis\spoints)
        | \d{1,3}(?:[\.,]\d{3})+(?:[\.,]\d+)?
        | \d+\s?(?:%|bilh\w+|milh\w+|trillion|billion|million)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

# "segundo X", "according to X", "de acordo com X", "X afirma", "per X"
ATTRIBUTION_PATTERNS = [
    re.compile(r"\bsegundo\s+(?:a|o|os|as)?\s*([A-Z][\w\s\-&\.]{2,60})", re.IGNORECASE),
    re.compile(r"\bde acordo com\s+(?:a|o|os|as)?\s*([A-Z][\w\s\-&\.]{2,60})", re.IGNORECASE),
    re.compile(r"\baccording to\s+(?:the\s+)?([A-Z][\w\s\-&\.]{2,60})", re.IGNORECASE),
    re.compile(r"\bper\s+(?:the\s+)?([A-Z][\w\s\-&\.]{2,60})\b", re.IGNORECASE),
    re.compile(r"\bfonte:\s*([A-Z][\w\s\-&\.]{2,80})", re.IGNORECASE),
    re.compile(r"\bsource:\s*([A-Z][\w\s\-&\.]{2,80})", re.IGNORECASE),
    re.compile(r"\b([A-Z][A-Za-z]{2,30})\s+(?:afirma|reporta|estima|projeta|reports?|estimates?|projects?|states?)", re.IGNORECASE),
    re.compile(r"\b(?:o|a)\s+(?:relatório|estudo|report|study)\s+(?:da\s+|do\s+|de\s+|by\s+|from\s+|of\s+)?([A-Z][\w\s\-&\.]{2,60})", re.IGNORECASE),
]

# Catch named entities that look like institutions / orgs (acronyms or capitalized)
ORG_PATTERN = re.compile(
    r"""
    \b(
        [A-Z]{2,6}                          # acronyms: IBGE, FMI, BCB, OECD, McKinsey-style not caught here
        | (?:[A-Z][a-záéíóúâêôãõç]+\s){1,3}[A-Z][a-záéíóúâêôãõç]+   # multi-word capitalized
    )\b
    """,
    re.VERBOSE,
)

# Acquisition / merger / launch — factual events
EVENT_PATTERN = re.compile(
    r"\b(?:adquiriu|comprou|fundiu|lançou|inaugurou|abriu|fechou|encerrou|"
    r"acquired|bought|merged|launched|opened|closed|shut)\b",
    re.IGNORECASE,
)

# Sentence-ish splitter that keeps Portuguese punctuation intact
SENTENCE_SPLIT = re.compile(r"(?<=[\.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])")


def split_sentences(text: str) -> list[str]:
    chunks = SENTENCE_SPLIT.split(text)
    out: list[str] = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        # If a chunk is huge (no punctuation), break by line as fallback
        if len(c) > 600:
            for line in c.split("\n"):
                line = line.strip()
                if line:
                    out.append(line)
        else:
            out.append(c)
    return out


def extract_from_sentence(sentence: str) -> dict[str, Any] | None:
    has_number = bool(NUMBER_PATTERN.search(sentence))
    has_year = bool(YEAR_PATTERN.search(sentence))
    declared_source: str | None = None
    for pat in ATTRIBUTION_PATTERNS:
        m = pat.search(sentence)
        if m:
            declared_source = m.group(1).strip().rstrip(".,;:")
            break

    # Also detect inline "(IBGE, 2024)" style
    paren_cite = re.search(r"\(([A-Z][\w\s\-&\.]{2,40}),?\s*\d{4}\)", sentence)
    if not declared_source and paren_cite:
        declared_source = paren_cite.group(1).strip()

    has_event = bool(EVENT_PATTERN.search(sentence))

    if has_number and declared_source:
        kind = "numeric_with_attribution"
    elif has_number:
        kind = "numeric"
    elif declared_source:
        kind = "citation"
    elif has_year and has_event:
        kind = "date_event"
    elif has_event and ORG_PATTERN.search(sentence):
        kind = "named_entity_factual"
    else:
        return None

    return {
        "candidate_kind": kind,
        "declared_source_hint": declared_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract candidate claims from ingest.json")
    parser.add_argument("ingest", help="Path to ingest.json")
    parser.add_argument("--out", default="-", help="Output JSON path (default: stdout)")
    parser.add_argument("--max-claims", type=int, default=200, help="Cap on candidates emitted")
    args = parser.parse_args()

    ingest = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
    candidates: list[dict[str, Any]] = []
    counter = 0
    for block in ingest.get("blocks", []):
        sentences = split_sentences(block["text"])
        for sentence in sentences:
            extracted = extract_from_sentence(sentence)
            if not extracted:
                continue
            counter += 1
            cand = {
                "id": f"c-{counter:03d}",
                "block_id": block["id"],
                "location": block["location"],
                "text_excerpt": sentence[:500],
                **extracted,
            }
            candidates.append(cand)
            if len(candidates) >= args.max_claims:
                break
        if len(candidates) >= args.max_claims:
            break

    payload = {
        "source": ingest.get("source"),
        "language": ingest.get("language_guess", "unknown"),
        "candidates": candidates,
        "candidate_count": len(candidates),
        "truncated": len(candidates) >= args.max_claims,
    }
    out_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(out_text)
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_text, encoding="utf-8")
        print(f"Wrote {len(candidates)} candidates to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
