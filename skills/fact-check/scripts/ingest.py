#!/usr/bin/env python3
"""Ingest a document or URL and produce a normalized JSON with text blocks + locations.

Usage:
    python ingest.py <input> [--out OUTPUT_JSON]

Input can be:
    - .docx file
    - .pptx file
    - .pdf file (text or scanned; OCR fallback for scanned)
    - http(s):// URL

Output JSON shape:
    {
      "source": "<original input>",
      "kind": "docx" | "pptx" | "pdf" | "url",
      "language_guess": "pt" | "en" | ...,
      "blocks": [{"id": "...", "location": "...", "text": "..."}],
      "warnings": ["..."]
    }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"[warn] {msg}", file=sys.stderr)


def detect_kind(input_path: str) -> str:
    if input_path.startswith(("http://", "https://")):
        return "url"
    p = Path(input_path)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        return "docx"
    if suffix == ".pptx":
        return "pptx"
    if suffix == ".pdf":
        return "pdf"
    raise SystemExit(f"Unsupported input: {input_path} (suffix '{suffix}')")


def guess_language(text: str) -> str:
    """Lightweight language guess. PT vs EN heuristic — enough for routing."""
    sample = text.lower()[:5000]
    pt_markers = sum(sample.count(w) for w in (" o ", " a ", " os ", " as ", " que ", " não ", " com ", " para ", "ção", " é "))
    en_markers = sum(sample.count(w) for w in (" the ", " and ", " of ", " to ", " in ", " is ", " that ", " for "))
    if pt_markers > en_markers * 1.2:
        return "pt"
    if en_markers > pt_markers * 1.2:
        return "en"
    return "unknown"


def ingest_docx(path: Path) -> list[dict[str, Any]]:
    try:
        from docx import Document
    except ImportError:
        raise SystemExit("python-docx not installed. Run: pip install -r requirements.txt")
    doc = Document(str(path))
    blocks: list[dict[str, Any]] = []
    current_heading = ""
    for i, para in enumerate(doc.paragraphs, start=1):
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style else ""
        if "heading" in style:
            current_heading = text
        location = f"paragraph {i}"
        if current_heading and current_heading != text:
            location += f" (under '{current_heading[:60]}')"
        blocks.append({"id": f"p{i}", "location": location, "text": text})
    for ti, table in enumerate(doc.tables, start=1):
        rows_text: list[str] = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            rows_text.append(" | ".join(cells))
        if rows_text:
            blocks.append({
                "id": f"t{ti}",
                "location": f"table {ti}",
                "text": "\n".join(rows_text),
            })
    return blocks


def ingest_pptx(path: Path) -> list[dict[str, Any]]:
    try:
        from pptx import Presentation
    except ImportError:
        raise SystemExit("python-pptx not installed. Run: pip install -r requirements.txt")
    pres = Presentation(str(path))
    blocks: list[dict[str, Any]] = []
    for si, slide in enumerate(pres.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    txt = "".join(run.text for run in para.runs).strip()
                    if txt:
                        parts.append(txt)
            if hasattr(shape, "image"):
                parts.append("[image]")
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"[speaker notes] {notes}")
        if parts:
            blocks.append({
                "id": f"s{si}",
                "location": f"slide {si}",
                "text": "\n".join(parts),
            })
    return blocks


def ingest_pdf(path: Path) -> list[dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("pdfplumber not installed. Run: pip install -r requirements.txt")
    blocks: list[dict[str, Any]] = []
    needs_ocr_pages: list[int] = []
    with pdfplumber.open(str(path)) as pdf:
        for pi, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                needs_ocr_pages.append(pi)
                continue
            blocks.append({"id": f"p{pi}", "location": f"page {pi}", "text": text})
    if needs_ocr_pages:
        warn(f"Pages {needs_ocr_pages} have no extractable text; trying OCR.")
        ocr_blocks = ocr_pdf_pages(path, needs_ocr_pages)
        blocks.extend(ocr_blocks)
        blocks.sort(key=lambda b: int(re.sub(r"\D", "", b["id"]) or 0))
    return blocks


def ocr_pdf_pages(path: Path, page_numbers: list[int]) -> list[dict[str, Any]]:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        warn("OCR libs missing (pdf2image / pytesseract). Skipping OCR — pages remain empty.")
        return []
    try:
        # convert_from_path uses 1-based page numbers
        results: list[dict[str, Any]] = []
        for pn in page_numbers:
            try:
                images = convert_from_path(str(path), first_page=pn, last_page=pn, dpi=200)
            except Exception as e:
                warn(f"pdf2image failed for page {pn}: {e}. Tesseract binary may be missing.")
                continue
            for img in images:
                try:
                    text = pytesseract.image_to_string(img, lang="por+eng").strip()
                except pytesseract.TesseractNotFoundError:
                    warn("Tesseract binary not found. Install via 'brew install tesseract' or 'apt install tesseract-ocr'.")
                    return results
                if text:
                    results.append({"id": f"p{pn}", "location": f"page {pn} (OCR)", "text": text})
        return results
    except Exception as e:
        warn(f"OCR pipeline error: {e}")
        return []


def ingest_url(url: str) -> list[dict[str, Any]]:
    try:
        import urllib.request
        from html.parser import HTMLParser
    except ImportError:
        raise SystemExit("stdlib urllib/html unavailable, which should not happen.")

    class TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []
            self.skip = 0
            self.current_heading = ""
            self.sections: list[tuple[str, str]] = []
            self.buffer: list[str] = []

        def handle_starttag(self, tag: str, attrs: Any) -> None:
            if tag in ("script", "style", "noscript"):
                self.skip += 1
            if tag in ("h1", "h2", "h3"):
                self._flush()
            if tag == "p":
                self.parts.append(" ")

        def handle_endtag(self, tag: str) -> None:
            if tag in ("script", "style", "noscript") and self.skip > 0:
                self.skip -= 1
            if tag in ("h1", "h2", "h3"):
                heading_text = "".join(self.parts).strip()
                self.current_heading = heading_text
                self.parts.clear()

        def handle_data(self, data: str) -> None:
            if self.skip:
                return
            self.parts.append(data)

        def _flush(self) -> None:
            text = re.sub(r"\s+", " ", "".join(self.parts)).strip()
            if text:
                self.sections.append((self.current_heading or "body", text))
            self.parts.clear()

        def finalize(self) -> list[tuple[str, str]]:
            self._flush()
            return self.sections

    try:
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - user-supplied URL
            content_type = response.headers.get("Content-Type", "").lower()
            raw = response.read()
    except Exception as e:
        raise SystemExit(f"Failed to fetch URL: {e}")

    if "html" not in content_type and "xml" not in content_type:
        warn(f"Non-HTML content-type '{content_type}'; treating as plain text.")
        text = raw.decode("utf-8", errors="replace")
        return [{"id": "u1", "location": "body", "text": text[:50000]}]

    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("latin-1", errors="replace")

    parser = TextExtractor()
    parser.feed(html)
    sections = parser.finalize()
    blocks: list[dict[str, Any]] = []
    for i, (heading, text) in enumerate(sections, start=1):
        if len(text) < 30:
            continue
        blocks.append({"id": f"u{i}", "location": heading[:80] or "body", "text": text})
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest document/URL into normalized JSON.")
    parser.add_argument("input", help="Path to .docx/.pptx/.pdf or http(s):// URL")
    parser.add_argument("--out", default="-", help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    kind = detect_kind(args.input)
    if kind == "docx":
        blocks = ingest_docx(Path(args.input))
    elif kind == "pptx":
        blocks = ingest_pptx(Path(args.input))
    elif kind == "pdf":
        blocks = ingest_pdf(Path(args.input))
    elif kind == "url":
        blocks = ingest_url(args.input)
    else:
        raise SystemExit(f"Unknown kind: {kind}")

    if not blocks:
        warn("No blocks extracted. Document may be empty, image-only, or extraction failed.")

    full_text = "\n".join(b["text"] for b in blocks)
    language = guess_language(full_text)

    payload = {
        "source": args.input,
        "kind": kind,
        "language_guess": language,
        "blocks": blocks,
        "warnings": WARNINGS,
    }
    out_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(out_text)
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_text, encoding="utf-8")
        print(f"Wrote {len(blocks)} blocks to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
