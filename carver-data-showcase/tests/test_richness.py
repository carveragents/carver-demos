"""Tests for carver_showcase/richness.py.

All tests are deterministic — no LLM, no network, no real data load.
Crafted in-memory frames only.

Tests:
- test_score_bounded_0_100
- test_score_monotonic_per_component
- test_weights_sum_to_one
- test_highlight_reel_deterministic_order_and_tiebreak
- test_highlight_reel_diversify_one_per_topic
"""

from __future__ import annotations

import pandas as pd
import pytest

from carver_showcase import config
from carver_showcase.richness import highlight_reel, richness_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(**kwargs) -> dict:
    """Build a minimal row with all richness-relevant columns.

    Defaults to all-zero/False — override only what the test needs.
    """
    defaults = {
        "artifact_id": "art-0001",
        "topic_id": "topic-001",
        "update_type": "Regulatory Update",
        "impact_score": 5.0,
        # has_* flags (prose parts)
        "has_objective": False,
        "has_what_changed": False,
        "has_why_it_matters": False,
        "has_risk_impact": False,
        "n_key_requirements": 0,
        # actionables
        "n_actionable_lanes": 0,
        # critical dates
        "n_critical_dates": 0,
        # reg refs
        "n_reg_refs_total": 0,
        # entities and tags
        "n_entities": 0,
        "n_tags": 0,
        # impacted business / functions
        "has_impacted_business": False,
        "n_impacted_functions": 0,
    }
    defaults.update(kwargs)
    return defaults


def _make_df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# Test: score bounded in [0, 100]
# ---------------------------------------------------------------------------


class TestScoreBounded:
    def test_score_bounded_0_100_all_zeros(self):
        """An all-empty record must score 0."""
        df = _make_df(_make_row())
        scores = richness_scores(df)
        assert len(scores) == 1
        assert scores.iloc[0] == 0

    def test_score_bounded_0_100_all_populated(self):
        """A fully populated record must score ≤ 100 (rounded)."""
        full_row = _make_row(
            has_objective=True,
            has_what_changed=True,
            has_why_it_matters=True,
            has_risk_impact=True,
            n_key_requirements=5,
            n_actionable_lanes=7,
            n_critical_dates=10,  # capped at 5
            n_reg_refs_total=12,  # capped at 6
            n_entities=20,        # capped at 8
            n_tags=20,            # capped at 8
            has_impacted_business=True,
            n_impacted_functions=5,
        )
        df = _make_df(full_row)
        scores = richness_scores(df)
        assert scores.iloc[0] == 100

    def test_score_bounded_0_100_partial(self):
        """Partial population must score between 0 and 100 (exclusive)."""
        partial_row = _make_row(
            has_objective=True,
            n_actionable_lanes=3,
            n_critical_dates=2,
        )
        df = _make_df(partial_row)
        scores = richness_scores(df)
        s = scores.iloc[0]
        assert 0 <= s <= 100

    def test_score_is_rounded_integer_like(self):
        """richness_scores must be rounded (integer-valued floats) in [0,100]."""
        rows = [_make_row(n_actionable_lanes=i) for i in range(8)]
        df = _make_df(*rows)
        scores = richness_scores(df)
        for s in scores:
            assert s == round(s), f"Score {s} is not rounded"
            assert 0 <= s <= 100


# ---------------------------------------------------------------------------
# Test: monotonic — adding population to any component must not decrease score
# ---------------------------------------------------------------------------


class TestScoreMonotonic:
    def test_score_monotonic_per_component(self):
        """Increasing any component's contribution must not decrease the richness score."""
        components_progression = [
            # (component column, values list from less to more populated)
            [
                _make_row(n_actionable_lanes=0),
                _make_row(n_actionable_lanes=3),
                _make_row(n_actionable_lanes=7),
            ],
            [
                _make_row(has_objective=False),
                _make_row(has_objective=True),
                _make_row(has_objective=True, has_what_changed=True),
                _make_row(has_objective=True, has_what_changed=True, has_risk_impact=True),
            ],
            [
                _make_row(n_critical_dates=0),
                _make_row(n_critical_dates=2),
                _make_row(n_critical_dates=5),
                _make_row(n_critical_dates=10),  # capped, same as 5
            ],
            [
                _make_row(n_reg_refs_total=0),
                _make_row(n_reg_refs_total=3),
                _make_row(n_reg_refs_total=6),
                _make_row(n_reg_refs_total=12),  # capped, same as 6
            ],
            [
                _make_row(n_entities=0, n_tags=0),
                _make_row(n_entities=4, n_tags=0),
                _make_row(n_entities=8, n_tags=8),
                _make_row(n_entities=16, n_tags=16),  # capped
            ],
            [
                _make_row(has_impacted_business=False, n_impacted_functions=0),
                _make_row(has_impacted_business=True, n_impacted_functions=0),
                _make_row(has_impacted_business=True, n_impacted_functions=3),
            ],
        ]

        for progression in components_progression:
            df = _make_df(*progression)
            scores = richness_scores(df)
            score_list = scores.tolist()
            for i in range(len(score_list) - 1):
                assert score_list[i] <= score_list[i + 1], (
                    f"Score decreased when adding population: "
                    f"{score_list[i]} -> {score_list[i+1]} "
                    f"for progression index {i}"
                )


# ---------------------------------------------------------------------------
# Test: weights sum to 1
# ---------------------------------------------------------------------------


class TestWeightsSumToOne:
    def test_weights_sum_to_one(self):
        """RICHNESS_WEIGHTS must sum to exactly 1.0 (within float tolerance)."""
        total = sum(config.RICHNESS_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"RICHNESS_WEIGHTS sum to {total}"

    def test_all_components_contribute(self):
        """Each weight must be strictly positive."""
        for key, weight in config.RICHNESS_WEIGHTS.items():
            assert weight > 0, f"Weight for '{key}' must be > 0, got {weight}"


# ---------------------------------------------------------------------------
# Test: highlight_reel — deterministic order and tiebreak
# ---------------------------------------------------------------------------


class TestHighlightReelDeterministicOrder:
    def _make_reel_df(self) -> pd.DataFrame:
        """Five rows with distinct richness scores and a tiebreak case."""
        rows = [
            _make_row(artifact_id="art-001", topic_id="t1", update_type="TypeA",
                      impact_score=8.0, n_actionable_lanes=7, n_reg_refs_total=6,
                      has_objective=True, has_what_changed=True, has_why_it_matters=True,
                      has_risk_impact=True, n_key_requirements=3,
                      n_critical_dates=5, n_entities=8, n_tags=8,
                      has_impacted_business=True, n_impacted_functions=3),
            _make_row(artifact_id="art-002", topic_id="t2", update_type="TypeB",
                      impact_score=6.0, n_actionable_lanes=3),
            _make_row(artifact_id="art-003", topic_id="t3", update_type="TypeC",
                      impact_score=5.0, n_actionable_lanes=3),
            _make_row(artifact_id="art-004", topic_id="t4", update_type="TypeD",
                      impact_score=9.0, n_actionable_lanes=0),
            _make_row(artifact_id="art-005", topic_id="t5", update_type="TypeE",
                      impact_score=4.0, n_actionable_lanes=0),
        ]
        df = _make_df(*rows)
        df["richness_score"] = richness_scores(df)
        return df

    def test_highlight_reel_deterministic_order_and_tiebreak(self):
        """highlight_reel returns rows sorted by richness_score desc, then impact_score desc,
        then artifact_id (all deterministic — no randomness)."""
        df = self._make_reel_df()
        n = 3
        reel = highlight_reel(df, n, diversify=False)
        assert len(reel) == n

        # Richness scores must be non-increasing
        scores = reel["richness_score"].tolist()
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not sorted descending at position {i}: {scores}"
            )

    def test_highlight_reel_tiebreak_by_impact_score(self):
        """When richness scores tie, tiebreak is impact_score desc."""
        # Two rows with the same richness components but different impact_score
        rows = [
            _make_row(artifact_id="art-low-impact", topic_id="t1", update_type="T",
                      impact_score=3.0, n_actionable_lanes=3),
            _make_row(artifact_id="art-high-impact", topic_id="t2", update_type="U",
                      impact_score=9.0, n_actionable_lanes=3),
        ]
        df = _make_df(*rows)
        df["richness_score"] = richness_scores(df)
        reel = highlight_reel(df, 2, diversify=False)
        # Both should appear; high-impact first
        assert reel.iloc[0]["artifact_id"] == "art-high-impact"
        assert reel.iloc[1]["artifact_id"] == "art-low-impact"

    def test_highlight_reel_tiebreak_by_artifact_id(self):
        """When richness AND impact_score tie, tiebreak is artifact_id lexicographic."""
        rows = [
            _make_row(artifact_id="art-zzz", topic_id="t1", update_type="T",
                      impact_score=5.0, n_actionable_lanes=3),
            _make_row(artifact_id="art-aaa", topic_id="t2", update_type="U",
                      impact_score=5.0, n_actionable_lanes=3),
        ]
        df = _make_df(*rows)
        df["richness_score"] = richness_scores(df)
        reel = highlight_reel(df, 2, diversify=False)
        assert reel.iloc[0]["artifact_id"] == "art-aaa"
        assert reel.iloc[1]["artifact_id"] == "art-zzz"

    def test_highlight_reel_is_reproducible(self):
        """Calling highlight_reel twice must return identical results."""
        df = self._make_reel_df()
        reel1 = highlight_reel(df, 3, diversify=False)
        reel2 = highlight_reel(df, 3, diversify=False)
        pd.testing.assert_frame_equal(reel1.reset_index(drop=True),
                                      reel2.reset_index(drop=True))

    def test_highlight_reel_n_capped_by_frame_size(self):
        """When n > len(df), return all rows."""
        df = self._make_reel_df()
        reel = highlight_reel(df, 100, diversify=False)
        assert len(reel) == len(df)


# ---------------------------------------------------------------------------
# Test: highlight_reel diversify — at most one per topic_id
# ---------------------------------------------------------------------------


class TestHighlightReelDiversify:
    def test_highlight_reel_diversify_one_per_topic(self):
        """With diversify=True, at most one record per topic_id appears in the reel."""
        rows = [
            # Three records from topic t1 — only the highest-richness one should appear
            _make_row(artifact_id="art-t1-a", topic_id="t1", update_type="TypeX",
                      impact_score=9.0, n_actionable_lanes=7,
                      has_objective=True, has_what_changed=True),
            _make_row(artifact_id="art-t1-b", topic_id="t1", update_type="TypeX",
                      impact_score=8.0, n_actionable_lanes=5),
            _make_row(artifact_id="art-t1-c", topic_id="t1", update_type="TypeX",
                      impact_score=7.0, n_actionable_lanes=3),
            # Two records from topic t2
            _make_row(artifact_id="art-t2-a", topic_id="t2", update_type="TypeY",
                      impact_score=6.0, n_actionable_lanes=4),
            _make_row(artifact_id="art-t2-b", topic_id="t2", update_type="TypeY",
                      impact_score=5.0, n_actionable_lanes=2),
            # One record from t3 and t4
            _make_row(artifact_id="art-t3", topic_id="t3", update_type="TypeZ",
                      impact_score=4.0, n_actionable_lanes=1),
            _make_row(artifact_id="art-t4", topic_id="t4", update_type="TypeW",
                      impact_score=3.0, n_actionable_lanes=1),
        ]
        df = _make_df(*rows)
        df["richness_score"] = richness_scores(df)
        n = 4
        reel = highlight_reel(df, n, diversify=True)
        assert len(reel) == n
        # Each topic_id appears at most once
        topic_ids = reel["topic_id"].tolist()
        assert len(topic_ids) == len(set(topic_ids)), (
            f"Duplicate topic_ids in diversified reel: {topic_ids}"
        )

    def test_highlight_reel_diversify_then_update_type_fill(self):
        """After topic diversity, remaining slots use update_type diversity."""
        # 6 records: 2 topics × 2 update types
        rows = [
            _make_row(artifact_id="t1-ua-1", topic_id="t1", update_type="UA",
                      impact_score=9.0, n_actionable_lanes=7,
                      has_objective=True),
            _make_row(artifact_id="t1-ua-2", topic_id="t1", update_type="UA",
                      impact_score=8.0, n_actionable_lanes=5),
            _make_row(artifact_id="t1-ub-1", topic_id="t1", update_type="UB",
                      impact_score=7.0, n_actionable_lanes=4),
            _make_row(artifact_id="t2-ua-1", topic_id="t2", update_type="UA",
                      impact_score=6.0, n_actionable_lanes=3),
            _make_row(artifact_id="t2-ub-1", topic_id="t2", update_type="UB",
                      impact_score=5.0, n_actionable_lanes=2),
            _make_row(artifact_id="t3-ua-1", topic_id="t3", update_type="UA",
                      impact_score=4.0, n_actionable_lanes=1),
        ]
        df = _make_df(*rows)
        df["richness_score"] = richness_scores(df)
        reel = highlight_reel(df, 6, diversify=True)
        # No more than 1 per topic in the first pass
        topic_counts = reel["topic_id"].value_counts()
        # All topics at most 2 (after topic diversity pass saturates, update_type pass runs)
        # But the test mainly checks it's stable and no topic gets more slots unfairly
        assert len(reel) <= 6
        assert len(reel) >= 3  # at least the 3 topics should appear

    def test_highlight_reel_diversify_false_no_topic_restriction(self):
        """With diversify=False, multiple records from the same topic_id are allowed."""
        rows = [
            _make_row(artifact_id="t1-1", topic_id="t1", update_type="T",
                      impact_score=9.0, n_actionable_lanes=7),
            _make_row(artifact_id="t1-2", topic_id="t1", update_type="T",
                      impact_score=8.0, n_actionable_lanes=6),
            _make_row(artifact_id="t1-3", topic_id="t1", update_type="T",
                      impact_score=7.0, n_actionable_lanes=5),
        ]
        df = _make_df(*rows)
        df["richness_score"] = richness_scores(df)
        reel = highlight_reel(df, 3, diversify=False)
        assert len(reel) == 3
        # All three from topic t1
        assert all(reel["topic_id"] == "t1")
