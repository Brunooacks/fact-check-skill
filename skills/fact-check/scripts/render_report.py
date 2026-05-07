#!/usr/bin/env python3
"""Render the fact-check report as bilingual markdown + JSON.

Input: verdicts.json with the model's graded claims.
Output: report.md (bilingual diagnostic) and report.json (pipeline-friendly).

Usage:
    python render_report.py <verdicts.json> --out <output_dir_or_basename>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERDICT_LABELS = {
    "confirmed":           ("✅ Confirmado",         "✅ Confirmed"),
    "contradictory":       ("🔴 Contraditório",      "🔴 Contradictory"),
    "source_inaccessible": ("🔒 Fonte inacessível",  "🔒 Source inaccessible"),
    "not_verifiable":      ("⚫ Não verificável",    "⚫ Not verifiable"),
    # Stretch verdicts (v1) — render gracefully if the model emits them
    "confirmed_with_caveat": ("🟢 Confirmado c/ ressalva", "🟢 Confirmed with caveat"),
    "partial":               ("🟡 Parcial",                "🟡 Partial"),
    "outdated":              ("⚠️ Desatualizado",          "⚠️ Outdated"),
    "out_of_scope":          ("🚫 Fora de escopo",         "🚫 Out of scope"),
}

CRITICAL = {"contradictory", "source_inaccessible"}


def label_for(verdict: str) -> str:
    pt, en = VERDICT_LABELS.get(verdict, (verdict, verdict))
    return f"{pt} / {en}"


def collect_sources(verdicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate all URLs consulted across all verdicts, deduped, with citing claim IDs."""
    seen: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        entries: list[dict[str, Any]] = []
        primary = v.get("consulted_url")
        if primary:
            entries.append({
                "url": primary,
                "title": v.get("source_title") or v.get("declared_source"),
                "quote": v.get("evidence_quote"),
                "is_primary": True,
            })
        for extra in v.get("additional_sources", []) or []:
            if not extra.get("url"):
                continue
            entries.append({
                "url": extra["url"],
                "title": extra.get("title"),
                "quote": extra.get("quote"),
                "is_primary": False,
            })
        for e in entries:
            url = e["url"]
            existing = seen.setdefault(url, {
                "url": url,
                "titles": set(),
                "quotes": [],
                "cited_by": [],
            })
            if e.get("title"):
                existing["titles"].add(e["title"])
            if e.get("quote") and e["quote"] not in existing["quotes"]:
                existing["quotes"].append(e["quote"])
            existing["cited_by"].append(v.get("id", "?"))
    # Convert sets to sorted lists for deterministic output
    return [
        {
            "url": s["url"],
            "titles": sorted(s["titles"]),
            "quotes": s["quotes"],
            "cited_by": s["cited_by"],
        }
        for s in seen.values()
    ]


def render_markdown(payload: dict[str, Any]) -> str:
    source = payload.get("source", "(unknown)")
    verdicts = payload.get("verdicts", [])
    counts = Counter(v.get("verdict", "not_verifiable") for v in verdicts)
    total = len(verdicts)
    sources_index = collect_sources(verdicts)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append(f"# Fact-check report — {source}")
    lines.append("")
    lines.append(f"_Gerado em / Generated at: {generated_at}_")
    if payload.get("mode") == "offline":
        lines.append("")
        lines.append("> **Modo offline ativo / Offline mode active** — verificação restrita a fontes declaradas no documento. / Verification restricted to sources declared in the document.")
    lines.append("")

    # ---- Summary
    lines.append("## Sumário executivo / Executive summary")
    lines.append("")
    lines.append(f"- **Claims totais / Total claims:** {total}")
    for v in ["confirmed", "contradictory", "source_inaccessible", "not_verifiable",
              "confirmed_with_caveat", "partial", "outdated", "out_of_scope"]:
        n = counts.get(v, 0)
        if n == 0 and v in {"confirmed_with_caveat", "partial", "outdated", "out_of_scope"}:
            continue
        bullet = f"- {label_for(v)}: {n}"
        if v in CRITICAL and n > 0:
            bullet = f"- **{label_for(v)}: {n}**"
        lines.append(bullet)
    lines.append("")

    # ---- Critical alerts
    critical_rows = [v for v in verdicts if v.get("verdict") in CRITICAL]
    if critical_rows:
        lines.append("## Alertas críticos / Critical alerts")
        lines.append("")
        for v in critical_rows:
            lines.append(f"### {v.get('id', '?')} — {v.get('location', '?')} — {label_for(v.get('verdict', ''))}")
            lines.append("")
            lines.append(f"> {v.get('claim', '')}")
            lines.append("")
            if v.get("declared_source"):
                lines.append(f"**Fonte declarada / Declared source:** {v['declared_source']}")
            if v.get("consulted_url"):
                title = v.get("source_title")
                title_str = f" — _{title}_" if title else ""
                lines.append(f"**URL consultada / URL consulted:** [{v['consulted_url']}]({v['consulted_url']}){title_str}")
            if v.get("evidence_quote"):
                lines.append(f"**Evidência / Evidence:** \"{v['evidence_quote']}\"")
            extras = v.get("additional_sources") or []
            if extras:
                lines.append("")
                lines.append("**Fontes adicionais consultadas / Additional sources:**")
                for extra in extras:
                    url = extra.get("url", "")
                    title = extra.get("title", "")
                    quote = extra.get("quote", "")
                    title_part = f" — _{title}_" if title else ""
                    quote_part = f' — "{quote}"' if quote else ""
                    lines.append(f"  - [{url}]({url}){title_part}{quote_part}")
            if v.get("judgment"):
                lines.append("")
                lines.append(f"**Diagnóstico / Judgment:** {v['judgment']}")
            lines.append("")
    else:
        lines.append("## Alertas críticos / Critical alerts")
        lines.append("")
        lines.append("_Nenhum / None_")
        lines.append("")

    # ---- Full table
    lines.append("## Tabela completa / Full table")
    lines.append("")
    lines.append("| ID | Local / Location | Claim | Veredicto / Verdict | Fonte declarada / Declared source | URL | Evidência / Evidence |")
    lines.append("|---|---|---|---|---|---|---|")
    for v in verdicts:
        url_cell = "—"
        if v.get("consulted_url"):
            extra_count = len(v.get("additional_sources") or [])
            suffix = f" (+{extra_count})" if extra_count else ""
            url_cell = f"[link]({v['consulted_url']}){suffix}"
        row = [
            v.get("id", ""),
            v.get("location", ""),
            _md_escape(_truncate(v.get("claim", ""), 220)),
            label_for(v.get("verdict", "")),
            _md_escape(v.get("declared_source") or "—"),
            url_cell,
            _md_escape(_truncate(v.get("evidence_quote", "") or v.get("judgment", "") or "—", 180)),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # ---- Sources consulted (bibliography)
    lines.append("## Fontes consultadas / Sources consulted")
    lines.append("")
    if sources_index:
        lines.append(
            "_Bibliografia consolidada — toda URL acessada durante a auditoria, "
            "com os IDs das afirmações que se apoiaram nela. / "
            "Consolidated bibliography — every URL accessed during the audit, "
            "with the IDs of claims that relied on it._"
        )
        lines.append("")
        for i, s in enumerate(sources_index, start=1):
            title = " · ".join(s["titles"]) if s["titles"] else _short_url(s["url"])
            cited = ", ".join(sorted(set(s["cited_by"])))
            lines.append(f"**[{i}] {title}**")
            lines.append(f"  - URL: <{s['url']}>")
            lines.append(f"  - Citada por / Cited by: {cited}")
            for q in s["quotes"]:
                lines.append(f"  - Trecho / Excerpt: \"{q}\"")
            lines.append("")
    else:
        lines.append(
            "_Nenhuma URL externa foi consultada (modo offline ou nenhuma afirmação verificável). "
            "/ No external URL was consulted (offline mode or no verifiable claims)._"
        )
        lines.append("")

    # ---- Methodology
    lines.append("## Metodologia / Methodology")
    lines.append("")
    methodology = payload.get("methodology")
    if methodology:
        lines.append(methodology)
    else:
        lines.append(
            "- Fontes declaradas foram acessadas e comparadas com o claim quanto a valor, recorte temporal, geografia e metodologia. "
            "Quando ausentes, foi feita busca web para sugestão de fonte plausível, sem promover o veredicto a Confirmado. "
            "Quotes diretos limitam-se a 15 palavras."
        )
        lines.append("")
        lines.append(
            "- Declared sources were fetched and compared against the claim for value, time period, geography, and methodology. "
            "Where absent, a web search was used to suggest a plausible source without promoting the verdict to Confirmed. "
            "Direct quotes are kept under 15 words."
        )
    lines.append("")
    if payload.get("limitations"):
        lines.append(f"**Limitações / Limitations:** {payload['limitations']}")
        lines.append("")

    return "\n".join(lines)


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def _short_url(url: str) -> str:
    """Return a compact, human-readable label for a URL when no title is available."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        if path and len(path) < 60:
            return f"{host}{path}"
        return host or url
    except Exception:
        return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Render fact-check report from verdicts.json")
    parser.add_argument("verdicts", help="Path to verdicts.json")
    parser.add_argument("--out", default="report", help="Output basename (writes <basename>.md and <basename>.json)")
    args = parser.parse_args()

    payload = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    md = render_markdown(payload)

    out = Path(args.out)
    if out.is_dir() or args.out.endswith("/"):
        out.mkdir(parents=True, exist_ok=True)
        md_path = out / "report.md"
        json_path = out / "report.json"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        md_path = out.with_suffix(".md")
        json_path = out.with_suffix(".json")

    md_path.write_text(md, encoding="utf-8")
    # Pass-through JSON; preserves the model's structured output for pipelines
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {md_path}", file=sys.stderr)
    print(f"Wrote: {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
