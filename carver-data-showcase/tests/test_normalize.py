"""Tests for carver_showcase/normalize.py.

All tests are deterministic — no LLM, no network.

The `raw_envelope` fixture (from conftest.py) is a realistic annotation envelope
with a mix of populated, empty, whitespace-only, and placeholder fields.
"""

import math
import copy

import pandas as pd
import pytest

from carver_showcase import normalize, schema, config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm(raw_envelope: dict) -> dict:
    """Normalize one envelope and return the flat row dict."""
    return normalize.normalize_record(raw_envelope)


# ---------------------------------------------------------------------------
# Empties / placeholder → NA
# ---------------------------------------------------------------------------


class TestEmptiesAndPlaceholders:
    def test_empty_string_and_placeholders_become_na(self, raw_envelope: dict):
        """'' and placeholder strings (N/A, None, etc.) must normalize to pd.NA."""
        row = _norm(raw_envelope)
        # compliance_date is "" in the fixture
        assert pd.isna(row["compliance_date"]), "empty string should become NA"
        # jurisdiction_bloc is "N/A" in the fixture → NA
        assert pd.isna(row["jurisdiction_bloc"]), "'N/A' should become NA"

    def test_whitespace_only_is_na(self, raw_envelope: dict):
        """Whitespace-only actionable lane must not be counted and resolves to NA internally."""
        row = _norm(raw_envelope)
        # process_change = "   " → not a counted lane; n_actionable_lanes should not include it
        # The fixture has: policy_change populated, reporting_change populated, tech_data_change populated
        # status_change="", process_change="   ", training_change="N/A", other_change="None" → all NA
        assert row["n_actionable_lanes"] == 3, (
            "Only 3 lanes are genuinely populated (policy_change, reporting_change, tech_data_change)"
        )

    def test_placeholder_none_string_becomes_na(self, raw_envelope: dict):
        """The string 'None' (case-insensitive) must be treated as a placeholder → NA."""
        row = _norm(raw_envelope)
        # other_change = "None" in fixture → NA; should not be counted
        assert row["n_actionable_lanes"] == 3

    def test_null_value_becomes_na(self, raw_envelope: dict):
        """Python None values in nested fields resolve to pd.NA / None."""
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["classification"]["jurisdiction"]["locality"] = None
        row = _norm(raw)
        assert pd.isna(row["jurisdiction_locality"])


# ---------------------------------------------------------------------------
# Counts computed AFTER empties pass
# ---------------------------------------------------------------------------


class TestCountsAfterEmpties:
    def test_counts_computed_after_empties(self, raw_envelope: dict):
        """Counts must reflect the post-empties state, not the raw field count."""
        row = _norm(raw_envelope)
        # The fixture has 3 genuinely populated actionable lanes (policy, reporting, tech_data)
        assert row["n_actionable_lanes"] == 3

    def test_n_tags_counts_non_empty(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # 3 tags in fixture
        assert row["n_tags"] == 3

    def test_n_entities_counts_non_empty(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # 3 entities in fixture
        assert row["n_entities"] == 3

    def test_n_key_requirements_counts_list_items(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # 3 key_requirements in fixture
        assert row["n_key_requirements"] == 3

    def test_n_actionable_lanes_over_seven_lanes(self, raw_envelope: dict):
        """n_actionable_lanes is bounded to the 7 defined lanes; can't exceed 7."""
        row = _norm(raw_envelope)
        assert 0 <= row["n_actionable_lanes"] <= 7

    def test_n_reg_refs_counts_each_lane(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # rules: 2, statutes: 2, other_ref: 1, personnel: 0, precedents: 0, past_release: 1
        assert row["n_reg_rules"] == 2
        assert row["n_reg_statutes"] == 2
        assert row["n_reg_other_ref"] == 1
        assert row["n_reg_personnel"] == 0
        assert row["n_reg_precedents"] == 0
        assert row["n_reg_past_release"] == 1

    def test_n_reg_refs_total_is_sum_of_six_lanes(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        expected = (
            row["n_reg_rules"]
            + row["n_reg_statutes"]
            + row["n_reg_other_ref"]
            + row["n_reg_personnel"]
            + row["n_reg_precedents"]
            + row["n_reg_past_release"]
        )
        assert row["n_reg_refs_total"] == expected

    def test_n_critical_dates_and_n_reg_refs_total_counts(self, raw_envelope: dict):
        """n_critical_dates = populated key date types + n_other_dates."""
        row = _norm(raw_envelope)
        # Fixture: effective_date populated, comment_deadline populated, pub_date_content populated
        # compliance_date="", early_adoption_date="", updated_date="" → NA → 0
        # other_dates has 2 entries
        # n_critical_dates = 3 (key date types) + 2 (other_dates) = 5
        assert row["n_other_dates"] == 2
        assert row["n_critical_dates"] == 5

    def test_n_impacted_functions(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # 4 impacted_functions in fixture
        assert row["n_impacted_functions"] == 4

    def test_n_penalties(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # 2 penalties in fixture
        assert row["n_penalties"] == 2

    def test_empty_penalties_list_gives_zero(self, raw_envelope: dict):
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["metadata"]["penalties_consequences"] = []
        row = _norm(raw)
        assert row["n_penalties"] == 0
        assert row["has_penalties"] is False


# ---------------------------------------------------------------------------
# Presence flags
# ---------------------------------------------------------------------------


class TestPresenceFlags:
    def test_presence_flags_follow_na_rule(self, raw_envelope: dict):
        """Presence flags are True when the value is genuinely non-NA."""
        row = _norm(raw_envelope)
        # All 5 impact_summary parts are populated in fixture
        assert row["has_impact_summary"] is True
        assert row["has_objective"] is True
        assert row["has_what_changed"] is True
        assert row["has_why_it_matters"] is True
        assert row["has_risk_impact"] is True

    def test_has_impacted_business_when_present(self, raw_envelope: dict):
        """has_impacted_business is True when impacted_business has at least one populated field."""
        row = _norm(raw_envelope)
        assert row["has_impacted_business"] is True

    def test_has_impacted_business_false_when_all_empty(self, raw_envelope: dict):
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["metadata"]["impacted_business"] = {
            "industry": [], "type": [], "jurisdiction": [], "other_notes": []
        }
        row = _norm(raw)
        assert row["has_impacted_business"] is False

    def test_has_penalties_true_when_present(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["has_penalties"] is True

    def test_has_impact_summary_false_when_all_parts_empty(self, raw_envelope: dict):
        """has_impact_summary is False only when ALL 5 parts are NA."""
        raw = copy.deepcopy(raw_envelope)
        summary = raw["output_data"]["metadata"]["impact_summary"]
        for part in config.IMPACT_SUMMARY_PARTS:
            summary[part] = "" if part != "key_requirements" else []
        row = _norm(raw)
        assert row["has_impact_summary"] is False
        assert row["has_objective"] is False
        assert row["has_what_changed"] is False

    def test_has_objective_false_when_placeholder(self, raw_envelope: dict):
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["metadata"]["impact_summary"]["objective"] = "N/A"
        row = _norm(raw)
        assert row["has_objective"] is False


# ---------------------------------------------------------------------------
# Scores and classification nested mapping
# ---------------------------------------------------------------------------


class TestScoresAndClassificationMapping:
    def test_scores_and_classification_nested_mapping(self, raw_envelope: dict):
        """Nested paths in FIELD_MAP are correctly resolved."""
        row = _norm(raw_envelope)
        assert row["impact_label"] == "high"
        assert row["impact_score"] == 8.5
        assert row["impact_confidence"] == 0.9
        assert row["urgency_label"] == "medium"
        assert row["urgency_score"] == 5.0
        assert row["urgency_basis"] == "future_deadline"
        assert row["relevance_label"] == "high"
        assert row["relevance_score"] == 7.5

    def test_envelope_fields_mapped(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["artifact_id"] == "aaaabbbb-0000-0000-0000-000000000001"
        assert row["topic_id"] == "topic-finance-001"
        assert row["source_id"] == "src-0001"
        assert row["state"] == "completed"
        assert row["entry_id"] == "src-0001"

    def test_regulator_fields_mapped(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["regulator_name"] == "Financial Conduct Authority"
        assert row["regulator_division"] == "Prudential Policy Division"
        # other_agency is a list → take first or join; normalized to a string value
        assert row["regulator_other_agency"] is not None

    def test_jurisdiction_fields_mapped(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["jurisdiction_scope"] == "national"
        assert row["jurisdiction_country"] == "GB"
        assert pd.isna(row["jurisdiction_bloc"])  # "N/A" → NA
        assert row["jurisdiction_reasoning"] is not None


# ---------------------------------------------------------------------------
# title / feed_url from classification.metadata (probe-confirmed path)
# ---------------------------------------------------------------------------


class TestTitleAndFeedUrlFromClassificationMetadata:
    def test_title_and_feed_url_from_classification_metadata(self, raw_envelope: dict):
        """title and feed_url must come from output_data.classification.metadata,
        not from input_data.extracted_metadata — this is the probe-confirmed source path."""
        row = _norm(raw_envelope)
        assert row["title"] == "FCA Capital Requirements Update 2025"
        assert row["feed_url"] == "https://www.fca.org.uk/news/press-releases/fca-capital-update-2025"

    def test_base_url_derived_from_feed_url(self, raw_envelope: dict):
        """base_url is the registrable domain parsed from feed_url."""
        row = _norm(raw_envelope)
        # feed_url is https://www.fca.org.uk/...  → base_url should be "fca.org.uk"
        assert row["base_url"] == "fca.org.uk"

    def test_base_url_na_when_feed_url_empty(self, raw_envelope: dict):
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["classification"]["metadata"]["feed_url"] = ""
        row = _norm(raw)
        assert pd.isna(row["feed_url"])
        assert pd.isna(row["base_url"])

    def test_language_from_classification_metadata(self, raw_envelope: dict):
        """language comes from output_data.classification.metadata.language (a list → first item)."""
        row = _norm(raw_envelope)
        assert row["language"] == "en"

    def test_summary_from_classification_metadata(self, raw_envelope: dict):
        """summary comes from output_data.classification.metadata.summary."""
        row = _norm(raw_envelope)
        assert row["summary"] == "FCA updates capital adequacy requirements for UK banks."


# ---------------------------------------------------------------------------
# Reconciled published date
# ---------------------------------------------------------------------------


class TestReconciledPublishedDate:
    def test_reconciled_published_date_from_date_field(self, raw_envelope: dict):
        """Uses `reconciled_published_date.date` field, NOT `.value`."""
        row = _norm(raw_envelope)
        # The date is "2025-10-15" in the fixture
        rpd = row["reconciled_published_date"]
        assert rpd is not None and not (isinstance(rpd, float) and math.isnan(rpd))
        # Should be parseable as a date
        assert "2025" in str(rpd) or "2025-10-15" in str(rpd)

    def test_reconciled_pub_source(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["reconciled_pub_source"] == "content"

    def test_reconciled_pub_converted(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["reconciled_pub_converted"] is False

    def test_reconciled_pub_original_calendar(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["reconciled_pub_original_calendar"] == "gregorian"

    def test_reconciled_pub_valid(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["reconciled_pub_valid"] is True


# ---------------------------------------------------------------------------
# Date parsing and calendar pairing
# ---------------------------------------------------------------------------


class TestDateParseAndCalendarPairing:
    def test_date_parse_and_calendar_pairing(self, raw_envelope: dict):
        """Key dates are extracted; paired *_calendar fields are kept."""
        row = _norm(raw_envelope)
        # effective_date = "2026-01-01" (parseable)
        assert row["effective_date"] is not None and not pd.isna(row["effective_date"])
        assert row["effective_date_calendar"] == "gregorian"

    def test_empty_date_becomes_na(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        # compliance_date = "" → NA
        assert pd.isna(row["compliance_date"])
        assert pd.isna(row["compliance_date_calendar"])

    def test_n_other_dates_counts_list(self, raw_envelope: dict):
        row = _norm(raw_envelope)
        assert row["n_other_dates"] == 2


# ---------------------------------------------------------------------------
# has_jurisdiction_tier_legacy flag
# ---------------------------------------------------------------------------


class TestJurisdictionTierLegacyFlag:
    def test_jurisdiction_tier_legacy_flag_false_when_absent(self, raw_envelope: dict):
        """has_jurisdiction_tier_legacy is False when jurisdiction_tier is not in the envelope."""
        row = _norm(raw_envelope)
        assert row["has_jurisdiction_tier_legacy"] is False

    def test_jurisdiction_tier_legacy_flag(self, raw_envelope_with_legacy_tier: dict):
        """has_jurisdiction_tier_legacy is True when jurisdiction_tier field is present."""
        row = _norm(raw_envelope_with_legacy_tier)
        assert row["has_jurisdiction_tier_legacy"] is True


# ---------------------------------------------------------------------------
# richness_score — must remain NA (computed in Phase 4)
# ---------------------------------------------------------------------------


class TestRichnessScoreDeferred:
    def test_richness_score_is_na(self, raw_envelope: dict):
        """richness_score is NOT computed by normalize_record; it must be NA."""
        row = _norm(raw_envelope)
        assert pd.isna(row.get("richness_score", float("nan"))), (
            "normalize_record must leave richness_score as NA — it is materialized in Phase 4"
        )


# ---------------------------------------------------------------------------
# normalize_frame — column contract and category join
# ---------------------------------------------------------------------------


class TestNormalizeFrame:
    def test_frame_has_exactly_normalized_columns(self, raw_envelope: dict, categories_df: pd.DataFrame):
        """normalize_frame produces a DataFrame with exactly NORMALIZED_COLUMNS."""
        df = normalize.normalize_frame([raw_envelope], categories_df)
        assert list(df.columns) == schema.NORMALIZED_COLUMNS

    def test_category_left_join_most_specific_and_uncategorized_fallback(
        self, raw_envelope: dict, categories_df: pd.DataFrame
    ):
        """Category is joined from categories_df; unmapped topics → 'Uncategorized'."""
        # The raw_envelope has topic_id='topic-finance-001' which maps to 'Finance'
        unmapped_envelope = copy.deepcopy(raw_envelope)
        unmapped_envelope["id"] = "unmapped-001"
        unmapped_envelope["topic_id"] = "topic-not-in-catalog"

        df = normalize.normalize_frame([raw_envelope, unmapped_envelope], categories_df)

        # First row should have category = Finance
        assert df.loc[0, "category"] == "Finance"
        # Second row should have category = Uncategorized (not in categories_df)
        assert df.loc[1, "category"] == "Uncategorized"

    def test_frame_row_count_matches_inputs(self, raw_envelope: dict, categories_df: pd.DataFrame):
        """normalize_frame produces exactly one row per input record."""
        records = [raw_envelope, copy.deepcopy(raw_envelope)]
        records[1]["id"] = "aaaabbbb-0000-0000-0000-000000000002"
        df = normalize.normalize_frame(records, categories_df)
        assert len(df) == 2

    def test_frame_no_extra_columns(self, raw_envelope: dict, categories_df: pd.DataFrame):
        """normalize_frame must not produce any columns outside NORMALIZED_COLUMNS."""
        df = normalize.normalize_frame([raw_envelope], categories_df)
        extra = set(df.columns) - set(schema.NORMALIZED_COLUMNS)
        assert not extra, f"Unexpected extra columns: {sorted(extra)}"


# ---------------------------------------------------------------------------
# Phase 4 quality support columns: min_prose_len, n_unparseable_dates
# ---------------------------------------------------------------------------


class TestMinProseLen:
    def test_min_prose_len_with_all_parts_populated(self, raw_envelope: dict):
        """min_prose_len is the shortest prose part length when all are populated."""
        row = _norm(raw_envelope)
        # All 4 text parts are populated in the fixture; min_prose_len must be
        # a positive integer ≥ 1
        min_len = row["min_prose_len"]
        assert not pd.isna(min_len), "min_prose_len should not be NA when prose parts present"
        assert isinstance(min_len, int) or (hasattr(min_len, '__int__') and not pd.isna(min_len))
        assert min_len > 0

    def test_min_prose_len_reflects_shortest_part(self, raw_envelope: dict):
        """min_prose_len equals the length of the shortest prose part."""
        raw = copy.deepcopy(raw_envelope)
        # Set a very short objective to be the minimum
        short_text = "Hi."
        raw["output_data"]["metadata"]["impact_summary"]["objective"] = short_text
        row = _norm(raw)
        assert row["min_prose_len"] == len(short_text), (
            f"Expected min_prose_len={len(short_text)}, got {row['min_prose_len']}"
        )

    def test_min_prose_len_na_when_no_prose(self, raw_envelope: dict):
        """min_prose_len is NA when no prose parts are present."""
        raw = copy.deepcopy(raw_envelope)
        summary = raw["output_data"]["metadata"]["impact_summary"]
        for part in config.IMPACT_SUMMARY_PARTS:
            summary[part] = "" if part != "key_requirements" else []
        row = _norm(raw)
        assert pd.isna(row["min_prose_len"]), (
            "min_prose_len should be NA when all prose parts are missing"
        )

    def test_min_prose_len_includes_key_requirements_joined(self, raw_envelope: dict):
        """key_requirements items are joined and their length is considered for min_prose_len."""
        raw = copy.deepcopy(raw_envelope)
        summary = raw["output_data"]["metadata"]["impact_summary"]
        # Clear text parts but keep key_requirements
        summary["objective"] = ""
        summary["what_changed"] = ""
        summary["why_it_matters"] = ""
        summary["risk_impact"] = ""
        summary["key_requirements"] = ["Requirement A", "Requirement B"]
        row = _norm(raw)
        # min_prose_len should be length of "Requirement A Requirement B" (joined)
        expected = len("Requirement A Requirement B")
        assert row["min_prose_len"] == expected, (
            f"Expected min_prose_len={expected}, got {row['min_prose_len']}"
        )


class TestNUnparseableDates:
    def test_n_unparseable_dates_zero_when_all_valid(self, raw_envelope: dict):
        """n_unparseable_dates=0 when all date fields are valid or empty."""
        row = _norm(raw_envelope)
        assert row["n_unparseable_dates"] == 0, (
            f"Expected n_unparseable_dates=0, got {row['n_unparseable_dates']}"
        )

    def test_n_unparseable_dates_counts_garbage_date(self, raw_envelope: dict):
        """A garbage date string like '2026-13-45' must increment n_unparseable_dates."""
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["metadata"]["critical_dates"]["effective_date"] = "2026-13-45"
        row = _norm(raw)
        assert row["n_unparseable_dates"] >= 1, (
            f"Expected n_unparseable_dates >= 1 for garbage date, got {row['n_unparseable_dates']}"
        )

    def test_n_unparseable_dates_empty_not_counted(self, raw_envelope: dict):
        """An empty date string must NOT be counted as unparseable."""
        raw = copy.deepcopy(raw_envelope)
        raw["output_data"]["metadata"]["critical_dates"]["compliance_date"] = ""
        row = _norm(raw)
        # compliance_date was already empty in the fixture → still 0
        assert row["n_unparseable_dates"] == 0

    def test_n_unparseable_dates_multiple_bad_dates(self, raw_envelope: dict):
        """Multiple garbage dates are each counted individually."""
        raw = copy.deepcopy(raw_envelope)
        critical_dates = raw["output_data"]["metadata"]["critical_dates"]
        critical_dates["effective_date"] = "not-a-date"
        critical_dates["comment_deadline"] = "99/99/9999"
        row = _norm(raw)
        assert row["n_unparseable_dates"] >= 2, (
            f"Expected n_unparseable_dates >= 2, got {row['n_unparseable_dates']}"
        )
