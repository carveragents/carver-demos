"""Tests for apps/components/filters.py — apply_filters (pure, no Streamlit).

All tests are deterministic; no LLM, no network, no real data load.
apply_filters must NOT import streamlit — the import guard test enforces this.

Tests:
- test_apply_filters_empty_state_is_noop
- test_apply_filters_each_dimension_narrows_category
- test_apply_filters_each_dimension_narrows_country
- test_apply_filters_each_dimension_narrows_bloc
- test_apply_filters_each_dimension_narrows_scope
- test_apply_filters_each_dimension_narrows_regulator
- test_apply_filters_each_dimension_narrows_update_type
- test_apply_filters_is_conjunctive
- test_apply_filters_score_and_date_ranges
- test_apply_filters_min_richness
- test_build_record_index_and_get_raw_record
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Import the module under test (no streamlit side-effect)
# ---------------------------------------------------------------------------
from apps.components.filters import FilterState, apply_filters


# ---------------------------------------------------------------------------
# Helpers — build a minimal normalized DataFrame for filter tests
# ---------------------------------------------------------------------------

SAMPLE_DATE_1 = pd.Timestamp("2024-01-15", tz="UTC")
SAMPLE_DATE_2 = pd.Timestamp("2025-06-01", tz="UTC")
SAMPLE_DATE_3 = pd.Timestamp("2023-03-10", tz="UTC")


def _make_frame() -> pd.DataFrame:
    """Build a 5-row frame spanning all filter dimensions."""
    rows = [
        {
            "artifact_id": "art-001",
            "category": "Finance",
            "jurisdiction_country": "US",
            "jurisdiction_bloc": "G20",
            "jurisdiction_scope": "national",
            "regulator_name": "SEC",
            "update_type": "Regulatory Update",
            "impact_score": 8.0,
            "urgency_score": 6.0,
            "relevance_score": 7.0,
            "reconciled_published_date": SAMPLE_DATE_1,
            "richness_score": 75.0,
        },
        {
            "artifact_id": "art-002",
            "category": "Medical Devices",
            "jurisdiction_country": "DE",
            "jurisdiction_bloc": "EU",
            "jurisdiction_scope": "regional",
            "regulator_name": "BfArM",
            "update_type": "Guidance",
            "impact_score": 5.0,
            "urgency_score": 3.0,
            "relevance_score": 4.0,
            "reconciled_published_date": SAMPLE_DATE_2,
            "richness_score": 50.0,
        },
        {
            "artifact_id": "art-003",
            "category": "Data protection & cybersecurity",
            "jurisdiction_country": "GB",
            "jurisdiction_bloc": pd.NA,
            "jurisdiction_scope": "national",
            "regulator_name": "ICO",
            "update_type": "Enforcement Action",
            "impact_score": 9.5,
            "urgency_score": 9.0,
            "relevance_score": 8.5,
            "reconciled_published_date": SAMPLE_DATE_3,
            "richness_score": 90.0,
        },
        {
            "artifact_id": "art-004",
            "category": "Finance",
            "jurisdiction_country": "US",
            "jurisdiction_bloc": "G20",
            "jurisdiction_scope": "national",
            "regulator_name": "CFTC",
            "update_type": "Regulatory Update",
            "impact_score": 3.0,
            "urgency_score": 2.0,
            "relevance_score": 2.5,
            "reconciled_published_date": SAMPLE_DATE_1,
            "richness_score": 20.0,
        },
        {
            "artifact_id": "art-005",
            "category": "Medical Devices",
            "jurisdiction_country": pd.NA,
            "jurisdiction_bloc": "EU",
            "jurisdiction_scope": "supranational",
            "regulator_name": "EMA",
            "update_type": "Guidance",
            "impact_score": 6.0,
            "urgency_score": 5.0,
            "relevance_score": 5.5,
            "reconciled_published_date": pd.NaT,
            "richness_score": 60.0,
        },
    ]
    df = pd.DataFrame(rows)
    # Apply proper dtypes
    for col in ("impact_score", "urgency_score", "relevance_score", "richness_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Test: empty FilterState is a no-op
# ---------------------------------------------------------------------------


def test_apply_filters_empty_state_is_noop():
    """An all-default FilterState leaves the frame unchanged."""
    df = _make_frame()
    state = FilterState()
    result = apply_filters(df, state)
    assert len(result) == len(df), "empty state must return all rows"
    assert list(result.index) == list(df.index), "row order must be preserved"


# ---------------------------------------------------------------------------
# Tests: each multiselect dimension narrows correctly
# ---------------------------------------------------------------------------


def test_apply_filters_each_dimension_narrows_category():
    df = _make_frame()
    state = FilterState(category=["Finance"])
    result = apply_filters(df, state)
    assert set(result["category"].unique()) == {"Finance"}
    assert len(result) == 2


def test_apply_filters_each_dimension_narrows_country():
    df = _make_frame()
    state = FilterState(jurisdiction_country=["US"])
    result = apply_filters(df, state)
    assert all(result["jurisdiction_country"] == "US")
    assert len(result) == 2


def test_apply_filters_each_dimension_narrows_bloc():
    df = _make_frame()
    state = FilterState(jurisdiction_bloc=["EU"])
    result = apply_filters(df, state)
    assert all(result["jurisdiction_bloc"] == "EU")
    assert len(result) == 2


def test_apply_filters_each_dimension_narrows_scope():
    df = _make_frame()
    state = FilterState(jurisdiction_scope=["national"])
    result = apply_filters(df, state)
    assert all(result["jurisdiction_scope"] == "national")
    assert len(result) == 3


def test_apply_filters_each_dimension_narrows_regulator():
    df = _make_frame()
    state = FilterState(regulator_name=["ICO"])
    result = apply_filters(df, state)
    assert len(result) == 1
    assert result.iloc[0]["artifact_id"] == "art-003"


def test_apply_filters_each_dimension_narrows_update_type():
    df = _make_frame()
    state = FilterState(update_type=["Guidance"])
    result = apply_filters(df, state)
    assert len(result) == 2
    assert all(result["update_type"] == "Guidance")


# ---------------------------------------------------------------------------
# Test: conjunctive (AND) semantics
# ---------------------------------------------------------------------------


def test_apply_filters_is_conjunctive():
    """Two filters are ANDed: Finance AND US must return fewer rows than either alone."""
    df = _make_frame()
    state = FilterState(category=["Finance"], jurisdiction_country=["US"])
    result = apply_filters(df, state)
    # Finance alone: 2 rows; US alone: 2 rows; Finance+US: 2 rows (art-001, art-004)
    assert len(result) == 2
    assert all(result["category"] == "Finance")
    assert all(result["jurisdiction_country"] == "US")

    # A filter that produces an empty intersection
    state2 = FilterState(category=["Medical Devices"], jurisdiction_country=["GB"])
    result2 = apply_filters(df, state2)
    assert len(result2) == 0, "Medical Devices + GB = no rows"


# ---------------------------------------------------------------------------
# Test: score and date range filters
# ---------------------------------------------------------------------------


def test_apply_filters_score_and_date_ranges():
    """Score range sliders narrow rows; an all-range slider is a no-op."""
    df = _make_frame()

    # Filter to high-impact rows only (>= 8.0)
    state = FilterState(impact_score_range=(8.0, 10.0))
    result = apply_filters(df, state)
    assert all(result["impact_score"] >= 8.0)
    assert len(result) == 2  # art-001 (8.0) and art-003 (9.5)

    # Urgency range that excludes only the top
    state2 = FilterState(urgency_score_range=(0.0, 5.5))
    result2 = apply_filters(df, state2)
    assert all(result2["urgency_score"] <= 5.5)

    # Date range: only rows with a plausible date between two bounds
    lo = pd.Timestamp("2024-01-01", tz="UTC")
    hi = pd.Timestamp("2024-12-31", tz="UTC")
    state3 = FilterState(date_range=(lo, hi))
    result3 = apply_filters(df, state3)
    # art-001 (2024-01-15) and art-004 (2024-01-15) are in range;
    # art-002 (2025-06-01) and art-003 (2023-03-10) are outside;
    # art-005 (NaT) is excluded (no date → excluded when range is set)
    assert all(
        (result3["reconciled_published_date"] >= lo)
        & (result3["reconciled_published_date"] <= hi)
    )
    assert len(result3) == 2


# ---------------------------------------------------------------------------
# Test: min_richness filter
# ---------------------------------------------------------------------------


def test_apply_filters_min_richness():
    """min_richness=0 is a no-op; min_richness=70 keeps only high-richness rows."""
    df = _make_frame()

    state = FilterState(min_richness=0)
    result = apply_filters(df, state)
    assert len(result) == len(df), "min_richness=0 should not filter anything"

    state2 = FilterState(min_richness=70)
    result2 = apply_filters(df, state2)
    assert all(result2["richness_score"] >= 70)
    assert len(result2) == 2  # art-001 (75), art-003 (90)

    state3 = FilterState(min_richness=91)
    result3 = apply_filters(df, state3)
    assert len(result3) == 0, "nothing exceeds richness_score 91"


# ---------------------------------------------------------------------------
# Test: build_record_index and get_raw_record on a tiny JSONL fixture
# ---------------------------------------------------------------------------


def test_build_record_index_and_get_raw_record(tmp_path: pathlib.Path):
    """Index maps artifact_id → byte offset; get_raw_record round-trips each record."""
    from carver_showcase.load import build_record_index, get_raw_record

    # Build a tiny JSONL with 3 records, varying sizes
    records = [
        {"id": "aaa-001", "topic_id": "t1", "output_data": {"entry_id": "e1", "value": "first record"}},
        {"id": "bbb-002", "topic_id": "t2", "output_data": {"entry_id": "e2", "value": "second"}},
        {"id": "ccc-003", "topic_id": "t3", "output_data": {"entry_id": "e3", "value": "third record with longer text here"}},
    ]
    jsonl_path = tmp_path / "tiny_index_test.jsonl"
    with jsonl_path.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")

    # Build the index
    idx = build_record_index(jsonl_path)

    # All three artifact_ids must be in the index
    assert set(idx.keys()) == {"aaa-001", "bbb-002", "ccc-003"}

    # Offsets must be distinct (different byte positions)
    assert len(set(idx.values())) == 3

    # Round-trip each record
    for rec in records:
        aid = rec["id"]
        retrieved = get_raw_record(aid, jsonl_path=jsonl_path, index=idx)
        assert retrieved is not None, f"record {aid} not found"
        assert retrieved["id"] == aid
        assert "output_data" in retrieved
        assert retrieved["output_data"]["entry_id"] == rec["output_data"]["entry_id"]

    # Unknown id returns None
    assert get_raw_record("does-not-exist", jsonl_path=jsonl_path, index=idx) is None


def test_get_raw_record_builds_index_if_not_supplied(tmp_path: pathlib.Path):
    """get_raw_record works even when no index is passed (builds it internally)."""
    from carver_showcase.load import get_raw_record

    records = [
        {"id": "x-001", "topic_id": "t1", "output_data": {"entry_id": "e1"}},
        {"id": "x-002", "topic_id": "t2", "output_data": {"entry_id": "e2"}},
    ]
    jsonl_path = tmp_path / "tiny_no_idx.jsonl"
    with jsonl_path.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")

    r = get_raw_record("x-002", jsonl_path=jsonl_path)
    assert r is not None
    assert r["id"] == "x-002"


def test_apply_filters_no_streamlit_import():
    """filters.py must not import streamlit at module level (apply_filters is pure).

    Order-independent: inspect the module source's top-level imports rather than
    sys.modules (which other tests in the session may have populated). The
    deferred ``import streamlit`` inside ``sidebar_filters`` is allowed.
    """
    import ast
    import pathlib

    src = pathlib.Path("apps/components/filters.py").read_text()
    tree = ast.parse(src)
    for node in tree.body:  # module-level statements only
        if isinstance(node, ast.Import):
            assert all(a.name != "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "streamlit"
