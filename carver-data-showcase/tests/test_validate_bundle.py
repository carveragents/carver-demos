"""Tests for tools/validate_bundle.py — offline bundle gate (Task 5).

Covers:
  - Clean slim bundle (15-col parquet + valid sidecars + deck stub) → all HARD
    pass, validate_bundle returns 0, writes report + baseline.
  - Denylist column OR oversized string → HARD FAIL → returns 1; baseline NOT
    updated.
  - Row count collapsed vs a provided baseline → HARD FAIL → 1.
  - topic_id absent from catalog → HARD FAIL.
  - Drift only (distinct countries shifted) → WARN present, returns 0, baseline
    updated.
  - Report file content includes FAIL markers when failing.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

# Ensure repo root is on sys.path so the module can be imported
ROOT = pathlib.Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carver_showcase.config import PUBLIC_KEEP_COLUMNS, PUBLIC_ORPHAN_TOPIC_TOLERANCE, PUBLIC_STRING_MAXLEN


# ---------------------------------------------------------------------------
# Module import helpers
# ---------------------------------------------------------------------------

def _import_module():
    import importlib
    return importlib.import_module("tools.validate_bundle")


# ---------------------------------------------------------------------------
# Bundle fixture builders
# ---------------------------------------------------------------------------

_PDF_STUB = b"%PDF-1.4\n" + b"X" * 21_000  # >20 KB, valid magic bytes


def _make_slim_df(n_rows: int = 50) -> pd.DataFrame:
    """Build a minimal valid slim DataFrame with exactly the 15 keep columns."""
    data: dict = {}
    for col in PUBLIC_KEEP_COLUMNS:
        if "score" in col or col in ("richness_score", "n_entities", "n_tags"):
            data[col] = [float(i % 10) for i in range(n_rows)]
        elif col == "reconciled_published_date":
            data[col] = ["2024-01-01"] * n_rows
        elif col in ("topic_id",):
            data[col] = [f"topic-{i:04d}" for i in range(n_rows)]
        elif col == "jurisdiction_country":
            data[col] = ["US"] * n_rows
        else:
            # Short strings — well within PUBLIC_STRING_MAXLEN (64)
            data[col] = [f"v{i}" for i in range(n_rows)]
    return pd.DataFrame(data)


def _make_catalog_df(topic_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"topic_id": topic_ids, "name": [f"Institution {t}" for t in topic_ids]})


def _make_snapshot_meta(snapshot_date: str = "2024-01-01") -> dict:
    return {"snapshot_date": snapshot_date, "total_records": 50}


def _write_bundle(
    tmp_path: pathlib.Path,
    df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    snapshot_meta: dict,
    include_deck: bool = True,
    deck_content: bytes = _PDF_STUB,
    baseline: dict | None = None,
) -> pathlib.Path:
    """Write a complete bundle directory to tmp_path and return it."""
    bundle_dir = tmp_path / "public"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # annotations.parquet
    df.to_parquet(bundle_dir / "annotations.parquet", engine="pyarrow", index=False)

    # topic_catalog.csv  (keep_default_na=False keeps literal "NA" values)
    catalog_df.to_csv(bundle_dir / "topic_catalog.csv", index=False)

    # snapshot_meta.json
    (bundle_dir / "snapshot_meta.json").write_text(
        json.dumps(snapshot_meta), encoding="utf-8"
    )

    # deck PDF stub
    if include_deck:
        (bundle_dir / "carver-state-of-data.pdf").write_bytes(deck_content)

    # optional pre-existing baseline
    if baseline is not None:
        (bundle_dir / "baseline.json").write_text(
            json.dumps(baseline), encoding="utf-8"
        )

    return bundle_dir


# ---------------------------------------------------------------------------
# Pure check unit tests
# ---------------------------------------------------------------------------

class TestCheckNoExtraColumns:
    def test_pass_exact_keep_columns(self):
        mod = _import_module()
        df = _make_slim_df()
        result = mod.check_no_extra_columns(df)
        assert result.ok is True
        assert result.level == "HARD"

    def test_fail_extra_column(self):
        mod = _import_module()
        df = _make_slim_df()
        df["title"] = "should not be here"
        result = mod.check_no_extra_columns(df)
        assert result.ok is False
        assert "title" in result.detail


class TestCheckNoDenylistColumns:
    def test_pass_clean_frame(self):
        mod = _import_module()
        df = _make_slim_df()
        result = mod.check_no_denylist_columns(df)
        assert result.ok is True

    def test_fail_title_present(self):
        mod = _import_module()
        df = _make_slim_df()
        df["title"] = "leaked content"
        result = mod.check_no_denylist_columns(df)
        assert result.ok is False
        assert "title" in result.detail


class TestCheckStringLengths:
    def test_pass_short_strings(self):
        mod = _import_module()
        df = _make_slim_df()
        result = mod.check_string_lengths(df)
        assert result.ok is True

    def test_fail_oversized_string(self):
        mod = _import_module()
        df = _make_slim_df()
        # Insert a value that exceeds PUBLIC_STRING_MAXLEN in a string column
        df.at[0, "update_type"] = "X" * 200
        result = mod.check_string_lengths(df)
        assert result.ok is False
        assert "update_type" in result.detail

    def test_pass_string_exactly_at_limit_minus_one(self):
        """Strings with length PUBLIC_STRING_MAXLEN - 1 must pass."""
        mod = _import_module()
        df = _make_slim_df()
        df.at[0, "update_type"] = "X" * (PUBLIC_STRING_MAXLEN - 1)
        result = mod.check_string_lengths(df)
        assert result.ok is True

    def test_fail_string_exactly_at_limit(self):
        """A string of EXACTLY PUBLIC_STRING_MAXLEN chars must FAIL (pins the >= boundary)."""
        mod = _import_module()
        df = _make_slim_df()
        df.at[0, "update_type"] = "X" * PUBLIC_STRING_MAXLEN
        result = mod.check_string_lengths(df)
        assert result.ok is False, (
            f"Expected FAIL for string of length {PUBLIC_STRING_MAXLEN} "
            f"(== PUBLIC_STRING_MAXLEN), got ok=True"
        )
        assert "update_type" in result.detail


class TestCheckSchemaPresent:
    def test_pass_all_columns_present(self):
        mod = _import_module()
        df = _make_slim_df()
        result = mod.check_schema_present(df)
        assert result.ok is True

    def test_fail_missing_column(self):
        mod = _import_module()
        df = _make_slim_df().drop(columns=["richness_score"])
        result = mod.check_schema_present(df)
        assert result.ok is False
        assert "richness_score" in result.detail


class TestCheckNotEmpty:
    def test_pass_non_empty(self):
        mod = _import_module()
        df = _make_slim_df(10)
        result = mod.check_not_empty(df)
        assert result.ok is True

    def test_fail_empty_df(self):
        mod = _import_module()
        df = _make_slim_df(0)
        result = mod.check_not_empty(df)
        assert result.ok is False


class TestCheckNoNullColumns:
    def test_pass_no_fully_null_columns(self):
        mod = _import_module()
        df = _make_slim_df(5)
        result = mod.check_no_null_columns(df)
        assert result.ok is True

    def test_fail_fully_null_column(self):
        mod = _import_module()
        df = _make_slim_df(5)
        df["jurisdiction_country"] = None
        result = mod.check_no_null_columns(df)
        assert result.ok is False
        assert "jurisdiction_country" in result.detail


class TestCheckRowcountVsBaseline:
    def test_pass_no_baseline(self):
        mod = _import_module()
        df = _make_slim_df(100)
        result = mod.check_rowcount_vs_baseline(df, None)
        assert result.ok is True

    def test_pass_within_tolerance(self):
        mod = _import_module()
        df = _make_slim_df(90)  # 10% drop from 100
        result = mod.check_rowcount_vs_baseline(df, {"rows": 100})
        assert result.ok is True

    def test_fail_excessive_drop(self):
        mod = _import_module()
        df = _make_slim_df(50)  # 50% drop from 100
        result = mod.check_rowcount_vs_baseline(df, {"rows": 100})
        assert result.ok is False
        assert "50%" in result.detail or "0.5" in result.detail or "50.0%" in result.detail


class TestCheckSnapshotAdvanced:
    def test_pass_no_baseline(self):
        mod = _import_module()
        result = mod.check_snapshot_advanced({"snapshot_date": "2024-02-01"}, None)
        assert result.ok is True

    def test_pass_advanced(self):
        mod = _import_module()
        meta = {"snapshot_date": "2024-02-01"}
        baseline = {"snapshot_date": "2024-01-01"}
        result = mod.check_snapshot_advanced(meta, baseline)
        assert result.ok is True

    def test_pass_equal_date_not_hard_fail(self):
        """Equal dates are NOT a HARD failure — documented intent."""
        mod = _import_module()
        meta = {"snapshot_date": "2024-01-01"}
        baseline = {"snapshot_date": "2024-01-01"}
        result = mod.check_snapshot_advanced(meta, baseline)
        assert result.ok is True
        assert result.level == "HARD"

    def test_fail_regression(self):
        mod = _import_module()
        meta = {"snapshot_date": "2024-01-01"}
        baseline = {"snapshot_date": "2024-02-01"}
        result = mod.check_snapshot_advanced(meta, baseline)
        assert result.ok is False
        assert "regress" in result.detail.lower()


class TestCheckTopicIdsInCatalog:
    def test_pass_all_resolved(self):
        mod = _import_module()
        df = _make_slim_df(5)
        catalog = _make_catalog_df([f"topic-{i:04d}" for i in range(5)])
        result = mod.check_topic_ids_in_catalog(df, catalog)
        assert result.ok is True
        # Detail must always include orphan count and share, even when passing
        assert "orphan" in result.detail.lower()

    def test_pass_few_orphans_within_tolerance(self):
        """A few orphan topic_ids (at or below the tolerance) must PASS with detail."""
        mod = _import_module()
        # 100 distinct topic_ids, 1 orphan = 1% share < 2% tolerance → PASS
        n = 100
        df = _make_slim_df(n)
        catalog = _make_catalog_df([f"topic-{i:04d}" for i in range(1, n)])  # missing topic-0000
        result = mod.check_topic_ids_in_catalog(df, catalog)
        assert result.ok is True, (
            f"Expected PASS for 1/{n} orphan (<= tolerance={PUBLIC_ORPHAN_TOPIC_TOLERANCE:.0%}), "
            f"got ok=False: {result.detail}"
        )
        # orphan count and share must still appear in the detail
        assert "orphan" in result.detail.lower() or "1" in result.detail

    def test_fail_many_orphans_exceeds_tolerance(self):
        """Many orphan topic_ids (> tolerance) must HARD FAIL."""
        mod = _import_module()
        # 10 distinct topic_ids, 5 orphans = 50% share >> 2% tolerance → FAIL
        df = _make_slim_df(10)
        catalog = _make_catalog_df([f"topic-{i:04d}" for i in range(5, 10)])  # 5 missing
        result = mod.check_topic_ids_in_catalog(df, catalog)
        assert result.ok is False
        assert result.level == "HARD"
        # detail includes sample of orphans
        assert "topic-0000" in result.detail

    def test_detail_always_includes_orphan_share(self):
        """The detail string must include orphan count and share regardless of pass/fail."""
        mod = _import_module()
        df = _make_slim_df(5)
        catalog = _make_catalog_df([f"topic-{i:04d}" for i in range(5)])
        result = mod.check_topic_ids_in_catalog(df, catalog)
        assert "%" in result.detail, "detail must include a share percentage"


class TestCheckDeckPdf:
    def test_pass_valid_pdf(self, tmp_path):
        mod = _import_module()
        pdf_path = tmp_path / "carver-state-of-data.pdf"
        pdf_path.write_bytes(_PDF_STUB)
        result = mod.check_deck_pdf(pdf_path)
        assert result.ok is True

    def test_fail_missing_pdf(self, tmp_path):
        mod = _import_module()
        result = mod.check_deck_pdf(tmp_path / "carver-state-of-data.pdf")
        assert result.ok is False
        assert "not found" in result.detail.lower()

    def test_fail_wrong_magic_bytes(self, tmp_path):
        mod = _import_module()
        pdf_path = tmp_path / "carver-state-of-data.pdf"
        pdf_path.write_bytes(b"NOTPDF" + b"X" * 21_000)
        result = mod.check_deck_pdf(pdf_path)
        assert result.ok is False
        assert "%PDF-" in result.detail

    def test_fail_too_small(self, tmp_path):
        mod = _import_module()
        pdf_path = tmp_path / "carver-state-of-data.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n" + b"X" * 100)  # tiny
        result = mod.check_deck_pdf(pdf_path)
        assert result.ok is False
        assert "small" in result.detail.lower()


class TestCheckSidecarsPresent:
    def test_pass_required_present(self, tmp_path):
        mod = _import_module()
        (tmp_path / "topic_catalog.csv").write_text("topic_id\n")
        (tmp_path / "snapshot_meta.json").write_text("{}")
        result = mod.check_sidecars_present(tmp_path)
        assert result.ok is True

    def test_fail_missing_required(self, tmp_path):
        mod = _import_module()
        # Only one of the two required files
        (tmp_path / "topic_catalog.csv").write_text("topic_id\n")
        result = mod.check_sidecars_present(tmp_path)
        assert result.ok is False
        assert "snapshot_meta.json" in result.detail


# ---------------------------------------------------------------------------
# Integration tests — validate_bundle end-to-end
# ---------------------------------------------------------------------------

class TestValidateBundleClean:
    """A clean valid bundle returns exit code 0 and writes report + baseline."""

    def test_returns_zero(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 0

    def test_writes_report_md(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        mod.validate_bundle(bundle_dir)
        assert (bundle_dir / "validation_report.md").exists()

    def test_writes_baseline_json(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        mod.validate_bundle(bundle_dir)
        baseline_path = bundle_dir / "baseline.json"
        assert baseline_path.exists()
        baseline = json.loads(baseline_path.read_text())
        assert baseline["rows"] == 50
        assert "distinct_institutions" in baseline

    def test_report_contains_pass(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        mod.validate_bundle(bundle_dir)
        report = (bundle_dir / "validation_report.md").read_text()
        assert "PASS" in report


class TestValidateBundleDenylistFail:
    """A bundle with a denylist column → HARD FAIL → exit code 1."""

    def test_returns_one(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        df["title"] = "leaked title content"  # denylist column
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 1

    def test_baseline_not_written(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        df["title"] = "leaked title content"
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        mod.validate_bundle(bundle_dir)
        assert not (bundle_dir / "baseline.json").exists()

    def test_report_contains_fail(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        df["title"] = "leaked title content"
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        mod.validate_bundle(bundle_dir)
        report = (bundle_dir / "validation_report.md").read_text()
        assert "FAIL" in report


class TestValidateBundleOversizedStringFail:
    """A bundle with an oversized string column → HARD FAIL → exit code 1."""

    def test_returns_one(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        df.at[0, "update_type"] = "A" * 200  # exceeds PUBLIC_STRING_MAXLEN
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 1

    def test_baseline_not_written(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(50)
        df.at[0, "update_type"] = "A" * 200
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-15"),
        )
        mod.validate_bundle(bundle_dir)
        assert not (bundle_dir / "baseline.json").exists()


class TestValidateBundleRowcountCollapse:
    """Row count collapsed vs baseline → HARD FAIL → exit code 1."""

    def test_returns_one(self, tmp_path):
        mod = _import_module()
        # baseline says 100 rows; we ship only 20 → 80% drop → exceeds 20% tolerance
        baseline = {
            "rows": 100,
            "snapshot_date": "2024-01-01",
            "distinct_institutions": 10,
            "distinct_countries": 5,
            "distinct_update_types": 3,
            "null_rates": {},
            "score_means": {},
            "out_of_window_date_share": 0.0,
        }
        df = _make_slim_df(20)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-02"),
            baseline=baseline,
        )
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 1

    def test_report_has_fail_for_rowcount(self, tmp_path):
        mod = _import_module()
        baseline = {
            "rows": 100,
            "snapshot_date": "2024-01-01",
            "distinct_institutions": 10,
            "distinct_countries": 5,
            "distinct_update_types": 3,
            "null_rates": {},
            "score_means": {},
            "out_of_window_date_share": 0.0,
        }
        df = _make_slim_df(20)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-02"),
            baseline=baseline,
        )
        mod.validate_bundle(bundle_dir)
        report = (bundle_dir / "validation_report.md").read_text()
        assert "FAIL" in report


class TestValidateBundleOrphanTopicId:
    """topic_id absent from catalog → HARD FAIL → exit code 1."""

    def test_returns_one(self, tmp_path):
        mod = _import_module()
        df = _make_slim_df(5)
        # Catalog missing topic-0000
        catalog = _make_catalog_df([f"topic-{i:04d}" for i in range(1, 5)])
        bundle_dir = _write_bundle(
            tmp_path, df, catalog,
            _make_snapshot_meta("2024-01-15"),
        )
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 1


class TestValidateBundleSoftDriftOnly:
    """Drift-only scenario (distinct countries shifted) → WARN, returns 0, baseline updated."""

    def test_returns_zero_on_drift_only(self, tmp_path):
        mod = _import_module()
        # baseline has 10 distinct countries; current has 50 (large relative drift → SOFT warn)
        # But all HARD checks pass
        baseline = {
            "rows": 50,
            "snapshot_date": "2024-01-01",
            "distinct_institutions": 50,
            "distinct_countries": 10,   # big drift — current will have 1
            "distinct_update_types": 1,
            "null_rates": {col: 0.0 for col in PUBLIC_KEEP_COLUMNS},
            "score_means": {"impact_score": 5.0, "urgency_score": 5.0},
            "out_of_window_date_share": 0.0,
        }
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-02"),
            baseline=baseline,
        )
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 0

    def test_warn_present_in_report(self, tmp_path):
        mod = _import_module()
        baseline = {
            "rows": 50,
            "snapshot_date": "2024-01-01",
            "distinct_institutions": 50,
            "distinct_countries": 10,
            "distinct_update_types": 1,
            "null_rates": {col: 0.0 for col in PUBLIC_KEEP_COLUMNS},
            "score_means": {"impact_score": 5.0, "urgency_score": 5.0},
            "out_of_window_date_share": 0.0,
        }
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-02"),
            baseline=baseline,
        )
        mod.validate_bundle(bundle_dir)
        report = (bundle_dir / "validation_report.md").read_text()
        assert "WARN" in report

    def test_baseline_updated_on_soft_warn(self, tmp_path):
        mod = _import_module()
        baseline = {
            "rows": 50,
            "snapshot_date": "2024-01-01",
            "distinct_institutions": 50,
            "distinct_countries": 10,
            "distinct_update_types": 1,
            "null_rates": {col: 0.0 for col in PUBLIC_KEEP_COLUMNS},
            "score_means": {"impact_score": 5.0, "urgency_score": 5.0},
            "out_of_window_date_share": 0.0,
        }
        df = _make_slim_df(50)
        topic_ids = df["topic_id"].unique().tolist()
        bundle_dir = _write_bundle(
            tmp_path, df,
            _make_catalog_df(topic_ids),
            _make_snapshot_meta("2024-01-02"),
            baseline=baseline,
        )
        mod.validate_bundle(bundle_dir)
        new_baseline = json.loads((bundle_dir / "baseline.json").read_text())
        assert new_baseline["snapshot_date"] == "2024-01-02"


class TestReportContentOnFail:
    """Report file must include FAIL markers when any HARD check fails."""

    def test_report_fail_on_missing_required_sidecar(self, tmp_path):
        mod = _import_module()
        bundle_dir = tmp_path / "public"
        bundle_dir.mkdir()
        df = _make_slim_df(10)
        topic_ids = df["topic_id"].unique().tolist()
        df.to_parquet(bundle_dir / "annotations.parquet", engine="pyarrow", index=False)
        # topic_catalog.csv present; snapshot_meta.json MISSING → sidecar check fails
        _make_catalog_df(topic_ids).to_csv(bundle_dir / "topic_catalog.csv", index=False)
        (bundle_dir / "carver-state-of-data.pdf").write_bytes(_PDF_STUB)
        # No snapshot_meta.json on disk → sidecars_present HARD fail
        exit_code = mod.validate_bundle(bundle_dir)
        assert exit_code == 1
        report = (bundle_dir / "validation_report.md").read_text()
        assert "FAIL" in report


class TestCurrentBaseline:
    """current_baseline returns expected keys and correct row count."""

    def test_keys_present(self):
        mod = _import_module()
        df = _make_slim_df(30)
        meta = {"snapshot_date": "2024-03-01"}
        baseline = mod.current_baseline(df, meta)
        assert baseline["rows"] == 30
        assert "distinct_institutions" in baseline
        assert "distinct_countries" in baseline
        assert "null_rates" in baseline
        assert "score_means" in baseline
        assert "snapshot_date" in baseline
        assert baseline["snapshot_date"] == "2024-03-01"

    def test_null_rates_keys_match_keep_columns(self):
        mod = _import_module()
        df = _make_slim_df(20)
        baseline = mod.current_baseline(df, {})
        for col in PUBLIC_KEEP_COLUMNS:
            assert col in baseline["null_rates"]


class TestSummarize:
    """summarize() correctly tallies HARD/SOFT counts and hard_failed flag."""

    def test_all_pass(self):
        mod = _import_module()
        results = [
            mod.CheckResult("c1", "HARD", True, ""),
            mod.CheckResult("c2", "SOFT", True, ""),
        ]
        s = mod.summarize(results)
        assert s["hard_failed"] is False
        assert s["hard_passed"] == 1
        assert s["soft_warned"] == 0

    def test_one_hard_fail(self):
        mod = _import_module()
        results = [
            mod.CheckResult("c1", "HARD", False, "bad"),
            mod.CheckResult("c2", "SOFT", False, "warn"),
        ]
        s = mod.summarize(results)
        assert s["hard_failed"] is True
        assert s["hard_failed_count"] == 1
        assert s["soft_warned"] == 1
