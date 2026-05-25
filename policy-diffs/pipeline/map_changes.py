# pipeline/map_changes.py
import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.classify import ClassificationRecord
from pipeline.llm import LLMClient


PROMPT = (Path(__file__).parent.parent / "prompts" / "map.txt").read_text()

SCHEMA = {
    "type": "object",
    "properties": {
        "section_id": {"type": "string"},
        "affected_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "policy": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["policy", "rationale"],
                "additionalProperties": False,
            },
        },
        "rationale": {"type": "string"},
    },
    "required": ["section_id", "affected_policies", "rationale"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class PolicyCatalogEntry:
    name: str
    description: str
    cited_sections: list[str]


@dataclass(frozen=True)
class AffectedPolicy:
    policy: str
    rationale: str


@dataclass(frozen=True)
class MappingRecord:
    section_id: str
    affected_policies: list[AffectedPolicy]
    rationale: str | None = None


def map_delta(
    classification: ClassificationRecord,
    *,
    before: str,
    after: str,
    catalog: list[PolicyCatalogEntry],
    llm: LLMClient,
) -> MappingRecord:
    user = (
        "Acme Pay policy catalog:\n"
        + json.dumps([c.__dict__ for c in catalog], indent=2)
        + "\n\nMastercard SPME diff:\n"
        f"section_id: {classification.section_id}\n"
        f"title: {classification.title}\n"
        f"materiality: {classification.materiality}\n"
        f"summary: {classification.summary}\n\n"
        f"--- BEFORE ---\n{before}\n\n"
        f"--- AFTER ---\n{after}\n"
    )
    out = llm.complete_json(stage="map", system=PROMPT, user=user, json_schema=SCHEMA)
    return MappingRecord(
        section_id=out["section_id"],
        affected_policies=[AffectedPolicy(**p) for p in out["affected_policies"]],
        rationale=out.get("rationale"),
    )
