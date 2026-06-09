"""Tests for carver_showcase/schema.py and carver_showcase/config.py.

Tests verify:
- NORMALIZED_COLUMNS contains the full spec §4.2 column set (no missing/extra)
- RICHNESS_WEIGHTS sum to 1.0
- LABEL_BANDS partition [0,10] (no gaps, no overlaps)
- FIELD_MAP keys are a subset of NORMALIZED_COLUMNS
"""

import pytest

from carver_showcase import config, schema


# ---------------------------------------------------------------------------
# Expected column set from spec §4.2 — this is the ground truth.
# Any discrepancy between this set and NORMALIZED_COLUMNS is a bug.
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = {
    # Identity / envelope
    "artifact_id",
    "entry_id",
    "topic_id",
    "source_id",
    "state",
    "artifact_created_at",
    "artifact_updated_at",
    # Scores — 3 axes
    "impact_label",
    "impact_score",
    "impact_confidence",
    "urgency_label",
    "urgency_score",
    "urgency_confidence",
    "urgency_basis",
    "relevance_label",
    "relevance_score",
    "relevance_confidence",
    # Classification
    "update_type",
    "update_subtype",
    "regulator_name",
    "regulator_division",
    "regulator_other_agency",
    "jurisdiction_scope",
    "jurisdiction_country",
    "jurisdiction_bloc",
    "jurisdiction_locality",
    "jurisdiction_region",
    "jurisdiction_reasoning",
    "has_jurisdiction_tier_legacy",
    # Category
    "category",
    # Source document
    "title",
    "feed_url",
    "base_url",
    "language",
    "source_type",
    "summary",
    # Key dates (+paired *_calendar)
    "effective_date",
    "effective_date_calendar",
    "compliance_date",
    "compliance_date_calendar",
    "comment_deadline",
    "comment_deadline_calendar",
    "early_adoption_date",
    "early_adoption_date_calendar",
    "updated_date",
    "updated_date_calendar",
    "pub_date_content",
    "pub_date_calendar",
    "n_other_dates",
    # Reconciled published date
    "reconciled_published_date",
    "reconciled_pub_source",
    "reconciled_pub_converted",
    "reconciled_pub_original_calendar",
    "reconciled_pub_valid",
    # Richness counts & flags
    "n_tags",
    "n_entities",
    "n_actionable_lanes",
    "has_impact_summary",
    "has_objective",
    "has_what_changed",
    "has_why_it_matters",
    "has_risk_impact",
    "n_key_requirements",
    "n_reg_rules",
    "n_reg_statutes",
    "n_reg_other_ref",
    "n_reg_personnel",
    "n_reg_precedents",
    "n_reg_past_release",
    "n_reg_refs_total",
    "has_impacted_business",
    "n_impacted_functions",
    "n_penalties",
    "has_penalties",
    "n_critical_dates",
    "richness_score",
    # Quality support columns (Phase 4)
    "min_prose_len",
    "n_unparseable_dates",
}


class TestNormalizedColumns:
    def test_no_missing_columns(self):
        """NORMALIZED_COLUMNS must contain every column in the expected spec §4.2 set."""
        actual = set(schema.NORMALIZED_COLUMNS)
        missing = EXPECTED_COLUMNS - actual
        assert not missing, f"NORMALIZED_COLUMNS is missing: {sorted(missing)}"

    def test_no_extra_columns(self):
        """NORMALIZED_COLUMNS must not add columns absent from the spec §4.2 set."""
        actual = set(schema.NORMALIZED_COLUMNS)
        extra = actual - EXPECTED_COLUMNS
        assert not extra, f"NORMALIZED_COLUMNS has unexpected extras: {sorted(extra)}"

    def test_is_list_type(self):
        """NORMALIZED_COLUMNS must be a list (ordered)."""
        assert isinstance(schema.NORMALIZED_COLUMNS, list)

    def test_no_duplicates(self):
        """NORMALIZED_COLUMNS must not have duplicate entries."""
        cols = schema.NORMALIZED_COLUMNS
        assert len(cols) == len(set(cols)), "NORMALIZED_COLUMNS has duplicate entries"


class TestRichnessWeights:
    def test_sum_to_one(self):
        """RICHNESS_WEIGHTS must sum to exactly 1.0 (within float tolerance)."""
        total = sum(config.RICHNESS_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"RICHNESS_WEIGHTS sum to {total}, expected 1.0"

    def test_expected_keys(self):
        """RICHNESS_WEIGHTS must have exactly the 6 component keys."""
        expected_keys = {
            "prose",
            "actionables",
            "critical_dates",
            "reg_refs",
            "entities_tags",
            "impacted",
        }
        assert set(config.RICHNESS_WEIGHTS.keys()) == expected_keys

    def test_all_positive(self):
        """All weights must be strictly positive."""
        for k, v in config.RICHNESS_WEIGHTS.items():
            assert v > 0, f"Weight for '{k}' is not positive: {v}"


class TestLabelBands:
    def test_partition_covers_zero_to_ten(self):
        """LABEL_BANDS must partition [0, 10] with no gaps and no overlaps."""
        # Expected: low=[0,4), medium=[4,7), high=[7,10]
        bands = config.LABEL_BANDS  # e.g. {"low": (0,4), "medium": (4,7), "high": (7,10)}
        assert "low" in bands
        assert "medium" in bands
        assert "high" in bands

        lo_lo, lo_hi = bands["low"]
        med_lo, med_hi = bands["medium"]
        high_lo, high_hi = bands["high"]

        # No gap between bands
        assert lo_lo == 0, "low band must start at 0"
        assert lo_hi == med_lo, "gap/overlap between low and medium"
        assert med_hi == high_lo, "gap/overlap between medium and high"
        assert high_hi == 10, "high band must end at 10"

    def test_score_zero_falls_in_low(self):
        lo, hi = config.LABEL_BANDS["low"]
        assert lo <= 0 < hi

    def test_score_ten_falls_in_high(self):
        lo, hi = config.LABEL_BANDS["high"]
        assert lo <= 10 <= hi

    def test_score_four_falls_in_medium(self):
        lo, hi = config.LABEL_BANDS["medium"]
        assert lo <= 4 < hi

    def test_score_seven_falls_in_high(self):
        lo, hi = config.LABEL_BANDS["high"]
        assert lo <= 7 <= hi


class TestFieldMap:
    def test_field_map_keys_subset_of_normalized_columns(self):
        """Every column named in FIELD_MAP must appear in NORMALIZED_COLUMNS."""
        col_set = set(schema.NORMALIZED_COLUMNS)
        field_map_cols = set(schema.FIELD_MAP.values())
        missing = field_map_cols - col_set
        assert not missing, (
            f"FIELD_MAP references columns not in NORMALIZED_COLUMNS: {sorted(missing)}"
        )

    def test_field_map_is_dict(self):
        assert isinstance(schema.FIELD_MAP, dict)

    def test_field_map_non_empty(self):
        assert len(schema.FIELD_MAP) > 0


class TestConfigConstants:
    def test_score_range(self):
        assert config.SCORE_RANGE == (0, 10)

    def test_confidence_range(self):
        assert config.CONFIDENCE_RANGE == (0, 1)

    def test_placeholders_non_empty(self):
        assert len(config.PLACEHOLDERS) > 0
        # Must include the canonical empties
        lower = {p.lower() for p in config.PLACEHOLDERS}
        for expected in ("", "n/a", "null", "none", "-", "unknown"):
            assert expected in lower, f"'{expected}' missing from PLACEHOLDERS"

    def test_min_prose_chars_positive(self):
        assert config.MIN_PROSE_CHARS > 0

    def test_paths_defined(self):
        import pathlib
        assert config.DATA_DIR
        assert config.ANNOTATIONS_JSONL
        assert config.ANNOTATIONS_PARQUET
        assert config.TOPIC_CATEGORIES_CSV
        assert config.TOPIC_CATALOG_CSV

    def test_iso_country_non_empty(self):
        """ISO_COUNTRY must be a non-empty dict mapping ISO-2 codes."""
        assert isinstance(config.ISO_COUNTRY, dict)
        assert len(config.ISO_COUNTRY) >= 200  # at least ~200 countries
        # Spot-check a few well-known codes
        assert "US" in config.ISO_COUNTRY
        assert "GB" in config.ISO_COUNTRY
        assert "DE" in config.ISO_COUNTRY

    def test_iso_country_structure(self):
        """Each ISO_COUNTRY entry must have iso3 and name."""
        us = config.ISO_COUNTRY.get("US")
        assert us is not None
        assert "iso3" in us
        assert "name" in us
        assert us["iso3"] == "USA"

    def test_plausible_date_window(self):
        """PLAUSIBLE_DATE_WINDOW must be a (start, end) date tuple where start < end."""
        import datetime
        w = config.PLAUSIBLE_DATE_WINDOW
        assert len(w) == 2
        start, end = w
        assert start < end

    def test_actionable_lanes(self):
        """ACTIONABLE_LANES must be a list/tuple of 7 lane names."""
        assert len(config.ACTIONABLE_LANES) == 7

    def test_reg_ref_lanes(self):
        """REG_REF_LANES must be a list/tuple of 6 lane names."""
        assert len(config.REG_REF_LANES) == 6

    def test_impact_summary_parts(self):
        """IMPACT_SUMMARY_PARTS must be a list/tuple of 5 part names."""
        assert len(config.IMPACT_SUMMARY_PARTS) == 5
