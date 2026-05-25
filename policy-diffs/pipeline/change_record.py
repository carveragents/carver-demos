# pipeline/change_record.py
import dataclasses
import json
from pathlib import Path
from typing import Literal


@dataclasses.dataclass(frozen=True)
class AffectedFile:
    path: str
    old_contents: str
    new_contents: str
    change_summary: str


@dataclasses.dataclass(frozen=True)
class ChangeRecord:
    change_id: str
    transition_from: str
    transition_to: str
    section_id: str
    section_title: str
    materiality: Literal["cosmetic", "clarifying", "substantive", "breaking"]
    summary: str
    section_before: str
    section_after: str
    affected_files: list[AffectedFile]
    rationale: str


def save_change_record(rec: ChangeRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataclasses.asdict(rec), indent=2))


def load_change_record(path: Path) -> ChangeRecord:
    raw = json.loads(path.read_text())
    raw["affected_files"] = [AffectedFile(**f) for f in raw["affected_files"]]
    return ChangeRecord(**raw)
