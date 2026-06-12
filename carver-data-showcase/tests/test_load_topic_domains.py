"""Tests for load_topic_domains() in carver_showcase/load.py.

TDD: tests written before implementation.

Coverage
--------
- happy_path: parses a valid temp CSV and returns expected columns/rows.
- absent_file: path does not exist → empty DataFrame, no exception.
- unknown_sub_domain: a sub_domain not in INSTITUTION_DOMAIN_PARENT is coerced
  to DOMAIN_FALLBACK_LEAF, and top_level is derived accordingly.
- top_level_rederived: top_level in the CSV is wrong (or blank); the loader
  re-derives it from INSTITUTION_DOMAIN_PARENT and ignores the CSV value.
- blank_topic_id_dropped: rows with blank/empty topic_id are dropped.
- secondary_passthrough: when the optional `secondary` column is present it is
  returned as-is (no coercion).
- no_secondary_column: CSV without a `secondary` column still works; the
  returned frame still has topic_id, sub_domain, top_level (no secondary).
"""
from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from carver_showcase.config import (
    DOMAIN_FALLBACK_LEAF,
    INSTITUTION_DOMAIN_PARENT,
    TOPIC_DOMAINS_CSV,
)
from carver_showcase.load import load_topic_domains


# ---------------------------------------------------------------------------
# Helper: write a small topic_domains.csv into a temp dir
# ---------------------------------------------------------------------------

_CORE_HEADER = ["topic_id", "sub_domain", "top_level", "secondary"]


def _write_domains_csv(
    path: pathlib.Path,
    rows: list[dict],
    fieldnames: list[str] | None = None,
) -> None:
    """Write rows to path (tab is fine; we use pandas to write)."""
    import csv
    headers = fieldnames or _CORE_HEADER
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# (a) happy path: parse a valid CSV
# ---------------------------------------------------------------------------

_VALID_LEAF = "Banking & Central Banking"
_VALID_TOP = INSTITUTION_DOMAIN_PARENT[_VALID_LEAF]  # "Finance"

_HAPPY_ROWS = [
    {
        "topic_id": "t1",
        "sub_domain": _VALID_LEAF,
        "top_level": _VALID_TOP,
        "secondary": "EU Banks",
    },
    {
        "topic_id": "t2",
        "sub_domain": "Securities & Capital Markets",
        "top_level": "Finance",
        "secondary": "",
    },
    {
        "topic_id": "t3",
        "sub_domain": "Data Protection & Privacy",
        "top_level": "Technology",
        "secondary": "GDPR",
    },
]


class TestLoadTopicDomainsHappyPath:
    """Happy path: small CSV with valid taxonomy rows."""

    @pytest.fixture()
    def result(self, tmp_path):
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, _HAPPY_ROWS)
        return load_topic_domains(p)

    def test_returns_dataframe(self, result):
        assert isinstance(result, pd.DataFrame)

    def test_row_count_matches_input(self, result):
        assert len(result) == 3

    def test_has_required_columns(self, result):
        assert {"topic_id", "sub_domain", "top_level"}.issubset(result.columns)

    def test_topic_ids_are_correct(self, result):
        assert list(result["topic_id"]) == ["t1", "t2", "t3"]

    def test_sub_domain_preserved_when_valid(self, result):
        assert result.loc[result["topic_id"] == "t1", "sub_domain"].iloc[0] == _VALID_LEAF

    def test_top_level_derived_from_taxonomy(self, result):
        """top_level must equal INSTITUTION_DOMAIN_PARENT[sub_domain] for all rows."""
        for _, row in result.iterrows():
            expected = INSTITUTION_DOMAIN_PARENT.get(row["sub_domain"], "")
            assert row["top_level"] == expected, (
                f"topic_id={row['topic_id']}: "
                f"expected top_level={expected!r}, got {row['top_level']!r}"
            )

    def test_secondary_column_passed_through(self, result):
        assert "secondary" in result.columns
        assert result.loc[result["topic_id"] == "t1", "secondary"].iloc[0] == "EU Banks"
        assert result.loc[result["topic_id"] == "t3", "secondary"].iloc[0] == "GDPR"


# ---------------------------------------------------------------------------
# (b) absent file → empty DataFrame, no exception
# ---------------------------------------------------------------------------

class TestLoadTopicDomainsAbsent:
    """Absent file → empty DataFrame, no exception."""

    def test_returns_empty_dataframe_when_file_absent(self, tmp_path):
        result = load_topic_domains(tmp_path / "topic_domains.csv")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_no_exception_when_file_absent(self, tmp_path):
        try:
            load_topic_domains(tmp_path / "topic_domains.csv")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"load_topic_domains raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# (c) unknown sub_domain → coerced to DOMAIN_FALLBACK_LEAF
# ---------------------------------------------------------------------------

class TestUnknownSubDomainCoerced:
    """An unknown sub_domain must be coerced to DOMAIN_FALLBACK_LEAF."""

    def test_unknown_sub_domain_becomes_fallback_leaf(self, tmp_path):
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "This leaf does not exist in taxonomy",
                "top_level": "Finance",  # wrong — will be overridden
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        assert result.loc[0, "sub_domain"] == DOMAIN_FALLBACK_LEAF

    def test_unknown_sub_domain_gets_correct_top_level(self, tmp_path):
        """After coercion, top_level must match INSTITUTION_DOMAIN_PARENT[DOMAIN_FALLBACK_LEAF]."""
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "Made up leaf",
                "top_level": "Anything Goes",
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        expected_top = INSTITUTION_DOMAIN_PARENT[DOMAIN_FALLBACK_LEAF]
        assert result.loc[0, "top_level"] == expected_top

    def test_empty_sub_domain_becomes_fallback_leaf(self, tmp_path):
        """A blank sub_domain (not in taxonomy) must also be coerced."""
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "",
                "top_level": "",
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        assert result.loc[0, "sub_domain"] == DOMAIN_FALLBACK_LEAF


# ---------------------------------------------------------------------------
# (d) top_level always re-derived from INSTITUTION_DOMAIN_PARENT
# ---------------------------------------------------------------------------

class TestTopLevelRederived:
    """top_level must always be re-derived; CSV value is ignored/overwritten."""

    def test_wrong_top_level_in_csv_is_overridden(self, tmp_path):
        """A valid sub_domain paired with an incorrect top_level in the CSV
        must be corrected by the loader."""
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "Banking & Central Banking",  # belongs to Finance
                "top_level": "Technology",  # WRONG
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        assert result.loc[0, "top_level"] == "Finance", (
            f"top_level should be 'Finance' (re-derived); got {result.loc[0, 'top_level']!r}"
        )

    def test_blank_top_level_in_csv_is_filled(self, tmp_path):
        """A valid sub_domain with a blank top_level in the CSV must be filled."""
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "Cybersecurity",  # belongs to Technology
                "top_level": "",  # blank
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        assert result.loc[0, "top_level"] == "Technology", (
            f"Expected 'Technology'; got {result.loc[0, 'top_level']!r}"
        )


# ---------------------------------------------------------------------------
# (e) blank topic_id rows are dropped
# ---------------------------------------------------------------------------

class TestBlankTopicIdDropped:
    """Rows with a blank or empty topic_id must be dropped."""

    def test_blank_topic_id_row_dropped(self, tmp_path):
        rows = [
            {
                "topic_id": "",
                "sub_domain": "Banking & Central Banking",
                "top_level": "Finance",
                "secondary": "",
            },
            {
                "topic_id": "t1",
                "sub_domain": "Banking & Central Banking",
                "top_level": "Finance",
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        assert len(result) == 1
        assert result.iloc[0]["topic_id"] == "t1"

    def test_all_blank_topic_ids_returns_empty_df(self, tmp_path):
        rows = [
            {
                "topic_id": "",
                "sub_domain": "Banking & Central Banking",
                "top_level": "Finance",
                "secondary": "",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows)
        result = load_topic_domains(p)
        assert result.empty


# ---------------------------------------------------------------------------
# (f) secondary column is optional — no secondary column in CSV is fine
# ---------------------------------------------------------------------------

class TestNoSecondaryColumn:
    """CSV without a secondary column must still load correctly."""

    def test_loads_without_secondary_column(self, tmp_path):
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "Banking & Central Banking",
                "top_level": "Finance",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows, fieldnames=["topic_id", "sub_domain", "top_level"])
        result = load_topic_domains(p)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert {"topic_id", "sub_domain", "top_level"}.issubset(result.columns)

    def test_secondary_column_absent_when_not_in_csv(self, tmp_path):
        """When CSV has no secondary column, result must not have it either."""
        rows = [
            {
                "topic_id": "t1",
                "sub_domain": "Insurance",
                "top_level": "Finance",
            },
        ]
        p = tmp_path / "topic_domains.csv"
        _write_domains_csv(p, rows, fieldnames=["topic_id", "sub_domain", "top_level"])
        result = load_topic_domains(p)
        assert "secondary" not in result.columns


# ---------------------------------------------------------------------------
# (g) default path constant wired correctly
# ---------------------------------------------------------------------------

class TestDefaultPath:
    """load_topic_domains() default path is TOPIC_DOMAINS_CSV from config."""

    def test_default_path_is_config_constant(self):
        """The function's default argument must equal the config constant.

        We do NOT test what happens when TOPIC_DOMAINS_CSV exists on disk
        (it may or may not in CI); we just verify the default is wired correctly
        by inspecting the function signature.
        """
        import inspect
        sig = inspect.signature(load_topic_domains)
        default = sig.parameters["path"].default
        assert default == TOPIC_DOMAINS_CSV
