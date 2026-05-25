# pipeline/extractors/base.py
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Section:
    section_id: str
    title: str
    markdown: str


class Extractor(Protocol):
    def extract(self, pdf_path: Path) -> list[Section]: ...
