"""Tests for load_normalized keep_columns allowlist (Task 2 — public bundle guard).

All tests use a small parquet fixture written to tmp_path.  The JSONL build path
is NOT exercised here — these tests verify the fast parquet-read path only, which
is the path taken by the public deployment (pre-built SLIM parquet).

The fixture intentionally includes a "title" content column to confirm that
keep_columns physically excludes it from the returned frame.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from carver_showcase.load import load_normalized


# ---------------------------------------------------------------------------
# Fixture factory
# ---------------------------------------------------------------------------

_FIXTURE_COLUMNS = ["topic_id", "impact_score", "title", "regulator_name"]


def _write_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    """Write a tiny parquet with content + aggregate columns to tmp_path."""
    df = pd.DataFrame(
        {
            "topic_id": pd.array(["t1", "t2", "t3"], dtype="string"),
            "impact_score": pd.array([8.0, 5.0, 3.0], dtype="Float64"),
            "title": pd.array(["Article A", "Article B", "Article C"], dtype="string"),
            "regulator_name": pd.array(["SEC", "FCA", "EMA"], dtype="string"),
        }
    )
    path = tmp_path / "fixture.parquet"
    df.to_parquet(path, engine="pyarrow", index=False)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKeepColumnsAllowlist:
    """Tests for the keep_columns parameter of load_normalized."""

    def test_keep_columns_returns_only_present_columns_in_order(self, tmp_path: pathlib.Path):
        """keep_columns returns the intersection in keep_columns order; missing col skipped."""
        parquet_path = _write_fixture(tmp_path)

        df = load_normalized(
            parquet_path=parquet_path,
            keep_columns=["topic_id", "impact_score", "title_NOPE_missing"],
        )

        # Only the present keep_columns survive, in the requested order
        assert list(df.columns) == ["topic_id", "impact_score"]
        assert df.shape[0] == 3

    def test_keep_columns_excludes_title_content_column(self, tmp_path: pathlib.Path):
        """A content column ("title") absent from keep_columns must not appear in output."""
        parquet_path = _write_fixture(tmp_path)

        df = load_normalized(
            parquet_path=parquet_path,
            keep_columns=["topic_id", "impact_score"],
        )

        assert "title" not in df.columns

    def test_keep_columns_none_returns_all_columns(self, tmp_path: pathlib.Path):
        """keep_columns=None (default) returns all columns unchanged."""
        parquet_path = _write_fixture(tmp_path)

        df = load_normalized(parquet_path=parquet_path, keep_columns=None)

        assert set(df.columns) == set(_FIXTURE_COLUMNS)
        assert df.shape[0] == 3

    def test_keep_columns_default_returns_all_columns(self, tmp_path: pathlib.Path):
        """Omitting keep_columns entirely behaves identically to keep_columns=None."""
        parquet_path = _write_fixture(tmp_path)

        df = load_normalized(parquet_path=parquet_path)

        assert set(df.columns) == set(_FIXTURE_COLUMNS)
        assert df.shape[0] == 3

    def test_keep_columns_missing_column_skipped_without_error(self, tmp_path: pathlib.Path):
        """A keep column not in the parquet is silently skipped (no KeyError)."""
        parquet_path = _write_fixture(tmp_path)

        # All three requested columns are absent from the fixture
        df = load_normalized(
            parquet_path=parquet_path,
            keep_columns=["nonexistent_col_a", "nonexistent_col_b"],
        )

        assert list(df.columns) == []
        assert df.shape[0] == 3

    def test_keep_columns_tuple_accepted(self, tmp_path: pathlib.Path):
        """keep_columns also accepts a tuple (not just a list)."""
        parquet_path = _write_fixture(tmp_path)

        df = load_normalized(
            parquet_path=parquet_path,
            keep_columns=("topic_id", "regulator_name"),
        )

        assert list(df.columns) == ["topic_id", "regulator_name"]

    def test_keep_columns_order_follows_keep_columns_not_parquet(self, tmp_path: pathlib.Path):
        """Returned column order follows keep_columns, not the parquet column order."""
        parquet_path = _write_fixture(tmp_path)

        # Reverse of fixture order: regulator_name comes before topic_id
        df = load_normalized(
            parquet_path=parquet_path,
            keep_columns=["regulator_name", "topic_id"],
        )

        assert list(df.columns) == ["regulator_name", "topic_id"]
