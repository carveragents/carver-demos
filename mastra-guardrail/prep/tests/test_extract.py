"""Tests for `mastra_prep.extract` (spec §2 "Extraction").

`extract_record` resolves every `FIELD_MAP` dotted path against a raw annotation
record via a null-safe dotted-path get: missing nested paths yield `None`, never
`KeyError`. A missing/empty top-level `id` makes the whole record unrecoverable
and `extract_record` returns `None`.

The fixture (`tests/fixtures/sample_record.json`) is a trimmed copy of the real
live sample record the spec itself was authored against
(`../carver-showcase/data/annotations.jsonl` line 1) — read-only reference data,
never written back, never imported as code (goal #13).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mastra_prep.extract import FIELD_MAP, extract_record

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_record.json"


@pytest.fixture
def sample_record() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# Keys the sample record legitimately carries as `null` (jurisdiction fields not
# applicable to a national-scope regulator) -- excluded from the "resolved to a
# real value" check below so that check cannot pass vacuously on an
# implementation that resolves nothing.
_LEGITIMATELY_NULL_KEYS = frozenset({"jurisdiction_bloc", "jurisdiction_locality", "jurisdiction_region"})


def test_every_field_map_path_resolves(sample_record):
    extracted = extract_record(sample_record)

    assert extracted is not None
    assert set(extracted) == set(FIELD_MAP.values())
    for output_key in FIELD_MAP.values():
        if output_key in _LEGITIMATELY_NULL_KEYS:
            continue
        assert extracted[output_key] is not None, f"{output_key!r} failed to resolve"


def test_field_map_values_match_real_record(sample_record):
    extracted = extract_record(sample_record)

    assert extracted["artifact_id"] == "805eda1c-3022-45fe-9914-1c09da16bae0"
    assert extracted["topic_id"] == "26ca193a-10e3-4f43-970d-93a7fa8529f0"
    assert extracted["source_id"] == "a5ab2024-a838-4b46-90d9-a4cef320f7d4"
    assert extracted["impact_label"] == "high"
    assert extracted["impact_score"] == 9
    assert extracted["impact_confidence"] == 0.9
    assert extracted["update_type"] == "bulletin"
    assert extracted["update_subtype"] == "regulatory_body"
    assert extracted["regulator_name"] == "Malta Financial Services Authority"
    assert extracted["regulator_division"] == "Banking Supervision Office"
    assert extracted["jurisdiction_scope"] == "national"
    assert extracted["jurisdiction_country"] == "MT"
    assert extracted["jurisdiction_bloc"] is None
    assert extracted["jurisdiction_locality"] is None
    assert extracted["jurisdiction_region"] is None
    assert extracted["title"].startswith("Dear Chief Executive Officer")
    assert extracted["base_url"] == "mfsa.mt"
    assert extracted["summary"] == (
        "MFSA reviews supervisory reporting adequacy for Less Significant Institutions"
    )
    assert extracted["objective"].startswith("To assess and ensure the adequacy")
    assert extracted["what_changed"].startswith("The MFSA conducted a targeted review")
    assert extracted["why_it_matters"].startswith("Accurate and timely supervisory reporting")
    assert isinstance(extracted["key_requirements"], list) and len(extracted["key_requirements"]) == 5
    assert extracted["effective_date"] == ""
    assert extracted["compliance_date"] == ""
    assert isinstance(extracted["reg_rules"], list) and len(extracted["reg_rules"]) == 2
    assert isinstance(extracted["reg_statutes"], list) and len(extracted["reg_statutes"]) == 3
    assert isinstance(extracted["reg_other_ref"], list) and len(extracted["reg_other_ref"]) == 1
    assert extracted["impacted_business"]["industry"] == ["Banking"]
    assert extracted["impacted_functions"] == [
        "Compliance", "Risk Management", "Operations", "Regulatory Reporting", "Legal",
    ]
    assert len(extracted["penalties_consequences"]) == 3
    assert extracted["reconciled_published_date"] == "2025-10-01"
    assert extracted["reconciled_pub_valid"] is True


def test_missing_nested_path_yields_none_not_keyerror(sample_record):
    del sample_record["output_data"]["classification"]["metadata"]["title"]

    extracted = extract_record(sample_record)

    assert extracted is not None
    assert extracted["title"] is None


def test_missing_intermediate_object_yields_none_for_all_its_paths(sample_record):
    del sample_record["output_data"]["metadata"]["critical_dates"]

    extracted = extract_record(sample_record)

    assert extracted is not None
    assert extracted["effective_date"] is None
    assert extracted["compliance_date"] is None


def test_missing_output_data_entirely_yields_none_for_all_nested_paths(sample_record):
    del sample_record["output_data"]

    extracted = extract_record(sample_record)

    assert extracted is not None  # top-level `id` is still present
    assert extracted["impact_label"] is None
    assert extracted["title"] is None
    assert extracted["reg_rules"] is None


def test_missing_id_returns_none(sample_record):
    del sample_record["id"]

    assert extract_record(sample_record) is None


def test_empty_id_returns_none(sample_record):
    sample_record["id"] = ""

    assert extract_record(sample_record) is None


def test_pure_no_mutation_of_input(sample_record):
    before = copy.deepcopy(sample_record)

    extract_record(sample_record)

    assert sample_record == before


def test_relevance_and_topic_taxonomy_never_extracted():
    """Goal's hard constraint ("never surface relevance or topic categories") is
    enforced at the extraction boundary — neither key appears in FIELD_MAP at all."""
    assert "relevance" not in FIELD_MAP
    assert not any(path.startswith("output_data.scores.relevance") for path in FIELD_MAP)
    assert not any("category" in path or "class_" in path for path in FIELD_MAP)
