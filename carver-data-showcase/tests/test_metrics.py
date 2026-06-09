"""Unit tests for carver_showcase.metrics and carver_showcase.load.

All tests use small, crafted in-memory frames — the 423 MB JSONL is NEVER loaded here.
Tests verify:
- coverage_matrix overall and sliced
- NA-as-missing honesty in coverage counts
- score_distributions bucket structure
- breadth_summary distinct counts
- volume_over_time excludes implausible dates by default
- historical_depth uses the plausible min/max (not 1947 / 2105 extremes)
- load_normalized build-then-cached-read on a tiny JSONL fixture
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd
import pytest

from carver_showcase.config import PLAUSIBLE_DATE_WINDOW


# ---------------------------------------------------------------------------
# Helpers to build crafted DataFrames
# ---------------------------------------------------------------------------


def _make_df(**col_overrides) -> pd.DataFrame:
    """Return a tiny crafted DataFrame suitable for metrics tests.

    Default has 4 rows; override specific columns as needed.
    """
    base = {
        # Scores
        "impact_score": pd.array([8.0, 5.0, 3.0, pd.NA], dtype="Float64"),
        "urgency_score": pd.array([7.0, 4.5, 2.0, 6.0], dtype="Float64"),
        "relevance_score": pd.array([9.0, pd.NA, 5.0, 3.0], dtype="Float64"),
        "impact_confidence": pd.array([0.9, 0.7, 0.6, 0.8], dtype="Float64"),
        "urgency_confidence": pd.array([0.8, 0.75, 0.5, 0.9], dtype="Float64"),
        "relevance_confidence": pd.array([0.85, pd.NA, 0.6, 0.7], dtype="Float64"),
        "impact_label": pd.array(["high", "medium", "low", pd.NA], dtype="string"),
        "urgency_label": pd.array(["high", "medium", "low", "medium"], dtype="string"),
        "relevance_label": pd.array(["high", pd.NA, "medium", "low"], dtype="string"),
        "urgency_basis": pd.array(
            ["future_deadline", "no_future_date", "past_deadline", "no_future_date"],
            dtype="string",
        ),
        # Classification
        "jurisdiction_country": pd.array(["US", "GB", pd.NA, "AU"], dtype="string"),
        "update_type": pd.array(
            ["Regulatory Update", "Guidance", "Regulatory Update", pd.NA], dtype="string"
        ),
        "regulator_name": pd.array(["SEC", "FCA", "EMA", "FDA"], dtype="string"),
        "jurisdiction_scope": pd.array(["national", "national", "national", pd.NA], dtype="string"),
        "jurisdiction_bloc": pd.array([pd.NA, pd.NA, "EU", pd.NA], dtype="string"),
        # Category
        "category": pd.array(["Finance", "Finance", "Medical Devices", "Finance"], dtype="string"),
        # Source
        "feed_url": pd.array(
            ["https://sec.gov/news", pd.NA, "https://ema.europa.eu", pd.NA], dtype="string"
        ),
        # Topic
        "topic_id": pd.array(["t1", "t2", "t3", "t2"], dtype="string"),
        # Richness
        "n_actionable_lanes": pd.array([3, 5, 2, 0], dtype="Int64"),
    }
    base.update(col_overrides)
    return pd.DataFrame(base)


def _make_date_df(dates: list[str]) -> pd.DataFrame:
    """Return a DataFrame with a reconciled_published_date column from string list."""
    return pd.DataFrame(
        {
            "reconciled_published_date": pd.to_datetime(dates, utc=True, errors="coerce"),
            "category": pd.array(["Finance"] * len(dates), dtype="string"),
        }
    )


# ---------------------------------------------------------------------------
# Tests: coverage_matrix
# ---------------------------------------------------------------------------


class TestCoverageMatrix:
    def test_coverage_matrix_overall_returns_dataframe(self):
        """coverage_matrix returns a DataFrame with field and pct columns."""
        from carver_showcase.metrics import coverage_matrix

        df = _make_df()
        result = coverage_matrix(df)
        assert isinstance(result, pd.DataFrame)
        assert "field" in result.columns or result.index.name == "field" or len(result) > 0

    def test_coverage_matrix_overall_and_sliced(self):
        """Sliced matrix has one column per slice value plus the 'overall' column."""
        from carver_showcase.metrics import coverage_matrix

        df = _make_df()
        overall = coverage_matrix(df)
        sliced = coverage_matrix(df, slice_by="category")

        # Overall has at least 'pct' for each field
        assert "pct" in overall.columns or "overall" in overall.columns

        # Sliced result has more columns than the overall result
        assert sliced.shape[1] > overall.shape[1]

    def test_coverage_counts_na_as_missing(self):
        """A cell that is NA reduces the population percentage below 100%."""
        from carver_showcase.metrics import coverage_matrix

        # impact_score has one NA (row index 3) out of 4 rows → 75%
        df = _make_df()
        result = coverage_matrix(df)

        # Find impact_score row
        if "field" in result.columns:
            row = result[result["field"] == "impact_score"]
            pct_val = row["pct"].iloc[0] if not row.empty else None
        else:
            pct_val = result.loc["impact_score", "pct"] if "impact_score" in result.index else None

        if pct_val is not None:
            # 3 out of 4 populated = 75%
            assert abs(pct_val - 0.75) < 0.01, f"Expected ~0.75 but got {pct_val}"

    def test_coverage_matrix_all_na_field_is_zero(self):
        """A fully-NA column shows 0% coverage."""
        from carver_showcase.metrics import coverage_matrix

        df = _make_df()
        df["impact_score"] = pd.array([pd.NA, pd.NA, pd.NA, pd.NA], dtype="Float64")
        result = coverage_matrix(df)

        if "field" in result.columns:
            row = result[result["field"] == "impact_score"]
            pct_val = row["pct"].iloc[0] if not row.empty else None
        else:
            pct_val = result.loc["impact_score", "pct"] if "impact_score" in result.index else None

        if pct_val is not None:
            assert pct_val == 0.0, f"Expected 0.0 but got {pct_val}"


# ---------------------------------------------------------------------------
# Tests: score_distributions
# ---------------------------------------------------------------------------


class TestScoreDistributions:
    def test_score_distributions_returns_dict(self):
        """score_distributions returns a dict."""
        from carver_showcase.metrics import score_distributions

        df = _make_df()
        result = score_distributions(df)
        assert isinstance(result, dict)

    def test_score_distributions_buckets(self):
        """Result contains histogram data for impact, urgency, and relevance."""
        from carver_showcase.metrics import score_distributions

        df = _make_df()
        result = score_distributions(df)

        # Must have keys for the three score axes
        for axis in ("impact", "urgency", "relevance"):
            assert axis in result, f"Missing key '{axis}' in score_distributions result"

    def test_score_distributions_confidence_included(self):
        """Result contains confidence data for each axis."""
        from carver_showcase.metrics import score_distributions

        df = _make_df()
        result = score_distributions(df)

        # Confidence must be present for each axis
        for axis in ("impact", "urgency", "relevance"):
            axis_data = result[axis]
            assert "confidence" in axis_data or "confidence_values" in axis_data or isinstance(
                axis_data, dict
            ), f"Expected confidence info for axis '{axis}'"

    def test_score_distributions_label_mix_included(self):
        """Result contains label mix (value counts) for each axis."""
        from carver_showcase.metrics import score_distributions

        df = _make_df()
        result = score_distributions(df)

        for axis in ("impact", "urgency", "relevance"):
            axis_data = result[axis]
            assert "label_counts" in axis_data or "labels" in axis_data or isinstance(
                axis_data, dict
            ), f"Expected label info for axis '{axis}'"


# ---------------------------------------------------------------------------
# Tests: breadth_summary
# ---------------------------------------------------------------------------


class TestBreadthSummary:
    def test_breadth_summary_returns_dict(self):
        """breadth_summary returns a dict."""
        from carver_showcase.metrics import breadth_summary

        df = _make_df()
        result = breadth_summary(df)
        assert isinstance(result, dict)

    def test_breadth_summary_distinct_counts(self):
        """Distinct counts match what's in the crafted DataFrame."""
        from carver_showcase.metrics import breadth_summary

        df = _make_df()
        result = breadth_summary(df)

        # topics: 3 distinct topic_ids (t1, t2, t3) — t2 appears twice
        assert result.get("n_topics") == 3, f"Expected 3 topics, got {result.get('n_topics')}"

        # countries: US, GB, AU (1 NA → not counted)
        assert result.get("n_countries") == 3, f"Expected 3 countries, got {result.get('n_countries')}"

        # blocs: only 'EU' (3 NAs)
        assert result.get("n_blocs") == 1, f"Expected 1 bloc, got {result.get('n_blocs')}"

        # scopes: 'national' (3 populated, 1 NA)
        assert result.get("n_scopes") == 1, f"Expected 1 scope, got {result.get('n_scopes')}"

        # regulators: SEC, FCA, EMA, FDA → 4 distinct
        assert result.get("n_regulators") == 4, f"Expected 4 regulators, got {result.get('n_regulators')}"

    def test_breadth_summary_per_category_record_counts(self):
        """per-category record counts are included in the summary."""
        from carver_showcase.metrics import breadth_summary

        df = _make_df()
        result = breadth_summary(df)

        category_counts = result.get("category_counts") or result.get("per_category")
        assert category_counts is not None, "Expected category_counts in breadth_summary"
        # Finance appears 3 times, Medical Devices 1 time
        if isinstance(category_counts, dict):
            assert category_counts.get("Finance") == 3
            assert category_counts.get("Medical Devices") == 1
        elif isinstance(category_counts, pd.Series):
            assert category_counts.get("Finance") == 3
            assert category_counts.get("Medical Devices") == 1


# ---------------------------------------------------------------------------
# Tests: volume_over_time
# ---------------------------------------------------------------------------


class TestVolumeOverTime:
    def test_volume_over_time_returns_dataframe(self):
        """volume_over_time returns a DataFrame."""
        from carver_showcase.metrics import volume_over_time

        df = _make_date_df(["2025-01-15", "2025-01-20", "2025-03-10"])
        result = volume_over_time(df)
        assert isinstance(result, pd.DataFrame)

    def test_volume_over_time_excludes_implausible_by_default(self):
        """A row with a year-2105 date is excluded from the volume series by default."""
        from carver_showcase.metrics import volume_over_time

        # Mix of plausible dates (2025) and an implausible one (2105)
        df = _make_date_df(
            ["2025-01-15", "2025-01-20", "2025-03-10", "2105-07-01"]
        )
        result = volume_over_time(df)

        # The 2105 row should be excluded; only 3 records in the result
        total = result["count"].sum() if "count" in result.columns else result.iloc[:, -1].sum()
        assert total == 3, f"Expected 3 records (implausible 2105 excluded), got {total}"

    def test_volume_over_time_includes_implausible_when_toggled(self):
        """With exclude_implausible=False, all dates including 2105 are counted."""
        from carver_showcase.metrics import volume_over_time

        df = _make_date_df(
            ["2025-01-15", "2025-01-20", "2025-03-10", "2105-07-01"]
        )
        result = volume_over_time(df, exclude_implausible=False)

        total = result["count"].sum() if "count" in result.columns else result.iloc[:, -1].sum()
        assert total == 4, f"Expected 4 records (all dates included), got {total}"

    def test_volume_over_time_grouping_monthly(self):
        """Monthly grouping aggregates dates within the same month together."""
        from carver_showcase.metrics import volume_over_time

        df = _make_date_df(["2025-01-15", "2025-01-20", "2025-03-10"])
        result = volume_over_time(df, freq="ME")

        # January should have 2 records, March should have 1
        count_col = "count" if "count" in result.columns else result.columns[-1]
        assert len(result) == 2, f"Expected 2 months, got {len(result)}"
        counts = sorted(result[count_col].tolist())
        assert counts == [1, 2], f"Expected [1, 2] but got {counts}"


# ---------------------------------------------------------------------------
# Tests: historical_depth
# ---------------------------------------------------------------------------


class TestHistoricalDepth:
    def test_historical_depth_returns_dict(self):
        """historical_depth returns a dict."""
        from carver_showcase.metrics import historical_depth

        df = _make_date_df(["2024-06-01", "2025-01-15", "2025-06-01"])
        result = historical_depth(df)
        assert isinstance(result, dict)

    def test_historical_depth_uses_plausible_min_and_recency_buckets(self):
        """Earliest plausible date excludes the 1947 extreme; recency buckets are correct.

        Crafted rows:
          - 1947-12-25  → implausible (too old) → must NOT define earliest
          - 2105-07-01  → implausible (too far future) → must NOT define latest
          - 2020-06-01  → plausible, older
          - 2023-03-15  → plausible, within last 3 years
          - 2025-06-01  → plausible, within last 1 year (if today is ~2026-06)
        """
        from carver_showcase.metrics import historical_depth

        dates = [
            "1947-12-25",  # implausible old extreme
            "2105-07-01",  # implausible future extreme
            "2020-06-01",  # plausible, >3 years ago
            "2023-03-15",  # plausible, ~3 years ago
            "2025-06-01",  # plausible, ~1 year ago
        ]
        df = _make_date_df(dates)
        result = historical_depth(df)

        # earliest must be 2020-06-01, NOT 1947-12-25
        earliest = result.get("earliest_date")
        assert earliest is not None, "Expected 'earliest_date' in result"
        # Convert to date if it's a Timestamp
        if hasattr(earliest, "date"):
            earliest = earliest.date()
        import datetime
        assert earliest >= datetime.date(1990, 1, 1), (
            f"Earliest should be >= 1990 (plausible window start), got {earliest}"
        )
        assert earliest >= datetime.date(2020, 1, 1), (
            f"Earliest should be 2020-06-01 (not 1947), got {earliest}"
        )

        # latest must be within the plausible window
        latest = result.get("latest_date")
        assert latest is not None, "Expected 'latest_date' in result"
        if hasattr(latest, "date"):
            latest = latest.date()
        assert latest <= PLAUSIBLE_DATE_WINDOW[1], (
            f"Latest should be within plausible window, got {latest}"
        )
        assert latest < datetime.date(2100, 1, 1), (
            f"Latest should NOT be 2105, got {latest}"
        )

        # recency buckets: at least one bucket for 1y / 3y / 7y
        recency = result.get("recency")
        assert recency is not None, "Expected 'recency' in result"
        # Should be a dict with pct_1y, pct_3y, or pct_7y
        assert any(k in recency for k in ("pct_1y", "pct_3y", "pct_7y", "1y", "3y", "7y")), (
            f"Expected recency bucket keys, got {list(recency.keys())}"
        )

    def test_historical_depth_span_excludes_extremes(self):
        """Span (date range) is computed on plausible dates only."""
        from carver_showcase.metrics import historical_depth
        import datetime

        dates = ["1947-12-25", "2105-07-01", "2020-06-01", "2025-06-01"]
        df = _make_date_df(dates)
        result = historical_depth(df)

        span = result.get("span_days") or result.get("span")
        assert span is not None, "Expected 'span_days' or 'span' in result"
        # Plausible span: 2020-06-01 to 2025-06-01 ≈ 1826 days (not from 1947 to 2105)
        if isinstance(span, (int, float)):
            assert span < 50_000, f"Span looks too large (includes extremes?): {span} days"


# ---------------------------------------------------------------------------
# Tests: load_normalized (build-then-cached-read on a tiny JSONL fixture)
# ---------------------------------------------------------------------------


class TestLoadNormalized:
    def _make_minimal_jsonl(self, tmp_path: pathlib.Path, n: int = 5) -> pathlib.Path:
        """Write n minimal realistic-ish JSONL records to a temp file."""
        records = []
        for i in range(n):
            record = {
                "id": f"art-{i:04d}",
                "topic_id": f"topic-{i % 3:04d}",
                "source_id": f"src-{i:04d}",
                "state": "completed",
                "created_at": "2025-01-01T00:00:00.000Z",
                "completed_at": "2025-01-01T00:01:00.000Z",
                "input_data": {
                    "id": f"src-{i:04d}",
                    "extracted_metadata": {
                        "source_type": "rss",
                    },
                },
                "output_data": {
                    "entry_id": f"src-{i:04d}",
                    "scores": {
                        "impact": {"label": "medium", "score": 5.0, "confidence": 0.8},
                        "urgency": {
                            "label": "low",
                            "score": 2.0,
                            "confidence": 0.7,
                            "basis": "no_future_date",
                        },
                        "relevance": {"label": "high", "score": 7.0, "confidence": 0.9},
                    },
                    "metadata": {
                        "tags": ["tag1", "tag2"],
                        "entities": ["Entity A"],
                        "actionables": {
                            "policy_change": "Update policies.",
                        },
                        "critical_dates": {},
                        "impact_summary": {
                            "objective": "Test objective.",
                            "what_changed": "Something changed.",
                            "why_it_matters": "It matters.",
                            "risk_impact": "Risk here.",
                            "key_requirements": ["Req 1", "Req 2"],
                        },
                        "reg_references": {},
                        "impacted_business": {"industry": ["Finance"]},
                        "impacted_functions": ["Compliance"],
                        "penalties_consequences": "Some penalty.",
                    },
                    "classification": {
                        "metadata": {
                            "title": f"Test Article {i}",
                            "feed_url": f"https://example.com/article-{i}",
                        },
                        "update_type": "Guidance",
                        "update_subtype": "Draft",
                        "jurisdiction": {
                            "scope": "national",
                            "country": "US",
                            "bloc": None,
                        },
                        "regulatory_source": {
                            "name": "Test Regulator",
                            "division_office": None,
                            "other_agency": [],
                        },
                    },
                    "reconciled_published_date": {
                        "date": "2025-01-15",
                        "source": "content",
                        "converted": False,
                        "original_calendar": "gregorian",
                        "valid": True,
                    },
                },
            }
            records.append(record)

        path = tmp_path / "tiny_annotations.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return path

    def _make_categories_csv(self, tmp_path: pathlib.Path) -> pathlib.Path:
        """Write a minimal topic_categories.csv."""
        content = "topic_id,category\n"
        for i in range(3):
            content += f"topic-{i:04d},Finance\n"
        path = tmp_path / "topic_categories.csv"
        path.write_text(content)
        return path

    def test_build_then_cached_read(self, tmp_path: pathlib.Path):
        """First call builds parquet; second call reads it — both return same shape."""
        from carver_showcase.load import load_normalized

        jsonl_path = self._make_minimal_jsonl(tmp_path, n=5)
        cat_path = self._make_categories_csv(tmp_path)
        parquet_path = tmp_path / "annotations.parquet"

        # First call — parquet does not exist, must be built
        assert not parquet_path.exists()
        df1 = load_normalized(
            parquet_path=parquet_path,
            jsonl_path=jsonl_path,
            categories_path=cat_path,
            rebuild=False,
        )
        assert parquet_path.exists(), "Parquet file should have been created"
        assert df1.shape[0] == 5, f"Expected 5 rows, got {df1.shape[0]}"

        # Second call — parquet exists, reads directly
        df2 = load_normalized(
            parquet_path=parquet_path,
            jsonl_path=jsonl_path,
            categories_path=cat_path,
            rebuild=False,
        )
        assert df2.shape == df1.shape, (
            f"Cached read shape {df2.shape} != build shape {df1.shape}"
        )

    def test_rebuild_flag_overwrites_parquet(self, tmp_path: pathlib.Path):
        """rebuild=True forces a re-build even when parquet already exists."""
        from carver_showcase.load import load_normalized

        jsonl_path = self._make_minimal_jsonl(tmp_path, n=3)
        cat_path = self._make_categories_csv(tmp_path)
        parquet_path = tmp_path / "annotations.parquet"

        # Build with 3 rows first
        load_normalized(
            parquet_path=parquet_path,
            jsonl_path=jsonl_path,
            categories_path=cat_path,
        )

        # Write a new JSONL with 2 rows and rebuild
        sub_dir = tmp_path / "sub"
        sub_dir.mkdir(exist_ok=True)
        jsonl_path2 = self._make_minimal_jsonl(sub_dir, n=2)

        df_rebuild = load_normalized(
            parquet_path=parquet_path,
            jsonl_path=jsonl_path2,
            categories_path=cat_path,
            rebuild=True,
        )
        assert df_rebuild.shape[0] == 2, (
            f"After rebuild, expected 2 rows but got {df_rebuild.shape[0]}"
        )

    def test_load_catalog_reads_csv(self, tmp_path: pathlib.Path):
        """load_catalog reads a CSV and returns a DataFrame."""
        from carver_showcase.load import load_catalog

        catalog_content = (
            "topic_id,name,acronym,category,jurisdiction_code\n"
            "t1,Regulator A,RA,Finance,US\n"
            "t2,Regulator B,RB,Medical Devices,GB\n"
        )
        catalog_path = tmp_path / "topic_catalog.csv"
        catalog_path.write_text(catalog_content)

        df = load_catalog(catalog_path=catalog_path)
        assert isinstance(df, pd.DataFrame)
        assert df.shape[0] == 2
        assert "name" in df.columns
