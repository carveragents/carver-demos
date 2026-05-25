# pipeline/extractors/pymupdf_pdfplumber.py
import re
from pathlib import Path

import fitz  # pymupdf

from pipeline.extractors.base import Section


HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+|\d+\.)\s+(.+)$")


def _clean_extracted_text(text: str) -> str:
    """Remove null bytes and other C0 control chars (keep \\n, \\t, \\r)."""
    keep = {"\n", "\t", "\r"}
    return "".join(ch for ch in text if ch in keep or ord(ch) >= 0x20)

# Patterns for running page chrome that appears in Mastercard SPME PDFs
_COPYRIGHT_RE = re.compile(r"^©\s*\d{4}[–\-]\d{4}\s+Mastercard.*", re.IGNORECASE)
_BARE_PAGE_NUM_RE = re.compile(r"^\d{1,4}$")
_BARE_DATE_RE = re.compile(r"^\d{1,2}\s+\w+\s+\d{4}$")


def _strip_page_chrome(text: str) -> str:
    """Remove running page headers/footers from extracted PDF text.

    Strips copyright lines, bare page numbers, and bare publication dates
    that Mastercard SPME PDFs repeat on every page.
    """
    filtered: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _COPYRIGHT_RE.match(stripped):
            continue
        if _BARE_PAGE_NUM_RE.match(stripped):
            continue
        if _BARE_DATE_RE.match(stripped):
            continue
        filtered.append(line)

    # Collapse runs of blank lines introduced by the removals into a single blank
    result_lines: list[str] = []
    prev_blank = False
    for line in filtered:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank

    return "\n".join(result_lines)


# Lines that look like TOC entries: "11.2 MATCH Standards ........ 47" — skip
# so we record the first BODY occurrence, not the TOC.
_TOC_LINE_RE = re.compile(r"\.{2,}\s*\d+\s*$")


def extract_section_pages(pdf_path: Path) -> dict[str, int]:
    """Map `section_id -> first body-page number (1-indexed)` for one PDF.

    Iterates pages individually, applies the same chrome stripping as the
    section extractor, and skips lines that look like TOC entries (dot-leader
    followed by a page number) so we record the first body occurrence.
    """
    doc = fitz.open(pdf_path)
    out: dict[str, int] = {}
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            raw_text = page.get_text()
            text = _strip_page_chrome(_clean_extracted_text(raw_text))
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or _TOC_LINE_RE.search(stripped):
                    continue
                m = HEADING_RE.match(stripped)
                if m and len(m.group(1).split(".")) <= 3:
                    section_id = m.group(1).rstrip(".")
                    out.setdefault(section_id, page_num + 1)
    finally:
        doc.close()
    return out


class PyMuPdfExtractor:
    """Default extractor — pymupdf for body text, pdfplumber for tables (later)."""

    def extract(self, pdf_path: Path) -> list[Section]:
        doc = fitz.open(pdf_path)
        raw_text = "\n".join(page.get_text() for page in doc)
        text = _strip_page_chrome(_clean_extracted_text(raw_text))
        return _split_sections(text)


def _split_sections(text: str) -> list[Section]:
    lines = text.splitlines()
    sections: list[Section] = []
    current_id: str | None = None
    current_title: str | None = None
    current_body: list[str] = []
    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m and len(m.group(1).split(".")) <= 3:
            if current_id is not None:
                sections.append(Section(current_id, current_title or "", "\n".join(current_body).strip()))
            current_id = m.group(1).rstrip(".")
            current_title = m.group(2).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_id is not None:
        sections.append(Section(current_id, current_title or "", "\n".join(current_body).strip()))
    return sections
