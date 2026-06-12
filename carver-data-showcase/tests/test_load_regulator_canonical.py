"""Tests for load_regulator_canonical() in carver_showcase/load.py.

TDD: tests written before implementation.

Coverage
--------
- absent_file: path does not exist → returns None, no exception.
- happy_path: small temp CSV with mixed is_regulator rows → dict with correct
  canonical / is_regulator (bool) / key values.
- merge_key_collapse: punctuation/case/whitespace variants of the SAME body
  produce the same key (light normalization).
- merge_key_distinct: two bodies differing only by an institution-type noun
  get DISTINCT keys — regression guard for the over-merging bug.
- na_literal: a row whose regulator_name is the literal string "NA" survives (not
  turned into NaN) — appears as a key in the returned dict.
- bool_parsing: "True"/"False" strings → Python True/False bools; also covers
  all-caps "TRUE" and blank "" edge cases.
- empty_or_missing_columns: file exists but is empty or lacks required columns →
  returns None (defensive).
- blank_key_fallback: names that the light key reduces to "" (e.g. purely
  punctuation canonical) fall back to raw_name so key is never "".
- mentions_tolerant_cast: malformed mentions values (e.g. "250.0", "") do not
  raise; they are coerced to 0.
"""
from __future__ import annotations

import csv
import pathlib

import pandas as pd
import pytest

from carver_showcase.load import load_regulator_canonical


# ---------------------------------------------------------------------------
# Helper: write a small regulator_canonical.csv into a temp dir
# ---------------------------------------------------------------------------

_HEADER = ["regulator_name", "canonical_regulator", "is_regulator", "mentions"]


def _write_canonical_csv(
    path: pathlib.Path,
    rows: list[dict],
) -> None:
    """Write rows to path using csv.DictWriter (same as canonicalize_regulators.py)."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_HEADER)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Test: absent file → None
# ---------------------------------------------------------------------------

class TestLoadRegulatorCanonicalAbsent:
    """Absent file → None, no exception."""

    def test_returns_none_when_file_absent(self, tmp_path):
        result = load_regulator_canonical(path=tmp_path / "regulator_canonical.csv")
        assert result is None

    def test_no_exception_when_file_absent(self, tmp_path):
        try:
            load_regulator_canonical(path=tmp_path / "regulator_canonical.csv")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"load_regulator_canonical raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Test: happy path
# ---------------------------------------------------------------------------

_HAPPY_ROWS = [
    {
        "regulator_name": "Financial Conduct Authority",
        "canonical_regulator": "Financial Conduct Authority",
        "is_regulator": "True",
        "mentions": "250",
    },
    {
        "regulator_name": "FCA",
        "canonical_regulator": "Financial Conduct Authority",
        "is_regulator": "True",
        "mentions": "180",
    },
    {
        "regulator_name": "Reuters News Agency",
        "canonical_regulator": "Reuters",
        "is_regulator": "False",
        "mentions": "42",
    },
]


class TestLoadRegulatorCanonicalHappyPath:
    """Happy path: small CSV with a few rows."""

    @pytest.fixture()
    def result(self, tmp_path):
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, _HAPPY_ROWS)
        return load_regulator_canonical(path=p)

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_dict_has_all_raw_names(self, result):
        expected_keys = {r["regulator_name"] for r in _HAPPY_ROWS}
        assert set(result.keys()) == expected_keys

    def test_canonical_field_correct(self, result):
        assert result["FCA"]["canonical"] == "Financial Conduct Authority"
        assert result["Reuters News Agency"]["canonical"] == "Reuters"

    def test_is_regulator_true_parsed_as_bool(self, result):
        val = result["Financial Conduct Authority"]["is_regulator"]
        assert val is True
        assert isinstance(val, bool)

    def test_is_regulator_false_parsed_as_bool(self, result):
        val = result["Reuters News Agency"]["is_regulator"]
        assert val is False
        assert isinstance(val, bool)

    def test_key_is_lowercase_no_punctuation(self, result):
        """Key for 'Financial Conduct Authority' should be its light-normalised form."""
        key = result["Financial Conduct Authority"]["key"]
        assert key == "financial conduct authority", (
            f"Unexpected key: {key!r}"
        )

    def test_fca_and_authority_share_same_key(self, result):
        """Both 'Financial Conduct Authority' and 'FCA' map to the same canonical,
        so they should produce the same merge key."""
        assert result["Financial Conduct Authority"]["key"] == result["FCA"]["key"]


# ---------------------------------------------------------------------------
# Test: merge-key collapse (punctuation / case / whitespace variants)
# ---------------------------------------------------------------------------

class TestMergeKeyCollapse:
    """Punctuation/case/whitespace variants of the SAME body produce the same key."""

    def test_punctuation_variants_of_same_body_collapse(self, tmp_path):
        """'F.C.A.' vs 'FCA' in canonical both collapse to the same key (punctuation stripped)."""
        rows = [
            {
                "regulator_name": "F.C.A. raw",
                "canonical_regulator": "F.C.A.",
                "is_regulator": "True",
                "mentions": "5",
            },
            {
                "regulator_name": "FCA raw",
                "canonical_regulator": "FCA",
                "is_regulator": "True",
                "mentions": "15",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        assert result["F.C.A. raw"]["key"] == result["FCA raw"]["key"]

    def test_case_and_extra_whitespace_collapse(self, tmp_path):
        """'Bank of Spain', 'bank of  spain', and 'Bank of Spain.' all produce the same key."""
        rows = [
            {
                "regulator_name": "Bank of Spain",
                "canonical_regulator": "Bank of Spain",
                "is_regulator": "True",
                "mentions": "10",
            },
            {
                "regulator_name": "bank of  spain raw",
                "canonical_regulator": "bank of  spain",
                "is_regulator": "True",
                "mentions": "5",
            },
            {
                "regulator_name": "Bank of Spain. raw",
                "canonical_regulator": "Bank of Spain.",
                "is_regulator": "True",
                "mentions": "3",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        key_a = result["Bank of Spain"]["key"]
        key_b = result["bank of  spain raw"]["key"]
        key_c = result["Bank of Spain. raw"]["key"]
        assert key_a == key_b == key_c, (
            f"Case/whitespace/punctuation variants should collapse: "
            f"{key_a!r}, {key_b!r}, {key_c!r}"
        )


# ---------------------------------------------------------------------------
# Test: merge-key distinct (regression guard for the over-merging bug)
# ---------------------------------------------------------------------------

class TestMergeKeyDistinct:
    """Bodies differing only by an institution-type noun must get DISTINCT keys.

    This is the regression guard for the bug where quality.canonicalize_regulator
    (which strips nouns like commission/authority/agency) was used as the identity
    key, causing 'Financial Services Agency' and 'Financial Services Authority' to
    collapse into the same bucket and bias the regulator KPI downward.
    """

    def test_agency_vs_authority_distinct(self, tmp_path):
        """'Financial Services Agency' vs 'Financial Services Authority' → DISTINCT keys."""
        rows = [
            {
                "regulator_name": "FSA Japan",
                "canonical_regulator": "Financial Services Agency",
                "is_regulator": "True",
                "mentions": "50",
            },
            {
                "regulator_name": "FSA UK",
                "canonical_regulator": "Financial Services Authority",
                "is_regulator": "True",
                "mentions": "40",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        key_agency = result["FSA Japan"]["key"]
        key_authority = result["FSA UK"]["key"]
        assert key_agency != key_authority, (
            f"'Financial Services Agency' and 'Financial Services Authority' "
            f"must NOT share a key; both got {key_agency!r}"
        )

    def test_ministry_vs_department_of_finance_distinct(self, tmp_path):
        """'Ministry of Finance' vs 'Department of Finance' → DISTINCT keys."""
        rows = [
            {
                "regulator_name": "Ministry of Finance raw",
                "canonical_regulator": "Ministry of Finance",
                "is_regulator": "True",
                "mentions": "20",
            },
            {
                "regulator_name": "Department of Finance raw",
                "canonical_regulator": "Department of Finance",
                "is_regulator": "True",
                "mentions": "15",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        key_min = result["Ministry of Finance raw"]["key"]
        key_dep = result["Department of Finance raw"]["key"]
        assert key_min != key_dep, (
            f"'Ministry of Finance' and 'Department of Finance' "
            f"must NOT share a key; both got {key_min!r}"
        )

    def test_financial_services_commission_vs_authority_distinct(self, tmp_path):
        """'Financial Services Commission' vs 'Financial Services Authority' → DISTINCT keys."""
        rows = [
            {
                "regulator_name": "FSC Korea",
                "canonical_regulator": "Financial Services Commission",
                "is_regulator": "True",
                "mentions": "30",
            },
            {
                "regulator_name": "FSA UK2",
                "canonical_regulator": "Financial Services Authority",
                "is_regulator": "True",
                "mentions": "30",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        key_comm = result["FSC Korea"]["key"]
        key_auth = result["FSA UK2"]["key"]
        assert key_comm != key_auth, (
            f"Commission vs Authority bodies must NOT share a key; "
            f"comm={key_comm!r}, auth={key_auth!r}"
        )


# ---------------------------------------------------------------------------
# Test: "NA" literal survives
# ---------------------------------------------------------------------------

class TestNaLiteralSurvives:
    """A regulator_name of literally "NA" must not be converted to NaN."""

    def test_na_raw_name_is_in_result(self, tmp_path):
        rows = [
            {
                "regulator_name": "NA",
                "canonical_regulator": "North American Authority",
                "is_regulator": "True",
                "mentions": "3",
            },
            {
                "regulator_name": "FCA",
                "canonical_regulator": "Financial Conduct Authority",
                "is_regulator": "True",
                "mentions": "100",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        assert "NA" in result, (
            f"Literal 'NA' raw name must survive; got keys: {list(result.keys())}"
        )

    def test_na_raw_name_value_is_string_key(self, tmp_path):
        """The key "NA" in the result dict is the Python str 'NA', not NaN."""
        rows = [
            {
                "regulator_name": "NA",
                "canonical_regulator": "North American Authority",
                "is_regulator": "True",
                "mentions": "3",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        # The key must be the string "NA", not a float NaN
        na_key = next(k for k in result if str(k) == "NA")
        assert isinstance(na_key, str)
        assert result[na_key]["canonical"] == "North American Authority"


# ---------------------------------------------------------------------------
# Test: bool parsing variants
# ---------------------------------------------------------------------------

class TestBoolParsing:
    """"True"/"False" strings (and edge cases) map to Python bools."""

    def test_true_string_maps_to_true(self, tmp_path):
        rows = [
            {
                "regulator_name": "FCA",
                "canonical_regulator": "Financial Conduct Authority",
                "is_regulator": "True",
                "mentions": "10",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result["FCA"]["is_regulator"] is True

    def test_false_string_maps_to_false(self, tmp_path):
        rows = [
            {
                "regulator_name": "Reuters",
                "canonical_regulator": "Reuters",
                "is_regulator": "False",
                "mentions": "5",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result["Reuters"]["is_regulator"] is False

    def test_lowercase_true_maps_to_true(self, tmp_path):
        rows = [
            {
                "regulator_name": "EBA",
                "canonical_regulator": "European Banking Authority",
                "is_regulator": "true",
                "mentions": "20",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result["EBA"]["is_regulator"] is True

    def test_one_string_maps_to_true(self, tmp_path):
        rows = [
            {
                "regulator_name": "PRA",
                "canonical_regulator": "Prudential Regulation Authority",
                "is_regulator": "1",
                "mentions": "8",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result["PRA"]["is_regulator"] is True

    def test_is_regulator_result_is_python_bool(self, tmp_path):
        """Parsed is_regulator must be a Python bool, not a string or int."""
        rows = [
            {
                "regulator_name": "FCA",
                "canonical_regulator": "Financial Conduct Authority",
                "is_regulator": "True",
                "mentions": "10",
            },
            {
                "regulator_name": "Reuters",
                "canonical_regulator": "Reuters",
                "is_regulator": "False",
                "mentions": "5",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert isinstance(result["FCA"]["is_regulator"], bool)
        assert isinstance(result["Reuters"]["is_regulator"], bool)


# ---------------------------------------------------------------------------
# Test: empty / missing-columns → None
# ---------------------------------------------------------------------------

class TestEmptyOrMissingColumns:
    """Defensive: empty file or missing required columns → None."""

    def test_empty_file_returns_none(self, tmp_path):
        p = tmp_path / "regulator_canonical.csv"
        p.write_text("", encoding="utf-8")
        result = load_regulator_canonical(path=p)
        assert result is None

    def test_header_only_no_rows_returns_none(self, tmp_path):
        """A file with only the header row (zero data rows) should return None."""
        p = tmp_path / "regulator_canonical.csv"
        p.write_text(",".join(_HEADER) + "\n", encoding="utf-8")
        # An empty DataFrame after reading (0 rows) should return None.
        # Note: pd.read_csv returns a zero-row DataFrame in this case.
        # The function checks df.empty, which is True when there are 0 rows.
        result = load_regulator_canonical(path=p)
        assert result is None

    def test_missing_required_column_returns_none(self, tmp_path):
        """CSV missing 'is_regulator' column → None (required column absent)."""
        p = tmp_path / "regulator_canonical.csv"
        # Write with only two of the three required columns.
        with open(p, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["regulator_name", "canonical_regulator", "mentions"])
            writer.writeheader()
            writer.writerow({"regulator_name": "FCA", "canonical_regulator": "Financial Conduct Authority", "mentions": "10"})
        result = load_regulator_canonical(path=p)
        assert result is None


# ---------------------------------------------------------------------------
# Test: blank-key fallback
# ---------------------------------------------------------------------------

class TestBlankKeyFallback:
    """Names whose canonical AND raw light-key reduce to '' get key=raw_name.

    Under the light merge key, institution-type nouns (commission, authority, …)
    are NOT stripped — they remain in the key.  A truly blank key can only arise
    from a name composed entirely of punctuation/whitespace (e.g. "...").
    """

    def test_blank_canonical_falls_back_to_raw_name(self, tmp_path):
        """A row whose canonical is purely punctuation (reduces to '') gets key=raw_name."""
        rows = [
            {
                "regulator_name": "Some Regulator",
                "canonical_regulator": "...",   # purely punctuation → light key = ""
                "is_regulator": "True",
                "mentions": "5",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        rec = result["Some Regulator"]
        assert rec["key"] != "", "key must not be empty string"
        # Fallback: light key of raw_name "Some Regulator" = "some regulator"
        assert rec["key"] == "some regulator", (
            f"Expected 'some regulator' from raw name fallback, got {rec['key']!r}"
        )

    def test_commission_and_authority_get_distinct_keys(self, tmp_path):
        """'Commission' and 'Authority' produce DISTINCT keys under the light merge key.

        Unlike quality.canonicalize_regulator which strips these words to '',
        the light key preserves them, so 'Commission' → 'commission' and
        'Authority' → 'authority' — two distinct keys.
        """
        rows = [
            {
                "regulator_name": "Commission",
                "canonical_regulator": "Commission",
                "is_regulator": "True",
                "mentions": "5",
            },
            {
                "regulator_name": "Authority",
                "canonical_regulator": "Authority",
                "is_regulator": "True",
                "mentions": "3",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        key_commission = result["Commission"]["key"]
        key_authority = result["Authority"]["key"]
        assert key_commission != "", "Commission key must not be empty"
        assert key_authority != "", "Authority key must not be empty"
        assert key_commission != key_authority, (
            f"'Commission' and 'Authority' must have distinct keys: "
            f"{key_commission!r} == {key_authority!r}"
        )
        assert key_commission == "commission"
        assert key_authority == "authority"


# ---------------------------------------------------------------------------
# Test: additional bool-parsing edge cases (Fix 3)
# ---------------------------------------------------------------------------

class TestBoolParsingEdgeCases:
    """All-caps 'TRUE' → True; blank '' → False."""

    def test_all_caps_true_maps_to_true(self, tmp_path):
        """'TRUE' (all caps) must parse as True."""
        rows = [
            {
                "regulator_name": "SEC",
                "canonical_regulator": "Securities and Exchange Commission",
                "is_regulator": "TRUE",
                "mentions": "30",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        assert result["SEC"]["is_regulator"] is True

    def test_blank_is_regulator_maps_to_false(self, tmp_path):
        """Blank/empty '' is_regulator must parse as False (not truthy)."""
        rows = [
            {
                "regulator_name": "Unknown Entity",
                "canonical_regulator": "Unknown Entity",
                "is_regulator": "",
                "mentions": "1",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        result = load_regulator_canonical(path=p)
        assert result is not None
        assert result["Unknown Entity"]["is_regulator"] is False


# ---------------------------------------------------------------------------
# Test: tolerant mentions cast (Fix 1)
# ---------------------------------------------------------------------------

class TestMentionsTolerantCast:
    """Malformed mentions values must not raise; they coerce to 0."""

    def test_float_string_mentions_does_not_raise(self, tmp_path):
        """'250.0' in mentions column must not raise ValueError."""
        rows = [
            {
                "regulator_name": "FCA",
                "canonical_regulator": "Financial Conduct Authority",
                "is_regulator": "True",
                "mentions": "250.0",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        try:
            result = load_regulator_canonical(path=p)
        except ValueError as exc:
            pytest.fail(f"Float-string mentions raised ValueError: {exc}")
        assert result is not None

    def test_empty_string_mentions_does_not_raise(self, tmp_path):
        """'' in mentions column must not raise; coerces to 0."""
        rows = [
            {
                "regulator_name": "FCA",
                "canonical_regulator": "Financial Conduct Authority",
                "is_regulator": "True",
                "mentions": "",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        try:
            result = load_regulator_canonical(path=p)
        except ValueError as exc:
            pytest.fail(f"Empty mentions raised ValueError: {exc}")
        assert result is not None

    def test_word_mentions_does_not_raise(self, tmp_path):
        """A word (e.g. 'many') in mentions column must not raise."""
        rows = [
            {
                "regulator_name": "FCA",
                "canonical_regulator": "Financial Conduct Authority",
                "is_regulator": "True",
                "mentions": "many",
            },
        ]
        p = tmp_path / "regulator_canonical.csv"
        _write_canonical_csv(p, rows)
        try:
            result = load_regulator_canonical(path=p)
        except ValueError as exc:
            pytest.fail(f"Word-value mentions raised ValueError: {exc}")
        assert result is not None
