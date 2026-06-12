"""Tests for load_regulator_stats() in carver_showcase/load.py.

TDD: tests written BEFORE implementation.

Coverage
--------
- absent canonical CSV → None (graceful, no exception).
- happy path: canonical + context present → dict with three keys.
- missing context CSV: still returns dict (by_country sparser, no crash).
- return value structure: "leaderboard", "by_country", "meta" keys present.
"""
from __future__ import annotations

import json
import pathlib

import pandas as pd
import pytest

from carver_showcase.load import load_regulator_stats


# ---------------------------------------------------------------------------
# Helpers: write the two CSV artifacts into a tmp_path directory
# ---------------------------------------------------------------------------

_CANONICAL_ROWS = [
    {"regulator_name": "Federal Reserve", "canonical_regulator": "Federal Reserve System",
     "is_regulator": "True", "mentions": 100},
    {"regulator_name": "FCA",             "canonical_regulator": "Financial Conduct Authority",
     "is_regulator": "True", "mentions": 80},
    {"regulator_name": "Private Corp",    "canonical_regulator": "Private Corp",
     "is_regulator": "False", "mentions": 50},
]

_CONTEXT_ROWS = [
    {"regulator_name": "Federal Reserve", "countries": json.dumps(["US"])},
    {"regulator_name": "FCA",             "countries": json.dumps(["GB"])},
    {"regulator_name": "Private Corp",    "countries": json.dumps(["US"])},
]


def _write_canonical(root: pathlib.Path) -> pathlib.Path:
    p = root / "regulator_canonical.csv"
    pd.DataFrame(_CANONICAL_ROWS).to_csv(p, index=False)
    return p


def _write_context(root: pathlib.Path) -> pathlib.Path:
    p = root / "regulator_context.csv"
    pd.DataFrame(_CONTEXT_ROWS).to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# TestLoadRegulatorStatsAbsent — canonical CSV missing → None
# ---------------------------------------------------------------------------


class TestLoadRegulatorStatsAbsent:
    def test_returns_none_when_canonical_absent(self, tmp_path):
        result = load_regulator_stats(
            canonical_path=tmp_path / "regulator_canonical.csv",
            context_path=tmp_path / "regulator_context.csv",
        )
        assert result is None

    def test_no_exception_when_absent(self, tmp_path):
        try:
            load_regulator_stats(
                canonical_path=tmp_path / "regulator_canonical.csv",
                context_path=tmp_path / "regulator_context.csv",
            )
        except Exception as exc:
            pytest.fail(f"load_regulator_stats raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# TestLoadRegulatorStatsHappyPath — both CSVs present
# ---------------------------------------------------------------------------


_FIXTURE_MENTIONS = {
    "Federal Reserve": 100,
    "FCA": 80,
    "Private Corp": 50,
}


class TestLoadRegulatorStatsHappyPath:
    @pytest.fixture()
    def result(self, tmp_path):
        canonical_path = _write_canonical(tmp_path)
        context_path = _write_context(tmp_path)
        return load_regulator_stats(
            canonical_path=canonical_path,
            context_path=context_path,
            mentions_by_name=_FIXTURE_MENTIONS,
        )

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_three_keys(self, result):
        assert set(result.keys()) == {"leaderboard", "by_country", "meta"}

    def test_leaderboard_is_dataframe(self, result):
        assert isinstance(result["leaderboard"], pd.DataFrame)

    def test_by_country_is_dataframe(self, result):
        assert isinstance(result["by_country"], pd.DataFrame)

    def test_meta_is_dict(self, result):
        assert isinstance(result["meta"], dict)

    def test_leaderboard_has_regulators_only(self, result):
        """Private Corp (is_regulator=False) must not appear."""
        lb = result["leaderboard"]
        assert "Private Corp" not in lb["name"].values

    def test_leaderboard_fed_reserve_present(self, result):
        lb = result["leaderboard"]
        assert "Federal Reserve System" in lb["name"].values

    def test_meta_n_private_excluded(self, result):
        assert result["meta"]["n_private_excluded"] == 1

    def test_meta_n_raw_names(self, result):
        assert result["meta"]["n_raw_names"] == 3


# ---------------------------------------------------------------------------
# TestLoadRegulatorStatsContextMissing — context CSV absent → sparser by_country
# ---------------------------------------------------------------------------


class TestLoadRegulatorStatsContextMissing:
    @pytest.fixture()
    def result(self, tmp_path):
        canonical_path = _write_canonical(tmp_path)
        # context CSV intentionally not written
        return load_regulator_stats(
            canonical_path=canonical_path,
            context_path=tmp_path / "regulator_context.csv",
            mentions_by_name=_FIXTURE_MENTIONS,
        )

    def test_returns_dict_not_none(self, result):
        """Absent context must NOT make the whole function return None."""
        assert result is not None
        assert isinstance(result, dict)

    def test_has_three_keys(self, result):
        assert set(result.keys()) == {"leaderboard", "by_country", "meta"}

    def test_leaderboard_still_populated(self, result):
        """Even without context, leaderboard rows come from canonical_df."""
        lb = result["leaderboard"]
        assert len(lb) >= 1

    def test_no_exception(self, tmp_path):
        canonical_path = _write_canonical(tmp_path)
        try:
            load_regulator_stats(
                canonical_path=canonical_path,
                context_path=tmp_path / "regulator_context.csv",
                mentions_by_name=_FIXTURE_MENTIONS,
            )
        except Exception as exc:
            pytest.fail(f"load_regulator_stats raised with missing context: {exc}")


# ---------------------------------------------------------------------------
# TestLoadRegulatorStatsMentionsByNameThreadthrough — injection passthrough
# ---------------------------------------------------------------------------


class TestLoadRegulatorStatsMentionsByNameThreadthrough:
    """load_regulator_stats must thread mentions_by_name through to build_regulator_stats.

    These tests inject a small dict so no real parquet read is performed — fast.
    """

    def test_injected_mentions_reflected_in_meta(self, tmp_path):
        """When mentions_by_name is injected, meta must reflect curated counts."""
        canonical_path = _write_canonical(tmp_path)
        context_path = _write_context(tmp_path)

        # Curated dict: only "FCA" present with 10 mentions; Fed Reserve absent → excluded.
        curated = {"FCA": 10, "Private Corp": 5}

        result = load_regulator_stats(
            canonical_path=canonical_path,
            context_path=context_path,
            mentions_by_name=curated,
        )

        assert result is not None
        meta = result["meta"]
        # Only FCA (is_regulator=True, curated=10) + Private Corp (is_regulator=False, curated=5)
        # Federal Reserve (absent from curated) → excluded
        assert meta["n_raw_names"] == 2, f"Expected n_raw_names=2, got {meta['n_raw_names']}"
        assert meta["n_distinct_bodies"] == 1, (
            f"Expected n_distinct_bodies=1 (FCA only), got {meta['n_distinct_bodies']}"
        )
        assert meta["n_private_excluded"] == 1, (
            f"Expected n_private_excluded=1, got {meta['n_private_excluded']}"
        )

    def test_injected_mentions_leaderboard(self, tmp_path):
        """Leaderboard rows reflect injected mention counts, not stored column."""
        canonical_path = _write_canonical(tmp_path)
        context_path = _write_context(tmp_path)

        curated = {"Federal Reserve": 7, "FCA": 3}

        result = load_regulator_stats(
            canonical_path=canonical_path,
            context_path=context_path,
            mentions_by_name=curated,
        )

        lb = result["leaderboard"]
        fed_row = lb[lb["name"] == "Federal Reserve System"]
        assert len(fed_row) == 1
        assert fed_row.iloc[0]["mentions"] == 7

    def test_absent_canonical_still_returns_none(self, tmp_path):
        """canonical CSV missing → None even when mentions_by_name is provided."""
        result = load_regulator_stats(
            canonical_path=tmp_path / "regulator_canonical.csv",
            context_path=tmp_path / "regulator_context.csv",
            mentions_by_name={"Some Body": 5},
        )
        assert result is None
