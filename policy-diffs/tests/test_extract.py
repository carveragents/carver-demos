# tests/test_extract.py
from pathlib import Path

from pipeline.extract import extract_sections


FIXTURE = Path("tests/fixtures/tiny.pdf")


def test_extract_sections_splits_by_numbered_headings():
    sections = extract_sections(FIXTURE)

    assert len(sections) == 2
    assert sections[0].section_id == "1"
    assert sections[0].title == "Introduction"
    assert "intro section" in sections[0].markdown
    assert sections[1].section_id == "2"
    assert sections[1].title == "Fraud Monitoring"
    assert "fraud-to-sales" in sections[1].markdown


def test_clean_extracted_text_strips_null_bytes_and_control_chars():
    from pipeline.extractors.pymupdf_pdfplumber import _clean_extracted_text
    raw = "Mastercard \x00\x01\x02 SPME \x07§10.2"
    cleaned = _clean_extracted_text(raw)
    assert "\x00" not in cleaned
    assert "\x07" not in cleaned
    assert cleaned == "Mastercard  SPME §10.2"


def test_clean_extracted_text_preserves_newlines_and_tabs():
    from pipeline.extractors.pymupdf_pdfplumber import _clean_extracted_text
    raw = "line1\nline2\tindented"
    assert _clean_extracted_text(raw) == raw


def test_strip_page_chrome_removes_running_headers_and_bare_numbers():
    from pipeline.extractors.pymupdf_pdfplumber import _strip_page_chrome

    text = (
        "© 1991–2025 Mastercard. All rights reserved.\n"
        "11 February 2025\n"
        "42\n"
        "1.1 Real heading\n"
        "Body text.\n"
    )
    cleaned = _strip_page_chrome(text)
    assert "Mastercard" not in cleaned
    assert "11 February 2025" not in cleaned
    assert "\n42\n" not in "\n" + cleaned + "\n"  # bare 42 line gone
    assert "1.1 Real heading" in cleaned
    assert "Body text." in cleaned
