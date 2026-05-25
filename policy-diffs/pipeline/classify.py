# pipeline/classify.py
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pipeline.diff import SectionDelta
from pipeline.llm import LLMClient


PROMPT = (Path(__file__).parent.parent / "prompts" / "classify.txt").read_text()

SCHEMA = {
    "type": "object",
    "properties": {
        "section_id": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "materiality": {
            "type": "string",
            "enum": ["cosmetic", "clarifying", "substantive", "breaking"],
        },
    },
    "required": ["section_id", "title", "summary", "materiality"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ClassificationRecord:
    section_id: str
    title: str
    summary: str
    materiality: Literal["cosmetic", "clarifying", "substantive", "breaking"]


def classify_delta(delta: SectionDelta, *, llm: LLMClient) -> ClassificationRecord:
    user = (
        f"section_id: {delta.section_id}\n"
        f"title: {delta.title}\n"
        f"kind: {delta.kind}\n\n"
        f"--- BEFORE ---\n{delta.before}\n\n"
        f"--- AFTER ---\n{delta.after}\n"
    )
    out = llm.complete_json(stage="classify", system=PROMPT, user=user, json_schema=SCHEMA)
    return ClassificationRecord(**out)
