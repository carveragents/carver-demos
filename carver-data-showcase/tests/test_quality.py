"""Tests for carver_showcase/quality.py.

All tests are deterministic — no LLM, no network, no real data load.
Crafted in-memory frames only.

Each test is engineered to trigger exactly one predicate or anomaly rule.

Tests per predicate (9):
  test_predicate_missing_core_score
  test_predicate_missing_join_key
  test_predicate_missing_feed_url
  test_predicate_missing_jurisdiction_country
  test_predicate_missing_update_type
  test_predicate_no_impact_summary
  test_predicate_short_prose
  test_predicate_no_actionables
  test_predicate_empty_but_expected

Tests per anomaly rule (11):
  test_score_out_of_range
  test_label_score_mismatch
  test_date_order_inconsistency
  test_implausible_pub_date_2105
  test_invalid_reconciled_date_valid_false
  test_duplicate_entry_id
  test_invalid_jurisdiction_country
  test_residual_legacy_field
  test_update_type_rare
  test_regulator_near_duplicate_canonicalization
  test_unparseable_date

Plus:
  test_cleanup_queue_includes_any_failing_predicate
"""

from __future__ import annotations

import pandas as pd
import pytest

from carver_showcase.quality import anomaly_report, cleanup_queue, predicate_flags


# ---------------------------------------------------------------------------
# Helpers — build minimal normalized rows
# ---------------------------------------------------------------------------

_BASE_ROW = {
    "artifact_id": "art-0001",
    "entry_id": "ent-0001",
    "topic_id": "topic-001",
    "feed_url": "https://example.com/doc.html",
    "jurisdiction_country": "US",
    "update_type": "Regulatory Update",
    # Impact summary: all present, long enough
    "has_impact_summary": True,
    "has_objective": True,
    "has_what_changed": True,
    "has_why_it_matters": True,
    "has_risk_impact": True,
    "n_key_requirements": 2,
    "min_prose_len": 80,          # > MIN_PROSE_CHARS → not short
    # Actionables
    "n_actionable_lanes": 3,
    # Scores
    "impact_label": "high",
    "impact_score": 8.0,
    "impact_confidence": 0.9,
    "urgency_label": "low",
    "urgency_score": 1.0,
    "urgency_confidence": 0.85,
    "relevance_label": "high",
    "relevance_score": 7.5,
    "relevance_confidence": 0.8,
    # Dates (stored as strings; None for unpopulated)
    "effective_date": "2026-01-01",
    "compliance_date": None,
    "comment_deadline": None,
    "reconciled_published_date": pd.Timestamp("2025-01-15", tz="UTC"),
    "reconciled_pub_valid": True,
    # Jurisdiction
    "has_jurisdiction_tier_legacy": False,
    # Other
    "regulator_name": "Financial Conduct Authority",
    "richness_score": 65.0,
    "n_unparseable_dates": 0,
}


def _row(**overrides) -> dict:
    """Return a copy of _BASE_ROW with the given overrides applied."""
    import copy
    r = copy.deepcopy(_BASE_ROW)
    r.update(overrides)
    return r


def _df(*rows) -> pd.DataFrame:
    """Build a DataFrame from one or more row dicts."""
    return pd.DataFrame(list(rows))


def _good_df(n: int = 3) -> pd.DataFrame:
    """A DataFrame with n clean rows (no flags, no anomalies)."""
    rows = [_row(
        artifact_id=f"art-{i:04d}",
        entry_id=f"ent-{i:04d}",
        regulator_name=f"Regulator {i}",
    ) for i in range(n)]
    return _df(*rows)


# ===========================================================================
# PART 1 — predicate_flags (9 predicates)
# ===========================================================================


class TestPredicateMissingCoreScore:
    def test_predicate_missing_core_score_false_when_all_present(self):
        """A row with all 9 score fields populated must not flag missing_core_score."""
        df = _df(_row())
        flags = predicate_flags(df)
        assert not flags["missing_core_score"].iloc[0]

    def test_predicate_missing_core_score_true_when_label_na(self):
        """A row missing one axis's label must flag missing_core_score."""
        df = _df(_row(impact_label=None))
        flags = predicate_flags(df)
        assert flags["missing_core_score"].iloc[0]

    def test_predicate_missing_core_score_true_when_score_na(self):
        """A row missing one axis's score must flag missing_core_score."""
        df = _df(_row(urgency_score=None))
        flags = predicate_flags(df)
        assert flags["missing_core_score"].iloc[0]

    def test_predicate_missing_core_score_true_when_confidence_na(self):
        """A row missing one confidence must flag missing_core_score."""
        df = _df(_row(relevance_confidence=None))
        flags = predicate_flags(df)
        assert flags["missing_core_score"].iloc[0]


class TestPredicateMissingJoinKey:
    def test_predicate_missing_join_key_false_when_both_present(self):
        df = _df(_row())
        flags = predicate_flags(df)
        assert not flags["missing_join_key"].iloc[0]

    def test_predicate_missing_join_key_true_when_topic_id_na(self):
        df = _df(_row(topic_id=None))
        flags = predicate_flags(df)
        assert flags["missing_join_key"].iloc[0]

    def test_predicate_missing_join_key_true_when_entry_id_na(self):
        df = _df(_row(entry_id=None))
        flags = predicate_flags(df)
        assert flags["missing_join_key"].iloc[0]


class TestPredicateMissingFeedUrl:
    def test_predicate_missing_feed_url_false_when_present(self):
        df = _df(_row())
        flags = predicate_flags(df)
        assert not flags["missing_feed_url"].iloc[0]

    def test_predicate_missing_feed_url_true_when_na(self):
        df = _df(_row(feed_url=None))
        flags = predicate_flags(df)
        assert flags["missing_feed_url"].iloc[0]


class TestPredicateMissingJurisdictionCountry:
    def test_predicate_missing_jurisdiction_country_false_when_present(self):
        df = _df(_row())
        flags = predicate_flags(df)
        assert not flags["missing_jurisdiction_country"].iloc[0]

    def test_predicate_missing_jurisdiction_country_true_when_na(self):
        df = _df(_row(jurisdiction_country=None))
        flags = predicate_flags(df)
        assert flags["missing_jurisdiction_country"].iloc[0]


class TestPredicateMissingUpdateType:
    def test_predicate_missing_update_type_false_when_present(self):
        df = _df(_row())
        flags = predicate_flags(df)
        assert not flags["missing_update_type"].iloc[0]

    def test_predicate_missing_update_type_true_when_na(self):
        df = _df(_row(update_type=None))
        flags = predicate_flags(df)
        assert flags["missing_update_type"].iloc[0]


class TestPredicateNoImpactSummary:
    def test_predicate_no_impact_summary_false_when_present(self):
        df = _df(_row())
        flags = predicate_flags(df)
        assert not flags["no_impact_summary"].iloc[0]

    def test_predicate_no_impact_summary_true_when_all_parts_missing(self):
        df = _df(_row(
            has_impact_summary=False,
            has_objective=False,
            has_what_changed=False,
            has_why_it_matters=False,
            has_risk_impact=False,
            n_key_requirements=0,
        ))
        flags = predicate_flags(df)
        assert flags["no_impact_summary"].iloc[0]


class TestPredicateShortProse:
    def test_predicate_short_prose_false_when_long_enough(self):
        """min_prose_len ≥ MIN_PROSE_CHARS → no short_prose flag."""
        df = _df(_row(has_impact_summary=True, min_prose_len=80))
        flags = predicate_flags(df)
        assert not flags["short_prose"].iloc[0]

    def test_predicate_short_prose_true_when_min_prose_short(self):
        """min_prose_len < MIN_PROSE_CHARS AND has_impact_summary → short_prose."""
        df = _df(_row(has_impact_summary=True, min_prose_len=5))
        flags = predicate_flags(df)
        assert flags["short_prose"].iloc[0]

    def test_predicate_short_prose_false_when_no_impact_summary(self):
        """If has_impact_summary is False, short_prose must not fire (no prose to be short)."""
        df = _df(_row(has_impact_summary=False, min_prose_len=None))
        flags = predicate_flags(df)
        assert not flags["short_prose"].iloc[0]


class TestPredicateNoActionables:
    def test_predicate_no_actionables_false_when_lanes_populated(self):
        df = _df(_row(n_actionable_lanes=3))
        flags = predicate_flags(df)
        assert not flags["no_actionables"].iloc[0]

    def test_predicate_no_actionables_true_when_zero_lanes(self):
        df = _df(_row(n_actionable_lanes=0))
        flags = predicate_flags(df)
        assert flags["no_actionables"].iloc[0]


class TestPredicateEmptyButExpected:
    def test_predicate_empty_but_expected_false_when_fine(self):
        """High-impact record WITH impact summary and actionables → not flagged."""
        df = _df(_row(
            impact_label="high",
            relevance_label="high",
            has_impact_summary=True,
            n_actionable_lanes=3,
        ))
        flags = predicate_flags(df)
        assert not flags["empty_but_expected"].iloc[0]

    def test_predicate_empty_but_expected_true_for_high_impact_no_summary(self):
        """High impact label but no impact_summary → empty_but_expected fires."""
        df = _df(_row(
            impact_label="high",
            has_impact_summary=False,
            n_actionable_lanes=3,
        ))
        flags = predicate_flags(df)
        assert flags["empty_but_expected"].iloc[0]

    def test_predicate_empty_but_expected_true_for_high_impact_no_actionables(self):
        """High impact label but no actionables → empty_but_expected fires."""
        df = _df(_row(
            impact_label="high",
            has_impact_summary=True,
            n_actionable_lanes=0,
        ))
        flags = predicate_flags(df)
        assert flags["empty_but_expected"].iloc[0]

    def test_predicate_empty_but_expected_true_for_high_relevance_no_summary(self):
        """High relevance label but no impact_summary → empty_but_expected fires."""
        df = _df(_row(
            impact_label="medium",
            relevance_label="high",
            has_impact_summary=False,
            n_actionable_lanes=3,
        ))
        flags = predicate_flags(df)
        assert flags["empty_but_expected"].iloc[0]

    def test_predicate_empty_but_expected_false_for_low_impact_no_summary(self):
        """Low impact label with no summary → NOT empty_but_expected (low is OK to be sparse)."""
        df = _df(_row(
            impact_label="low",
            relevance_label="low",
            has_impact_summary=False,
            n_actionable_lanes=0,
        ))
        flags = predicate_flags(df)
        assert not flags["empty_but_expected"].iloc[0]

    def test_predicate_flags_returns_dataframe_of_booleans(self):
        """predicate_flags must return a DataFrame with boolean dtype columns."""
        df = _good_df(5)
        flags = predicate_flags(df)
        assert isinstance(flags, pd.DataFrame)
        for col in flags.columns:
            # Allow both bool and boolean (nullable) dtypes
            assert flags[col].dtype in (
                "bool", "boolean"
            ) or str(flags[col].dtype) in ("bool", "boolean"), (
                f"Column '{col}' has non-boolean dtype: {flags[col].dtype}"
            )

    def test_predicate_flags_has_nine_columns(self):
        """predicate_flags must return exactly 9 predicate columns."""
        df = _good_df(2)
        flags = predicate_flags(df)
        expected = {
            "missing_core_score",
            "missing_join_key",
            "missing_feed_url",
            "missing_jurisdiction_country",
            "missing_update_type",
            "no_impact_summary",
            "short_prose",
            "no_actionables",
            "empty_but_expected",
        }
        assert set(flags.columns) == expected


# ===========================================================================
# PART 2 — anomaly_report (11 rules)
# ===========================================================================


class TestAnomalyScoreOutOfRange:
    def test_score_out_of_range_clean_row(self):
        """A row with valid scores must not appear in score_out_of_range."""
        df = _good_df(3)
        report = anomaly_report(df)
        assert report["score_out_of_range"]["count"] == 0

    def test_score_out_of_range_impact_score_above_10(self):
        """impact_score > 10 must be flagged."""
        df = _df(_row(impact_score=11.0))
        report = anomaly_report(df)
        assert report["score_out_of_range"]["count"] >= 1

    def test_score_out_of_range_confidence_above_1(self):
        """Any confidence > 1.0 must be flagged."""
        df = _df(_row(impact_confidence=1.5))
        report = anomaly_report(df)
        assert report["score_out_of_range"]["count"] >= 1

    def test_score_out_of_range_negative_score(self):
        """Negative scores must be flagged."""
        df = _df(_row(urgency_score=-1.0))
        report = anomaly_report(df)
        assert report["score_out_of_range"]["count"] >= 1


class TestAnomalyLabelScoreMismatch:
    def test_label_score_mismatch_clean_row(self):
        """'high' label with score 8.0 → no mismatch."""
        df = _df(_row(impact_label="high", impact_score=8.0))
        report = anomaly_report(df)
        mismatch_ids = report["label_score_mismatch"]["records"]["artifact_id"].tolist()
        assert "art-0001" not in mismatch_ids

    def test_label_score_mismatch_high_label_with_low_score(self):
        """'high' label with score 2.0 (falls in low band) → mismatch."""
        df = _df(_row(artifact_id="mismatch-001",
                      impact_label="high", impact_score=2.0))
        report = anomaly_report(df)
        assert report["label_score_mismatch"]["count"] >= 1

    def test_label_score_mismatch_low_label_with_high_score(self):
        """'low' label with score 9.0 (falls in high band) → mismatch."""
        df = _df(_row(artifact_id="mismatch-002",
                      urgency_label="low", urgency_score=9.0))
        report = anomaly_report(df)
        assert report["label_score_mismatch"]["count"] >= 1

    def test_label_score_mismatch_medium_label_with_score_5(self):
        """'medium' label with score 5.0 → no mismatch (5.0 is in [4,7))."""
        df = _df(_row(impact_label="medium", impact_score=5.0))
        report = anomaly_report(df)
        mismatch_records = report["label_score_mismatch"]["records"]
        assert "art-0001" not in mismatch_records["artifact_id"].tolist()

    def test_label_score_mismatch_label_present_na_score_no_mismatch(self):
        """A present label with a missing (NA) score is NOT a mismatch — it's
        caught by missing_core_score. Guards the score-presence condition."""
        df = _df(_row(artifact_id="na-score-001",
                      impact_label="high", impact_score=pd.NA))
        report = anomaly_report(df)
        ids = report["label_score_mismatch"]["records"]["artifact_id"].tolist()
        assert "na-score-001" not in ids

    def test_label_score_mismatch_high_label_with_score_10(self):
        """'high' label with score 10.0 (inclusive upper boundary) → no mismatch."""
        df = _df(_row(impact_label="high", impact_score=10.0))
        report = anomaly_report(df)
        records = report["label_score_mismatch"]["records"]
        assert "art-0001" not in records["artifact_id"].tolist()


class TestAnomalyDateOrderInconsistency:
    def test_date_order_clean(self):
        """comment_deadline < effective_date (good order) → no flag."""
        df = _df(_row(
            comment_deadline="2025-12-01",
            effective_date="2026-01-01",
        ))
        report = anomaly_report(df)
        assert report["date_order_inconsistency"]["count"] == 0

    def test_date_order_comment_deadline_after_effective_date(self):
        """comment_deadline > effective_date → date_order_inconsistency."""
        df = _df(_row(
            artifact_id="date-order-001",
            comment_deadline="2026-06-01",
            effective_date="2026-01-01",
        ))
        report = anomaly_report(df)
        assert report["date_order_inconsistency"]["count"] >= 1

    def test_date_order_compliance_before_effective(self):
        """compliance_date < effective_date → date_order_inconsistency."""
        df = _df(_row(
            artifact_id="date-order-002",
            compliance_date="2025-06-01",
            effective_date="2026-01-01",
        ))
        report = anomaly_report(df)
        assert report["date_order_inconsistency"]["count"] >= 1


class TestAnomalyImplausiblePubDate:
    def test_implausible_pub_date_clean(self):
        """A 2025 pub date is plausible."""
        df = _df(_row(
            reconciled_published_date=pd.Timestamp("2025-06-01", tz="UTC"),
        ))
        report = anomaly_report(df)
        assert report["implausible_pub_date"]["count"] == 0

    def test_implausible_pub_date_2105(self):
        """A 2105 pub date must be flagged as implausible."""
        df = _df(_row(
            artifact_id="implausible-001",
            reconciled_published_date=pd.Timestamp("2105-07-01", tz="UTC"),
        ))
        report = anomaly_report(df)
        assert report["implausible_pub_date"]["count"] >= 1

    def test_implausible_pub_date_1947(self):
        """A 1947 pub date must be flagged as implausible (before 1990)."""
        df = _df(_row(
            artifact_id="implausible-002",
            reconciled_published_date=pd.Timestamp("1947-12-25", tz="UTC"),
        ))
        report = anomaly_report(df)
        assert report["implausible_pub_date"]["count"] >= 1


class TestAnomalyInvalidReconciledDate:
    def test_invalid_reconciled_date_clean(self):
        """reconciled_pub_valid=True → not flagged."""
        df = _df(_row(reconciled_pub_valid=True))
        report = anomaly_report(df)
        assert report["invalid_reconciled_date"]["count"] == 0

    def test_invalid_reconciled_date_valid_false(self):
        """reconciled_pub_valid=False → flagged."""
        df = _df(_row(artifact_id="invalid-date-001", reconciled_pub_valid=False))
        report = anomaly_report(df)
        assert report["invalid_reconciled_date"]["count"] >= 1


class TestAnomalyDuplicateEntryId:
    def test_duplicate_entry_id_clean(self):
        """Distinct entry_ids → no duplicate flag."""
        df = _df(
            _row(artifact_id="a1", entry_id="e1"),
            _row(artifact_id="a2", entry_id="e2"),
        )
        report = anomaly_report(df)
        assert report["duplicate_entry_id"]["count"] == 0

    def test_duplicate_entry_id(self):
        """Same entry_id on two rows → both flagged."""
        df = _df(
            _row(artifact_id="dup-001", entry_id="shared-entry"),
            _row(artifact_id="dup-002", entry_id="shared-entry"),
            _row(artifact_id="clean-003", entry_id="unique-entry"),
        )
        report = anomaly_report(df)
        # Both rows with "shared-entry" should be returned
        assert report["duplicate_entry_id"]["count"] == 2


class TestAnomalyInvalidJurisdictionCountry:
    def test_invalid_jurisdiction_country_clean(self):
        """Known ISO-2 code → not flagged."""
        df = _df(_row(jurisdiction_country="US"))
        report = anomaly_report(df)
        records = report["invalid_jurisdiction_country"]["records"]
        assert "art-0001" not in records["artifact_id"].tolist()

    def test_invalid_jurisdiction_country_bad_code(self):
        """Unknown country code → flagged."""
        df = _df(_row(artifact_id="bad-country-001", jurisdiction_country="XX"))
        report = anomaly_report(df)
        assert report["invalid_jurisdiction_country"]["count"] >= 1

    def test_invalid_jurisdiction_country_na_not_flagged(self):
        """NA jurisdiction_country → NOT flagged (rule is only for non-NA values)."""
        df = _df(_row(jurisdiction_country=None))
        report = anomaly_report(df)
        assert report["invalid_jurisdiction_country"]["count"] == 0


class TestAnomalyResidualLegacyField:
    def test_residual_legacy_field_clean(self):
        """has_jurisdiction_tier_legacy=False → not flagged."""
        df = _df(_row(has_jurisdiction_tier_legacy=False))
        report = anomaly_report(df)
        assert report["residual_legacy_field"]["count"] == 0

    def test_residual_legacy_field_true(self):
        """has_jurisdiction_tier_legacy=True → flagged."""
        df = _df(_row(artifact_id="legacy-001", has_jurisdiction_tier_legacy=True))
        report = anomaly_report(df)
        assert report["residual_legacy_field"]["count"] >= 1


class TestAnomalyUpdateTypeRare:
    def test_update_type_rare_common_type(self):
        """An update_type appearing many times → not rare."""
        rows = [_row(artifact_id=f"a{i}", entry_id=f"e{i}",
                     update_type="Common Type") for i in range(20)]
        df = _df(*rows)
        report = anomaly_report(df)
        # "Common Type" appears 20 times → above RARE_UPDATE_TYPE_CUTOFF
        assert report["update_type_rare"]["count"] == 0

    def test_update_type_rare_rare_type(self):
        """An update_type appearing fewer times than RARE_UPDATE_TYPE_CUTOFF → flagged."""
        from carver_showcase.config import RARE_UPDATE_TYPE_CUTOFF
        # Create one row with a very rare update_type
        rows = [_row(artifact_id=f"a{i}", entry_id=f"e{i}",
                     update_type="Common Type") for i in range(20)]
        rows.append(_row(artifact_id="rare-001", entry_id="e-rare",
                         update_type="Very Rare Type"))
        df = _df(*rows)
        report = anomaly_report(df)
        # "Very Rare Type" appears 1 time (< RARE_UPDATE_TYPE_CUTOFF)
        assert report["update_type_rare"]["count"] >= 1
        rare_records = report["update_type_rare"]["records"]
        assert "rare-001" in rare_records["artifact_id"].tolist()


class TestAnomalyRegulatorNearDuplicate:
    def test_regulator_near_duplicate_distinct_names(self):
        """Completely different regulator names → no near-duplicate."""
        df = _df(
            _row(artifact_id="a1", entry_id="e1", regulator_name="Financial Conduct Authority"),
            _row(artifact_id="a2", entry_id="e2", regulator_name="European Central Bank"),
            _row(artifact_id="a3", entry_id="e3", regulator_name="Bank of England"),
        )
        report = anomaly_report(df)
        assert report["regulator_near_duplicate"]["count"] == 0

    def test_regulator_near_duplicate_canonicalization(self):
        """Two regulator names that differ only in punctuation/case/legal suffix
        must collapse to the same canonical form → near-duplicate flagged."""
        df = _df(
            _row(artifact_id="nd-001", entry_id="e1",
                 regulator_name="Financial Conduct Authority"),
            _row(artifact_id="nd-002", entry_id="e2",
                 regulator_name="Financial Conduct Authority Ltd"),
            _row(artifact_id="nd-003", entry_id="e3",
                 regulator_name="financial conduct authority"),
        )
        report = anomaly_report(df)
        # All three canonicalize to the same form → all 3 are near-duplicates
        assert report["regulator_near_duplicate"]["count"] >= 2

    def test_regulator_near_duplicate_punctuation_difference(self):
        """Names differing only in punctuation collapse together → near-duplicate."""
        df = _df(
            _row(artifact_id="nd-punct-1", entry_id="e1",
                 regulator_name="U.S. Securities and Exchange Commission"),
            _row(artifact_id="nd-punct-2", entry_id="e2",
                 regulator_name="US Securities and Exchange Commission"),
        )
        report = anomaly_report(df)
        assert report["regulator_near_duplicate"]["count"] >= 1

    def test_regulator_near_duplicate_na_not_included(self):
        """NA regulator_name rows must not be included in near-duplicate analysis."""
        df = _df(
            _row(artifact_id="na-1", entry_id="e1", regulator_name=None),
            _row(artifact_id="na-2", entry_id="e2", regulator_name=None),
        )
        report = anomaly_report(df)
        assert report["regulator_near_duplicate"]["count"] == 0


class TestAnomalyUnparseableDate:
    def test_unparseable_date_clean(self):
        """n_unparseable_dates=0 → not flagged."""
        df = _df(_row(n_unparseable_dates=0))
        report = anomaly_report(df)
        assert report["unparseable_date"]["count"] == 0

    def test_unparseable_date_flagged(self):
        """n_unparseable_dates > 0 → flagged."""
        df = _df(_row(artifact_id="unparseable-001", n_unparseable_dates=2))
        report = anomaly_report(df)
        assert report["unparseable_date"]["count"] >= 1


class TestAnomalyReportStructure:
    def test_anomaly_report_has_all_11_keys(self):
        """anomaly_report must return a dict with all 11 rule keys."""
        df = _good_df(3)
        report = anomaly_report(df)
        expected_keys = {
            "score_out_of_range",
            "label_score_mismatch",
            "date_order_inconsistency",
            "implausible_pub_date",
            "invalid_reconciled_date",
            "duplicate_entry_id",
            "invalid_jurisdiction_country",
            "residual_legacy_field",
            "update_type_rare",
            "regulator_near_duplicate",
            "unparseable_date",
        }
        assert set(report.keys()) == expected_keys

    def test_anomaly_report_each_value_has_count_and_records(self):
        """Each rule's value must have 'count' (int) and 'records' (DataFrame)."""
        df = _good_df(3)
        report = anomaly_report(df)
        for rule, value in report.items():
            assert "count" in value, f"Rule '{rule}' missing 'count'"
            assert "records" in value, f"Rule '{rule}' missing 'records'"
            assert isinstance(value["count"], int), f"Rule '{rule}' count is not int"
            assert isinstance(value["records"], pd.DataFrame), (
                f"Rule '{rule}' records is not DataFrame"
            )


# ===========================================================================
# PART 3 — cleanup_queue
# ===========================================================================


class TestCleanupQueue:
    def test_cleanup_queue_includes_any_failing_predicate(self):
        """cleanup_queue must include rows that fail at least one predicate."""
        rows = [
            _row(artifact_id="clean-001", entry_id="e1"),           # all good
            _row(artifact_id="dirty-002", entry_id="e2",
                 feed_url=None),                                      # missing_feed_url
            _row(artifact_id="dirty-003", entry_id="e3",
                 jurisdiction_country=None),                          # missing_jurisdiction_country
            _row(artifact_id="clean-004", entry_id="e4"),            # all good
        ]
        df = _df(*rows)
        queue = cleanup_queue(df)
        # dirty-002 and dirty-003 must appear
        queue_ids = set(queue["artifact_id"].tolist())
        assert "dirty-002" in queue_ids
        assert "dirty-003" in queue_ids
        # clean rows must NOT appear
        assert "clean-001" not in queue_ids
        assert "clean-004" not in queue_ids

    def test_cleanup_queue_contains_required_columns(self):
        """cleanup_queue must include artifact_id, failed_predicates, and feed_url."""
        rows = [_row(artifact_id="a1", entry_id="e1", feed_url=None)]
        df = _df(*rows)
        queue = cleanup_queue(df)
        assert "artifact_id" in queue.columns
        assert "failed_predicates" in queue.columns
        assert "feed_url" in queue.columns

    def test_cleanup_queue_failed_predicates_is_list(self):
        """failed_predicates column must be a list-like containing the predicate names."""
        rows = [_row(artifact_id="a1", entry_id="e1",
                     feed_url=None, jurisdiction_country=None)]
        df = _df(*rows)
        queue = cleanup_queue(df)
        # The row fails missing_feed_url AND missing_jurisdiction_country
        fp = queue.iloc[0]["failed_predicates"]
        assert "missing_feed_url" in fp
        assert "missing_jurisdiction_country" in fp

    def test_cleanup_queue_empty_when_all_clean(self):
        """If no rows fail any predicate, cleanup_queue must return an empty DataFrame."""
        df = _good_df(5)
        queue = cleanup_queue(df)
        assert len(queue) == 0

    def test_cleanup_queue_predicate_filter(self):
        """When predicates= is specified, only rows failing those predicates are returned."""
        rows = [
            _row(artifact_id="url-miss", entry_id="e1", feed_url=None),
            _row(artifact_id="country-miss", entry_id="e2", jurisdiction_country=None),
        ]
        df = _df(*rows)
        queue = cleanup_queue(df, predicates=["missing_feed_url"])
        ids = queue["artifact_id"].tolist()
        assert "url-miss" in ids
        assert "country-miss" not in ids
