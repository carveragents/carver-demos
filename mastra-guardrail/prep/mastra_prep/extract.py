"""Extraction of Carver annotation records into a flat, project-local shape.

`FIELD_MAP` is this project's OWN hand-derived copy of the nested `output_data`
paths it needs — never `import carver_showcase` (different repo, different venv,
goal #13; `test_imports.py::test_never_imports_carver_showcase` enforces this
mechanically). Paths are confirmed against a live sample record
(`../carver-showcase/data/annotations.jsonl` line 1, probed 2026-07-16; spec §2).

`relevance` (deprecated) and topic-catalog taxonomy (`category`/`class_*`) are
deliberately absent from `FIELD_MAP` — the goal's hard constraint against
surfacing either is enforced HERE, at the extraction boundary, so it is
structurally impossible for them to leak into `data/cleared/` downstream.
"""
from __future__ import annotations

# Dotted source path (within a raw annotation record) -> flat output key.
FIELD_MAP: dict[str, str] = {
    "id": "artifact_id",
    "topic_id": "topic_id",
    "source_id": "source_id",
    "output_data.scores.impact.label": "impact_label",
    "output_data.scores.impact.score": "impact_score",
    "output_data.scores.impact.confidence": "impact_confidence",
    "output_data.classification.update_type": "update_type",
    "output_data.classification.update_subtype": "update_subtype",
    "output_data.classification.regulatory_source.name": "regulator_name",
    "output_data.classification.regulatory_source.division_office": "regulator_division",
    "output_data.classification.jurisdiction.scope": "jurisdiction_scope",
    "output_data.classification.jurisdiction.country": "jurisdiction_country",
    "output_data.classification.jurisdiction.bloc": "jurisdiction_bloc",
    "output_data.classification.jurisdiction.locality": "jurisdiction_locality",
    "output_data.classification.jurisdiction.region_name": "jurisdiction_region",
    "output_data.classification.metadata.title": "title",
    "output_data.classification.metadata.base_url": "base_url",
    "output_data.classification.metadata.summary": "summary",
    "output_data.metadata.impact_summary.objective": "objective",
    "output_data.metadata.impact_summary.what_changed": "what_changed",
    "output_data.metadata.impact_summary.why_it_matters": "why_it_matters",
    "output_data.metadata.impact_summary.key_requirements": "key_requirements",
    "output_data.metadata.critical_dates.effective_date": "effective_date",
    "output_data.metadata.critical_dates.compliance_date": "compliance_date",
    "output_data.metadata.reg_references.rules": "reg_rules",
    "output_data.metadata.reg_references.statutes": "reg_statutes",
    "output_data.metadata.reg_references.other_ref": "reg_other_ref",
    "output_data.metadata.impacted_business": "impacted_business",
    "output_data.metadata.impacted_functions": "impacted_functions",
    "output_data.metadata.penalties_consequences": "penalties_consequences",
    "output_data.reconciled_published_date.date": "reconciled_published_date",
    "output_data.reconciled_published_date.valid": "reconciled_pub_valid",
}


def _get_dotted(raw: dict, dotted_path: str):
    """Null-safe dotted-path get: missing keys or non-dict intermediates yield
    `None` rather than raising."""
    current = raw
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def extract_record(raw: dict) -> dict | None:
    """Resolve every `FIELD_MAP` path via dotted-path get (missing -> None, never
    `KeyError`). Returns `None` if `id` (-> `artifact_id`) is missing or empty --
    an unrecoverable record. Pure; no I/O; never mutates `raw`.

    Note: list/dict-valued fields (`key_requirements`, `reg_rules`, `reg_statutes`,
    `reg_other_ref`, `impacted_business`, `impacted_functions`,
    `penalties_consequences`) are returned by reference, not deep-copied -- a
    caller that mutates one of those *in place* would mutate `raw`'s nested
    structure too. No caller in this package does; downstream consumers treat
    the extracted record as read-only.
    """
    extracted = {
        output_key: _get_dotted(raw, dotted_path)
        for dotted_path, output_key in FIELD_MAP.items()
    }
    if not extracted.get("artifact_id"):
        return None
    return extracted
