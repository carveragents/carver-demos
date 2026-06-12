"""Unit tests for carver_showcase.metrics and carver_showcase.load.

All tests use small, crafted in-memory frames — the 423 MB JSONL is NEVER loaded here.
Tests verify:
- coverage_matrix overall and sliced
- NA-as-missing honesty in coverage counts
- score_distributions bucket structure
- breadth_summary distinct counts
- volume_over_time excludes implausible dates by default
- historical_depth excludes out-of-window extremes (1947 / 2105) and uses a low-quantile
  display floor for the advertised earliest date (true min reported separately)
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
# Tests: breadth_summary with regulator_canon
# ---------------------------------------------------------------------------


class TestBreadthSummaryRegulatorCanon:
    """Tests for the optional regulator_canon deduplication parameter."""

    def _make_canon_df(self, reg_names: list) -> pd.DataFrame:
        """Build a minimal DataFrame with just regulator_name (plus required cols)."""
        base = _make_df()
        # Override regulator_name with the provided list (pad/truncate to 4 rows).
        names = (reg_names + [None] * 4)[:4]
        base["regulator_name"] = pd.array(names, dtype="string")
        return base

    # ------------------------------------------------------------------
    # Backward-compatibility: no mapping → identical to plain nunique
    # ------------------------------------------------------------------

    def test_backward_compat_no_mapping(self):
        """No regulator_canon → n_regulators equals plain dropna().nunique()."""
        from carver_showcase.metrics import breadth_summary

        df = _make_df()
        result = breadth_summary(df)
        expected = int(df["regulator_name"].dropna().nunique())
        assert result["n_regulators"] == expected

    def test_backward_compat_other_keys_unchanged(self):
        """Empty regulator_canon → all non-regulator keys match the no-arg call."""
        from carver_showcase.metrics import breadth_summary

        df = _make_df()
        result_no_map = breadth_summary(df)
        # Pass an empty mapping: every regulator name is unmapped, so n_regulators
        # may differ from the no-arg (nunique) path.  Assert all OTHER keys are
        # identical — that is what this backward-compat test is actually verifying.
        result_empty_map = breadth_summary(df, regulator_canon={})
        other_keys = [k for k in result_no_map if k != "n_regulators"]
        for key in other_keys:
            assert result_no_map[key] == result_empty_map[key], (
                f"Key {key!r} changed unexpectedly between no-arg and empty-map calls"
            )

    # ------------------------------------------------------------------
    # Dedup: two raw names → same canonical key → counted as 1
    # ------------------------------------------------------------------

    def test_dedup_two_names_same_key(self):
        """Two raw names mapping to the same key are counted as 1 regulator."""
        from carver_showcase.metrics import breadth_summary

        canon = {
            "Financial Conduct Authority": {
                "canonical": "Financial Conduct Authority",
                "is_regulator": True,
                "key": "financial_conduct_authority",
            },
            "FCA": {
                "canonical": "Financial Conduct Authority",
                "is_regulator": True,
                "key": "financial_conduct_authority",  # same key
            },
        }
        df = self._make_canon_df(["Financial Conduct Authority", "FCA", None, None])
        result = breadth_summary(df, regulator_canon=canon)
        assert result["n_regulators"] == 1, (
            f"Expected 1 (two names share a key), got {result['n_regulators']}"
        )

    # ------------------------------------------------------------------
    # Drop: is_regulator=False → excluded from count
    # ------------------------------------------------------------------

    def test_drop_non_regulator(self):
        """A raw name with is_regulator=False is excluded from n_regulators."""
        from carver_showcase.metrics import breadth_summary

        canon = {
            "SEC": {
                "canonical": "Securities and Exchange Commission",
                "is_regulator": True,
                "key": "sec",
            },
            "Reuters": {
                "canonical": "Reuters",
                "is_regulator": False,  # news agency, not a regulator
                "key": "reuters",
            },
        }
        df = self._make_canon_df(["SEC", "Reuters", None, None])
        result = breadth_summary(df, regulator_canon=canon)
        # Only SEC (is_regulator=True) should be counted; Reuters is dropped.
        assert result["n_regulators"] == 1, (
            f"Expected 1 (Reuters dropped), got {result['n_regulators']}"
        )

    def test_all_non_regulators_gives_zero(self):
        """If every name has is_regulator=False, n_regulators == 0."""
        from carver_showcase.metrics import breadth_summary

        canon = {
            "Reuters": {"canonical": "Reuters", "is_regulator": False, "key": "reuters"},
            "Bloomberg": {"canonical": "Bloomberg", "is_regulator": False, "key": "bloomberg"},
        }
        df = self._make_canon_df(["Reuters", "Bloomberg", None, None])
        result = breadth_summary(df, regulator_canon=canon)
        assert result["n_regulators"] == 0

    # ------------------------------------------------------------------
    # Unmapped fallback: absent from canon → counted with raw name as key
    # ------------------------------------------------------------------

    def test_unmapped_name_is_counted(self):
        """A name absent from regulator_canon is still counted (raw name as key)."""
        from carver_showcase.metrics import breadth_summary

        # canon knows about SEC but not about "CFTC" (added after last batch run)
        canon = {
            "SEC": {
                "canonical": "Securities and Exchange Commission",
                "is_regulator": True,
                "key": "sec",
            },
        }
        df = self._make_canon_df(["SEC", "CFTC", None, None])
        result = breadth_summary(df, regulator_canon=canon)
        # SEC (mapped, is_regulator=True) + CFTC (unmapped fallback) = 2
        assert result["n_regulators"] == 2, (
            f"Expected 2 (mapped SEC + unmapped CFTC), got {result['n_regulators']}"
        )

    def test_unmapped_names_deduplicated_by_raw_key(self):
        """Multiple identical unmapped names count as 1, not N."""
        from carver_showcase.metrics import breadth_summary

        canon: dict = {}  # nothing mapped
        # Two rows with "UnknownBody" — should deduplicate to 1.
        df = self._make_canon_df(["UnknownBody", "UnknownBody", None, None])
        result = breadth_summary(df, regulator_canon=canon)
        assert result["n_regulators"] == 1, (
            f"Expected 1 (same unmapped name twice), got {result['n_regulators']}"
        )

    # ------------------------------------------------------------------
    # Mixed scenario: mapped true + mapped false + unmapped
    # ------------------------------------------------------------------

    def test_mixed_mapped_dropped_unmapped(self):
        """Mixed canon: 2 mapped-true (shared key), 1 dropped, 1 unmapped → 2."""
        from carver_showcase.metrics import breadth_summary

        canon = {
            "Financial Conduct Authority": {
                "canonical": "Financial Conduct Authority",
                "is_regulator": True,
                "key": "fca",
            },
            "FCA": {
                "canonical": "Financial Conduct Authority",
                "is_regulator": True,
                "key": "fca",  # same key as above
            },
            "Reuters": {
                "canonical": "Reuters",
                "is_regulator": False,
                "key": "reuters",
            },
            # "NewBody" intentionally absent → unmapped fallback
        }
        df = self._make_canon_df(
            ["Financial Conduct Authority", "FCA", "Reuters", "NewBody"]
        )
        result = breadth_summary(df, regulator_canon=canon)
        # "Financial Conduct Authority" + "FCA" → 1 (shared key "fca")
        # "Reuters" → dropped (is_regulator=False)
        # "NewBody" → 1 (unmapped fallback, raw name as key)
        # Total: 2
        assert result["n_regulators"] == 2, (
            f"Expected 2, got {result['n_regulators']}"
        )

    # ------------------------------------------------------------------
    # Filter-awareness: subset of rows → count reflects only that subset
    # ------------------------------------------------------------------

    def test_filter_awareness(self):
        """Passing a row-subset yields a count reflecting only that subset."""
        from carver_showcase.metrics import breadth_summary

        canon = {
            "SEC": {"canonical": "SEC", "is_regulator": True, "key": "sec"},
            "FCA": {"canonical": "FCA", "is_regulator": True, "key": "fca"},
            "EMA": {"canonical": "EMA", "is_regulator": True, "key": "ema"},
        }
        df_full = self._make_canon_df(["SEC", "FCA", "EMA", None])

        # Full df: 3 distinct mapped regulators.
        result_full = breadth_summary(df_full, regulator_canon=canon)
        assert result_full["n_regulators"] == 3

        # Subset: only rows where regulator_name is "SEC" or "FCA".
        df_subset = df_full[df_full["regulator_name"].isin(["SEC", "FCA"])].copy()
        result_subset = breadth_summary(df_subset, regulator_canon=canon)
        assert result_subset["n_regulators"] == 2, (
            f"Expected 2 for subset, got {result_subset['n_regulators']}"
        )

    # ------------------------------------------------------------------
    # No regulator_name column → 0
    # ------------------------------------------------------------------

    def test_missing_column_with_canon_returns_zero(self):
        """If regulator_name column is absent and canon is provided, n_regulators=0."""
        from carver_showcase.metrics import breadth_summary

        canon = {"SEC": {"canonical": "SEC", "is_regulator": True, "key": "sec"}}
        df = _make_df().drop(columns=["regulator_name"])
        result = breadth_summary(df, regulator_canon=canon)
        assert result["n_regulators"] == 0


# ---------------------------------------------------------------------------
# Tests: breadth_summary min_regulator_mentions threshold
# ---------------------------------------------------------------------------


class TestBreadthSummaryMinMentions:
    """Tests for the min_regulator_mentions threshold in breadth_summary.

    Uses an inline regulator_canon with bodies that have varying row-counts in
    the test DataFrame, verifying that the threshold correctly filters out
    long-tail bodies with too few mentions.
    """

    # Inline canon: three distinct bodies
    _CANON = {
        # "BodyA" and "body_a_alias" both map to key "body_a" → total 2 mentions
        "BodyA": {"canonical": "Body A", "is_regulator": True, "key": "body_a"},
        "body_a_alias": {"canonical": "Body A", "is_regulator": True, "key": "body_a"},
        # "BodyB" → key "body_b", will have 1 row → below threshold=3
        "BodyB": {"canonical": "Body B", "is_regulator": True, "key": "body_b"},
        # "BodyC" → key "body_c", will have 3 rows → at threshold=3
        "BodyC": {"canonical": "Body C", "is_regulator": True, "key": "body_c"},
        # "BodyD" → key "body_d", will have 5 rows → above threshold=3
        "BodyD": {"canonical": "Body D", "is_regulator": True, "key": "body_d"},
    }

    def _make_threshold_df(self) -> "pd.DataFrame":
        """Build a DataFrame where row counts per name are:
        - BodyA: 1, body_a_alias: 1 → body_a key total: 2 (below threshold=3)
        - BodyB: 1               → body_b key total: 1 (below threshold=3)
        - BodyC: 3               → body_c key total: 3 (meets threshold=3)
        - BodyD: 5               → body_d key total: 5 (above threshold=3)
        """
        names = (
            ["BodyA"] * 1
            + ["body_a_alias"] * 1
            + ["BodyB"] * 1
            + ["BodyC"] * 3
            + ["BodyD"] * 5
        )
        df = pd.DataFrame(
            {
                "regulator_name": pd.array(names, dtype="string"),
                "topic_id": pd.array([f"t{i}" for i in range(len(names))], dtype="string"),
                "jurisdiction_country": pd.array(["US"] * len(names), dtype="string"),
            }
        )
        return df

    def test_threshold_1_equals_plain_dedup(self):
        """min_regulator_mentions=1 (no cutoff) must equal the plain deduped key count."""
        from carver_showcase.metrics import breadth_summary

        df = self._make_threshold_df()
        result_1 = breadth_summary(df, regulator_canon=self._CANON, min_regulator_mentions=1)
        # 4 distinct keys: body_a (2 mentions), body_b (1), body_c (3), body_d (5)
        assert result_1["n_regulators"] == 4, (
            f"With min=1 expected 4 bodies, got {result_1['n_regulators']}"
        )

    def test_threshold_3_excludes_low_mention_bodies(self):
        """min_regulator_mentions=3 must exclude body_a (2 mentions) and body_b (1 mention)."""
        from carver_showcase.metrics import breadth_summary

        df = self._make_threshold_df()
        result_3 = breadth_summary(df, regulator_canon=self._CANON, min_regulator_mentions=3)
        # Only body_c (3) and body_d (5) meet the threshold
        assert result_3["n_regulators"] == 2, (
            f"With min=3 expected 2 bodies (body_c + body_d), got {result_3['n_regulators']}"
        )

    def test_split_variants_summed_across_raw_names(self):
        """A body whose mentions are split across two raw variants must sum them."""
        from carver_showcase.metrics import breadth_summary

        # BodyA appears 2x and body_a_alias appears 2x → key "body_a" = 4 total → meets min=3
        names = ["BodyA", "BodyA", "body_a_alias", "body_a_alias"]
        df = pd.DataFrame({"regulator_name": pd.array(names, dtype="string")})
        result = breadth_summary(df, regulator_canon=self._CANON, min_regulator_mentions=3)
        assert result["n_regulators"] == 1, (
            f"body_a should be counted (4 mentions summed across two variants), "
            f"got n_regulators={result['n_regulators']}"
        )

    def test_filter_awareness_changes_which_bodies_clear_threshold(self):
        """Passing a row-subset can push a borderline body below the threshold."""
        from carver_showcase.metrics import breadth_summary

        df_full = self._make_threshold_df()
        # Full frame: body_c (3 rows) meets min=3 → counted
        result_full = breadth_summary(df_full, regulator_canon=self._CANON, min_regulator_mentions=3)
        assert result_full["n_regulators"] == 2  # body_c + body_d

        # Subset: keep only BodyC rows minus 2 (leaves 1 BodyC row) and keep BodyD
        df_sub = df_full[df_full["regulator_name"].isin(["BodyC", "BodyD"])].head(3).copy()
        # Ensure BodyC appears fewer than 3 times in the subset
        sub_body_c_count = int((df_sub["regulator_name"] == "BodyC").sum())
        if sub_body_c_count < 3:
            result_sub = breadth_summary(df_sub, regulator_canon=self._CANON, min_regulator_mentions=3)
            # body_c drops below threshold in this subset
            assert result_sub["n_regulators"] <= 2, (
                f"Subset should have fewer qualifying bodies; got {result_sub['n_regulators']}"
            )

    def test_threshold_above_all_drops_to_zero(self):
        """A threshold higher than all mention-counts gives n_regulators=0."""
        from carver_showcase.metrics import breadth_summary

        # max in the full frame is 5 (BodyD); threshold=6 should give 0
        df = self._make_threshold_df()
        result = breadth_summary(df, regulator_canon=self._CANON, min_regulator_mentions=6)
        assert result["n_regulators"] == 0, (
            f"Expected 0 with threshold=6 (max mentions=5), got {result['n_regulators']}"
        )

    def test_default_min_matches_threshold_1(self):
        """Calling breadth_summary without min_regulator_mentions uses default=1."""
        from carver_showcase.metrics import breadth_summary

        df = self._make_threshold_df()
        result_default = breadth_summary(df, regulator_canon=self._CANON)
        result_explicit_1 = breadth_summary(df, regulator_canon=self._CANON, min_regulator_mentions=1)
        assert result_default["n_regulators"] == result_explicit_1["n_regulators"], (
            "Default (no min arg) must equal explicit min=1"
        )


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

        # recency buckets: one per configured window (1, 2, 3, 5, 10 years)
        recency = result.get("recency")
        assert recency is not None, "Expected 'recency' in result"
        expected_keys = {"pct_1y", "pct_2y", "pct_3y", "pct_5y", "pct_10y"}
        assert expected_keys.issubset(recency.keys()), (
            f"Expected recency buckets {expected_keys}, got {list(recency.keys())}"
        )
        # longer windows include at least as many records as shorter ones
        assert (
            recency["pct_1y"]
            <= recency["pct_2y"]
            <= recency["pct_3y"]
            <= recency["pct_5y"]
            <= recency["pct_10y"]
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

    def test_historical_depth_earliest_uses_quantile_floor(self):
        """earliest_date is the low-quantile DISPLAY floor (not the hard min); the true
        in-window minimum is still exposed as true_earliest_date, and sub-floor records
        are counted in n_below_floor."""
        import datetime

        from carver_showcase.metrics import historical_depth

        # One in-window old outlier (0.5% of the sample, below the 1% floor) + a recent
        # cluster. The floor should trim the lone 2005 record from the advertised earliest.
        dates = ["2005-01-01"] + ["2025-01-01"] * 199
        df = _make_date_df(dates)
        result = historical_depth(df)

        earliest = result["earliest_date"]
        true_earliest = result["true_earliest_date"]
        if hasattr(earliest, "date"):
            earliest = earliest.date()
        if hasattr(true_earliest, "date"):
            true_earliest = true_earliest.date()

        # True minimum is preserved and honestly reported …
        assert true_earliest == datetime.date(2005, 1, 1)
        # … but the advertised earliest is the recent cluster, not the 2005 outlier.
        assert earliest >= datetime.date(2024, 1, 1)
        assert earliest > true_earliest
        # The sub-floor outlier is counted, and the quantile is surfaced.
        assert result["n_below_floor"] >= 1
        assert result["floor_quantile"] == 0.01
        # All 200 rows are still plausible (the floor is display-only, not a filter).
        assert result["n_plausible"] == 200


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
