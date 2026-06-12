"""Tests for load_term_stats() in carver_showcase/load.py.

TDD: tests written BEFORE implementation.

Coverage
--------
- present: all four artifacts exist → returns dict with correct keys/shapes.
- absent: empty tmp_path (no artifacts at all) → returns None, no exception.
- partial / core-absent boundary: only non-core artifacts present → returns None.
- isolation: tool-internal files (entity_types.csv, entity_mentions.csv,
  tag_mentions.csv) are NOT required — returns the dict when they are absent.

"Core absent" rule: if the breakdown CSV *or* the meta JSON is missing,
load_term_stats returns None.  Both must be present for a successful load.
The two leaderboard CSVs are treated as optional extras; if absent they
are returned as empty DataFrames.
"""
from __future__ import annotations

import json
import pathlib

import pandas as pd
import pytest

from carver_showcase.load import load_term_stats


# ---------------------------------------------------------------------------
# Helpers: write the four rollup artifacts into a tmp_path directory
# ---------------------------------------------------------------------------

_BREAKDOWN_ROWS = [
    {"type": "Regulator", "mentions": 120, "distinct_entities": 10},
    {"type": "Bank",      "mentions":  80, "distinct_entities":  6},
    {"type": "Law",       "mentions":  40, "distinct_entities":  4},
    {"type": "Other",     "mentions":  20, "distinct_entities":  3},
    {"type": "Person",    "mentions":  10, "distinct_entities":  2},
    {"type": "Location",  "mentions":   5, "distinct_entities":  1},
]

_ENTITY_LB_ROWS = [
    {"canonical_name": "Federal Reserve", "type": "Regulator", "mentions": 90},
    {"canonical_name": "JPMorgan Chase",  "type": "Bank",      "mentions": 55},
]

_TAG_LB_ROWS = [
    {"tag": "capital-requirements", "count": 200},
    {"tag": "stress-testing",       "count": 150},
    {"tag": "AML",                  "count":  80},
]

_META = {
    "n_distinct_entities": 26,
    "n_entity_mentions": 275,
    "n_distinct_tags": 3,
    "n_tag_mentions": 430,
    "model": "gpt-4o-mini",
    "enriched_at": "2026-06-09T12:00:00+00:00",
    "n_classified": 22,
}


def _write_artifacts(
    root: pathlib.Path,
    *,
    write_breakdown: bool = True,
    write_entity_lb: bool = True,
    write_tag_lb: bool = True,
    write_meta: bool = True,
) -> dict[str, pathlib.Path]:
    """Write rollup CSVs + meta JSON into *root*.  Returns a dict of paths."""
    paths: dict[str, pathlib.Path] = {}

    breakdown_path = root / "entity_type_breakdown.csv"
    entity_lb_path = root / "entity_leaderboard.csv"
    tag_lb_path = root / "tag_leaderboard.csv"
    meta_path = root / "term_stats_meta.json"

    if write_breakdown:
        pd.DataFrame(_BREAKDOWN_ROWS).to_csv(breakdown_path, index=False)
    if write_entity_lb:
        pd.DataFrame(_ENTITY_LB_ROWS).to_csv(entity_lb_path, index=False)
    if write_tag_lb:
        pd.DataFrame(_TAG_LB_ROWS).to_csv(tag_lb_path, index=False)
    if write_meta:
        meta_path.write_text(json.dumps(_META), encoding="utf-8")

    paths.update(
        breakdown=breakdown_path,
        entity_lb=entity_lb_path,
        tag_lb=tag_lb_path,
        meta=meta_path,
    )
    return paths


# ---------------------------------------------------------------------------
# Test: all four artifacts present
# ---------------------------------------------------------------------------

class TestLoadTermStatsPresent:
    """Happy-path: all four rollup artifacts exist."""

    @pytest.fixture()
    def result(self, tmp_path):
        paths = _write_artifacts(tmp_path)
        return load_term_stats(
            breakdown_path=paths["breakdown"],
            entity_leaderboard_path=paths["entity_lb"],
            tag_leaderboard_path=paths["tag_lb"],
            meta_path=paths["meta"],
        )

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_all_keys(self, result):
        assert set(result.keys()) == {"breakdown", "entity_leaderboard", "tag_leaderboard", "meta"}

    def test_breakdown_is_dataframe(self, result):
        assert isinstance(result["breakdown"], pd.DataFrame)

    def test_breakdown_columns(self, result):
        assert list(result["breakdown"].columns) == ["type", "mentions", "distinct_entities"]

    def test_breakdown_row_count(self, result):
        assert len(result["breakdown"]) == len(_BREAKDOWN_ROWS)

    def test_breakdown_values(self, result):
        top = result["breakdown"].iloc[0]
        assert top["type"] == "Regulator"
        assert top["mentions"] == 120

    def test_entity_leaderboard_is_dataframe(self, result):
        assert isinstance(result["entity_leaderboard"], pd.DataFrame)

    def test_entity_leaderboard_columns(self, result):
        assert list(result["entity_leaderboard"].columns) == ["canonical_name", "type", "mentions"]

    def test_entity_leaderboard_row_count(self, result):
        assert len(result["entity_leaderboard"]) == len(_ENTITY_LB_ROWS)

    def test_tag_leaderboard_is_dataframe(self, result):
        assert isinstance(result["tag_leaderboard"], pd.DataFrame)

    def test_tag_leaderboard_columns(self, result):
        assert list(result["tag_leaderboard"].columns) == ["tag", "count"]

    def test_tag_leaderboard_row_count(self, result):
        assert len(result["tag_leaderboard"]) == len(_TAG_LB_ROWS)

    def test_meta_is_dict(self, result):
        assert isinstance(result["meta"], dict)

    def test_meta_keys(self, result):
        expected_keys = {
            "n_distinct_entities", "n_entity_mentions", "n_distinct_tags",
            "n_tag_mentions", "model", "enriched_at", "n_classified",
        }
        assert set(result["meta"].keys()) == expected_keys

    def test_meta_values(self, result):
        assert result["meta"]["n_distinct_entities"] == 26
        assert result["meta"]["model"] == "gpt-4o-mini"
        assert result["meta"]["enriched_at"] == "2026-06-09T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Test: no artifacts (empty tmp_path) → None
# ---------------------------------------------------------------------------

class TestLoadTermStatsAbsent:
    """Graceful absent: no files at all → None, no exception."""

    def test_returns_none(self, tmp_path):
        result = load_term_stats(
            breakdown_path=tmp_path / "entity_type_breakdown.csv",
            entity_leaderboard_path=tmp_path / "entity_leaderboard.csv",
            tag_leaderboard_path=tmp_path / "tag_leaderboard.csv",
            meta_path=tmp_path / "term_stats_meta.json",
        )
        assert result is None

    def test_no_exception(self, tmp_path):
        """Must not raise even if all files are absent."""
        try:
            load_term_stats(
                breakdown_path=tmp_path / "entity_type_breakdown.csv",
                entity_leaderboard_path=tmp_path / "entity_leaderboard.csv",
                tag_leaderboard_path=tmp_path / "tag_leaderboard.csv",
                meta_path=tmp_path / "term_stats_meta.json",
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"load_term_stats raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Test: partial / core-absent boundary
# ---------------------------------------------------------------------------

class TestLoadTermStatsPartial:
    """Core-absent rule: missing breakdown OR meta → None."""

    def test_only_tag_leaderboard_present_returns_none(self, tmp_path):
        """Only the tag leaderboard is present — core is absent → None."""
        _write_artifacts(
            tmp_path,
            write_breakdown=False,
            write_entity_lb=False,
            write_tag_lb=True,
            write_meta=False,
        )
        result = load_term_stats(
            breakdown_path=tmp_path / "entity_type_breakdown.csv",
            entity_leaderboard_path=tmp_path / "entity_leaderboard.csv",
            tag_leaderboard_path=tmp_path / "tag_leaderboard.csv",
            meta_path=tmp_path / "term_stats_meta.json",
        )
        assert result is None

    def test_breakdown_missing_returns_none(self, tmp_path):
        """Breakdown absent but meta + leaderboards present → None."""
        _write_artifacts(tmp_path, write_breakdown=False)
        result = load_term_stats(
            breakdown_path=tmp_path / "entity_type_breakdown.csv",
            entity_leaderboard_path=tmp_path / "entity_leaderboard.csv",
            tag_leaderboard_path=tmp_path / "tag_leaderboard.csv",
            meta_path=tmp_path / "term_stats_meta.json",
        )
        assert result is None

    def test_meta_missing_returns_none(self, tmp_path):
        """Meta absent but breakdown + leaderboards present → None."""
        _write_artifacts(tmp_path, write_meta=False)
        result = load_term_stats(
            breakdown_path=tmp_path / "entity_type_breakdown.csv",
            entity_leaderboard_path=tmp_path / "entity_leaderboard.csv",
            tag_leaderboard_path=tmp_path / "tag_leaderboard.csv",
            meta_path=tmp_path / "term_stats_meta.json",
        )
        assert result is None

    def test_leaderboards_missing_still_returns_dict(self, tmp_path):
        """Core artifacts present but leaderboards absent → dict with empty DFs."""
        _write_artifacts(
            tmp_path,
            write_entity_lb=False,
            write_tag_lb=False,
        )
        result = load_term_stats(
            breakdown_path=tmp_path / "entity_type_breakdown.csv",
            entity_leaderboard_path=tmp_path / "entity_leaderboard.csv",
            tag_leaderboard_path=tmp_path / "tag_leaderboard.csv",
            meta_path=tmp_path / "term_stats_meta.json",
        )
        assert isinstance(result, dict)
        assert len(result["entity_leaderboard"]) == 0
        assert len(result["tag_leaderboard"]) == 0
        # breakdown and meta are still fully populated
        assert len(result["breakdown"]) == len(_BREAKDOWN_ROWS)
        assert isinstance(result["meta"], dict)


# ---------------------------------------------------------------------------
# Test: isolation — tool-internal files are NOT required
# ---------------------------------------------------------------------------

class TestLoadTermStatsIsolation:
    """load_term_stats must NOT read entity_types.csv / mention CSVs.

    Verify by: having all rollup artifacts present but no tool-internal files,
    and asserting the result is the full dict (not None, no exception).
    """

    def test_succeeds_without_internal_files(self, tmp_path):
        paths = _write_artifacts(tmp_path)

        # Explicitly confirm the tool-internal files do NOT exist
        assert not (tmp_path / "entity_types.csv").exists()
        assert not (tmp_path / "entity_mentions.csv").exists()
        assert not (tmp_path / "tag_mentions.csv").exists()

        result = load_term_stats(
            breakdown_path=paths["breakdown"],
            entity_leaderboard_path=paths["entity_lb"],
            tag_leaderboard_path=paths["tag_lb"],
            meta_path=paths["meta"],
        )
        assert isinstance(result, dict)
        assert result is not None

    def test_internal_files_do_not_affect_result(self, tmp_path):
        """Even if tool-internal files exist, the result is the same dict."""
        paths = _write_artifacts(tmp_path)

        # Write dummy internal files — should be completely ignored
        pd.DataFrame({"entity": ["X"], "count": [1]}).to_csv(
            tmp_path / "entity_mentions.csv", index=False
        )
        pd.DataFrame({"entity": ["X"], "type": ["Other"], "canonical_name": ["X"]}).to_csv(
            tmp_path / "entity_types.csv", index=False
        )
        pd.DataFrame({"tag": ["foo"], "count": [1]}).to_csv(
            tmp_path / "tag_mentions.csv", index=False
        )

        result = load_term_stats(
            breakdown_path=paths["breakdown"],
            entity_leaderboard_path=paths["entity_lb"],
            tag_leaderboard_path=paths["tag_lb"],
            meta_path=paths["meta"],
        )
        assert isinstance(result, dict)
        # The internal files must not pollute the leaderboard or breakdown
        assert len(result["breakdown"]) == len(_BREAKDOWN_ROWS)
        assert len(result["entity_leaderboard"]) == len(_ENTITY_LB_ROWS)


# ---------------------------------------------------------------------------
# Regression: "NA" / "null" tokens in rollup CSVs must survive as strings
# ---------------------------------------------------------------------------

class TestLoadTermStatsNaTokenRobustness:
    """Regression: a canonical_name or tag that is the literal string 'NA' (or
    'null', 'NaN') must be returned as the *string* 'NA', not as float NaN.

    pandas.read_csv silently converts those tokens to NaN by default.  The fix
    is keep_default_na=False in load_term_stats; these tests verify that fix.
    """

    def test_canonical_name_na_string_survives_as_string(self, tmp_path):
        """entity_leaderboard row with canonical_name='NA' is loaded as the string."""
        entity_lb_rows = [
            {"canonical_name": "NA", "type": "Regulator / Supervisor", "mentions": 42},
            {"canonical_name": "Federal Reserve", "type": "Regulator / Supervisor", "mentions": 90},
        ]
        breakdown_rows = [
            {"type": "Regulator / Supervisor", "mentions": 132, "distinct_entities": 2},
        ]
        meta = {
            "n_distinct_entities": 2, "n_entity_mentions": 132,
            "n_distinct_tags": 1, "n_tag_mentions": 10,
            "model": "gpt-4o-mini", "enriched_at": "2026-06-09T12:00:00+00:00",
            "n_classified": 2,
        }
        breakdown_path = tmp_path / "entity_type_breakdown.csv"
        entity_lb_path = tmp_path / "entity_leaderboard.csv"
        tag_lb_path = tmp_path / "tag_leaderboard.csv"
        meta_path = tmp_path / "term_stats_meta.json"

        pd.DataFrame(breakdown_rows).to_csv(breakdown_path, index=False)
        pd.DataFrame(entity_lb_rows).to_csv(entity_lb_path, index=False)
        pd.DataFrame([{"tag": "AML", "count": 10}]).to_csv(tag_lb_path, index=False)
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        result = load_term_stats(
            breakdown_path=breakdown_path,
            entity_leaderboard_path=entity_lb_path,
            tag_leaderboard_path=tag_lb_path,
            meta_path=meta_path,
        )
        assert result is not None
        lb = result["entity_leaderboard"]
        na_rows = lb[lb["canonical_name"] == "NA"]
        assert len(na_rows) == 1, (
            f"Expected 'NA' canonical_name to survive as string, got: {lb['canonical_name'].tolist()}"
        )
        # Must be the Python string 'NA', not a float NaN
        assert isinstance(na_rows.iloc[0]["canonical_name"], str)
        assert na_rows.iloc[0]["mentions"] == 42

    def test_tag_na_string_survives_as_string(self, tmp_path):
        """tag_leaderboard row with tag='NA' is loaded as the string, not NaN."""
        tag_lb_rows = [
            {"tag": "NA", "count": 15},
            {"tag": "null", "count": 8},
            {"tag": "AML", "count": 100},
        ]
        breakdown_rows = [{"type": "Other", "mentions": 10, "distinct_entities": 1}]
        meta = {
            "n_distinct_entities": 1, "n_entity_mentions": 10,
            "n_distinct_tags": 3, "n_tag_mentions": 123,
            "model": "gpt-4o-mini", "enriched_at": "2026-06-09T12:00:00+00:00",
            "n_classified": 1,
        }
        breakdown_path = tmp_path / "entity_type_breakdown.csv"
        entity_lb_path = tmp_path / "entity_leaderboard.csv"
        tag_lb_path = tmp_path / "tag_leaderboard.csv"
        meta_path = tmp_path / "term_stats_meta.json"

        pd.DataFrame(breakdown_rows).to_csv(breakdown_path, index=False)
        pd.DataFrame([{"canonical_name": "X", "type": "Other", "mentions": 10}]).to_csv(
            entity_lb_path, index=False
        )
        pd.DataFrame(tag_lb_rows).to_csv(tag_lb_path, index=False)
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        result = load_term_stats(
            breakdown_path=breakdown_path,
            entity_leaderboard_path=entity_lb_path,
            tag_leaderboard_path=tag_lb_path,
            meta_path=meta_path,
        )
        assert result is not None
        tlb = result["tag_leaderboard"]
        na_rows = tlb[tlb["tag"] == "NA"]
        assert len(na_rows) == 1, (
            f"Expected 'NA' tag to survive as string, got: {tlb['tag'].tolist()}"
        )
        assert isinstance(na_rows.iloc[0]["tag"], str)
        assert na_rows.iloc[0]["count"] == 15

        null_rows = tlb[tlb["tag"] == "null"]
        assert len(null_rows) == 1
        assert isinstance(null_rows.iloc[0]["tag"], str)

    def test_numeric_columns_are_int_not_string(self, tmp_path):
        """After keep_default_na=False, numeric columns must still be int (not str)."""
        breakdown_path = tmp_path / "entity_type_breakdown.csv"
        entity_lb_path = tmp_path / "entity_leaderboard.csv"
        tag_lb_path = tmp_path / "tag_leaderboard.csv"
        meta_path = tmp_path / "term_stats_meta.json"

        pd.DataFrame([{"type": "Regulator", "mentions": 50, "distinct_entities": 3}]).to_csv(
            breakdown_path, index=False
        )
        pd.DataFrame([{"canonical_name": "FCA", "type": "Regulator", "mentions": 50}]).to_csv(
            entity_lb_path, index=False
        )
        pd.DataFrame([{"tag": "AML", "count": 100}]).to_csv(tag_lb_path, index=False)
        meta = {
            "n_distinct_entities": 1, "n_entity_mentions": 50,
            "n_distinct_tags": 1, "n_tag_mentions": 100,
            "model": "gpt-4o-mini", "enriched_at": "2026-06-09T12:00:00+00:00",
            "n_classified": 1,
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        result = load_term_stats(
            breakdown_path=breakdown_path,
            entity_leaderboard_path=entity_lb_path,
            tag_leaderboard_path=tag_lb_path,
            meta_path=meta_path,
        )
        assert result is not None
        bd = result["breakdown"]
        assert bd["mentions"].dtype == int or bd["mentions"].dtype.kind == "i", (
            f"breakdown.mentions should be int, got {bd['mentions'].dtype}"
        )
        assert bd["distinct_entities"].dtype == int or bd["distinct_entities"].dtype.kind == "i"
        lb = result["entity_leaderboard"]
        assert lb["mentions"].dtype == int or lb["mentions"].dtype.kind == "i"
        tlb = result["tag_leaderboard"]
        assert tlb["count"].dtype == int or tlb["count"].dtype.kind == "i"
