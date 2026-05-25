# pipeline/extract.py
from pathlib import Path

from pipeline.extractors.base import Extractor, Section
from pipeline.extractors.pymupdf_pdfplumber import PyMuPdfExtractor


def extract_sections(pdf_path: Path, extractor: Extractor | None = None) -> list[Section]:
    return (extractor or PyMuPdfExtractor()).extract(pdf_path)
