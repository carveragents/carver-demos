"""Tests for build/_scoring.py — wow-score and inbox eligibility."""
from datetime import date

import pytest

from build import _scoring


def _make(**overrides) -> dict:
    base = {
        "title": "T",
        "link": "https://x",
        "regulator_name": "CFTC",
        "topic_name": "Commodity Futures Trading Commission",
        "topic_jurisdiction_code": "US",
        "update_type": "enforcement",
        "pub_date": "2026-05-19",
        "pub_date_valid": True,
        "impacted_business": {"jurisdiction": ["US"]},
        "scores": {
            "urgency": {"score": 8},
            "impact": {"score": 7},
            "relevance": {"score": 8},
        },
        "entities": [],
        "tags": [],
        "jurisdiction_tier": {"label": "us_federal"},
    }
    base.update(overrides)
    return base


def test_eligible_record_passes() -> None:
    assert _scoring.is_inbox_eligible(_make()) is True


def test_excludes_website_error() -> None:
    assert _scoring.is_inbox_eligible(_make(update_type="website error")) is False


def test_excludes_other_update_type() -> None:
    assert _scoring.is_inbox_eligible(_make(update_type="other")) is False


def test_excludes_low_relevance() -> None:
    rec = _make()
    rec["scores"]["relevance"]["score"] = 4.5
    assert _scoring.is_inbox_eligible(rec) is False


def test_excludes_no_title() -> None:
    assert _scoring.is_inbox_eligible(_make(title="")) is False


def test_excludes_no_link() -> None:
    assert _scoring.is_inbox_eligible(_make(link="")) is False


def test_excludes_invalid_pub_date() -> None:
    assert _scoring.is_inbox_eligible(_make(pub_date_valid=False)) is False


def test_excludes_old_record_outside_window() -> None:
    rec = _make(pub_date="2025-01-01")  # >90 days from build date
    assert _scoring.is_inbox_eligible(rec, today=date(2026, 5, 19), max_age_days=90) is False


def test_wow_score_recency_full_credit_for_recent() -> None:
    rec = _make(pub_date="2026-05-19")  # 0 days old
    score = _scoring.wow_score(rec, today=date(2026, 5, 19))
    # recency_score = 10; weight 0.15
    assert score == pytest.approx(
        0.30 * 8 + 0.20 * 7 + 0.15 * 10 + 0.15 * 10 + 0.10 * 8 + 0.10 * 0,
        rel=0.01,
    )


def test_wow_score_recency_decays_with_age() -> None:
    rec_30 = _make(pub_date="2026-04-19")  # 30 days
    rec_60 = _make(pub_date="2026-03-20")  # 60 days
    rec_90 = _make(pub_date="2026-02-18")  # 90 days
    today = date(2026, 5, 19)
    assert _scoring.wow_score(rec_30, today=today) > _scoring.wow_score(rec_60, today=today)
    assert _scoring.wow_score(rec_60, today=today) > _scoring.wow_score(rec_90, today=today)


def test_wow_score_recognition_fires_for_pm_name() -> None:
    rec = _make(entities=["Kalshi"])
    rec_no = _make()
    today = date(2026, 5, 19)
    assert _scoring.wow_score(rec, today=today) > _scoring.wow_score(rec_no, today=today)


def test_wow_score_jurisdiction_us_state_beats_us_federal() -> None:
    rec_state = _make(topic_jurisdiction_code="US-CA")
    rec_fed = _make(topic_jurisdiction_code="US")
    today = date(2026, 5, 19)
    # jurisdiction weight is 0.10; state=10, fed=8 → difference = 0.2
    assert _scoring.wow_score(rec_state, today=today) > _scoring.wow_score(rec_fed, today=today)
