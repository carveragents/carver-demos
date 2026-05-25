"""Tests for build/_heat.py — heat score + sparkline + entity matching."""
from datetime import date

import pytest

from build import _heat


def test_entity_match_exact_intersect() -> None:
    contract_entities = ["U.S. Securities and Exchange Commission", "BlackRock"]
    record_entities = ["BlackRock", "Vanguard"]
    assert _heat.entity_match(contract_entities, record_entities) is True


def test_entity_match_case_insensitive_substring() -> None:
    contract = ["TikTok"]
    record_entities = ["tiktok inc."]
    assert _heat.entity_match(contract, record_entities) is True


def test_entity_match_no_overlap() -> None:
    assert _heat.entity_match(["SEC"], ["FDA"]) is False


def test_entity_match_empty_inputs() -> None:
    assert _heat.entity_match([], ["SEC"]) is False
    assert _heat.entity_match(["SEC"], []) is False


def test_heat_score_zero_when_no_matches() -> None:
    """No record matches the contract's entities → heat 0."""
    contract = {"settlement_entities": ["Made-Up Agency"]}
    records = [
        {
            "entities": ["SEC"],
            "scores": {"urgency": {"score": 9}},
            "pub_date": "2026-05-19",
            "pub_date_valid": True,
        }
    ]
    assert _heat.heat_score(contract, records, today=date(2026, 5, 19)) == 0.0


def test_heat_score_decays_with_age() -> None:
    """Same severity, two records — recent one weighs more than 30-day-old."""
    contract = {"settlement_entities": ["SEC"]}
    rec_today = {
        "entities": ["SEC"],
        "scores": {"urgency": {"score": 8}},
        "pub_date": "2026-05-19",
        "pub_date_valid": True,
        "update_type": "enforcement",
    }
    rec_30d = {
        "entities": ["SEC"],
        "scores": {"urgency": {"score": 8}},
        "pub_date": "2026-04-19",
        "pub_date_valid": True,
        "update_type": "enforcement",
    }
    today = date(2026, 5, 19)
    h_today = _heat.heat_score(contract, [rec_today], today=today)
    h_30d = _heat.heat_score(contract, [rec_30d], today=today)
    assert h_today > h_30d


def test_heat_score_sums_across_matching_records() -> None:
    contract = {"settlement_entities": ["SEC"]}
    _rec = {
        "entities": ["SEC"],
        "scores": {"urgency": {"score": 8}},
        "pub_date": "2026-05-19",
        "pub_date_valid": True,
        "update_type": "enforcement",
    }
    records = [_rec, _rec]
    h_one = _heat.heat_score(contract, records[:1], today=date(2026, 5, 19))
    h_two = _heat.heat_score(contract, records, today=date(2026, 5, 19))
    assert h_two == pytest.approx(2 * h_one, rel=0.001)


def test_sparkline_buckets_14_days() -> None:
    contract = {"settlement_entities": ["SEC"]}
    records = [
        {
            "entities": ["SEC"],
            "scores": {"urgency": {"score": 7}},
            "pub_date": "2026-05-19",
            "pub_date_valid": True,
        },
        {
            "entities": ["SEC"],
            "scores": {"urgency": {"score": 7}},
            "pub_date": "2026-05-10",
            "pub_date_valid": True,
        },
        {
            "entities": ["FDA"],
            "scores": {"urgency": {"score": 7}},
            "pub_date": "2026-05-19",
            "pub_date_valid": True,
        },  # filtered out
    ]
    buckets = _heat.sparkline_buckets(contract, records, today=date(2026, 5, 19), days=14)
    assert len(buckets) == 14
    # Most-recent index (last) has the today record; index 9 (5 days ago) has the older one
    assert buckets[-1] >= 1
    assert sum(buckets) == 2  # FDA record was filtered


def test_heat_score_excludes_invalid_dates_and_old_records() -> None:
    contract = {"settlement_entities": ["SEC"]}
    records = [
        {
            "entities": ["SEC"],
            "scores": {"urgency": {"score": 8}},
            "pub_date_valid": False,
            "pub_date": "2026-05-19",
        },
        {
            "entities": ["SEC"],
            "scores": {"urgency": {"score": 8}},
            "pub_date_valid": True,
            "pub_date": "2025-01-01",  # >90 days
        },
    ]
    assert _heat.heat_score(contract, records, today=date(2026, 5, 19), max_age_days=90) == 0.0
