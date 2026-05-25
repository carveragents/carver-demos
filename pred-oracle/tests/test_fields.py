"""Tests for build/_fields.py — extractors for the Stage 1 artifact schema."""

from datetime import date

from build import _fields

SAMPLE = {
    "artifact_id": "a1",
    "feed_entry_id": "f1",
    "topic_id": "t1",
    "topic_name": "Commodity Futures Trading Commission",
    "topic_jurisdiction_code": "US",
    "title": "CFTC Sues Minnesota",
    "link": "https://www.cftc.gov/p/9233-26",
    "regulator_name": "Commodity Futures Trading Commission",
    "regulator_division": "Division of Enforcement",
    "update_type": "enforcement",
    "pub_date": "2026-05-19",
    "pub_date_valid": True,
    "impacted_business": {"jurisdiction": ["US", "US-MN"], "industry": ["Derivatives"]},
    "scores": {
        "urgency": {"label": "high", "score": 9, "confidence": 0.95},
        "impact": {"label": "high", "score": 9, "confidence": 0.9},
        "relevance": {"label": "high", "score": 9, "confidence": 0.9},
    },
    "tags": ["CFTC", "enforcement"],
    "entities": ["Minnesota Attorney General", "CFTC"],
    "jurisdiction_tier": {"label": "us_federal", "tier": 1},
    "impact_summary": {
        "what_changed": "CFTC sued Minnesota.",
        "why_it_matters": "It matters because event contracts.",
        "key_requirements": ["Comply.", "File reports."],
        "objective": "Block state criminalization.",
        "risk_impact": "high",
    },
}


def test_urgency_score_returns_numeric() -> None:
    assert _fields.urgency_score(SAMPLE) == 9.0


def test_impact_score_returns_numeric() -> None:
    assert _fields.impact_score(SAMPLE) == 9.0


def test_relevance_score_returns_numeric() -> None:
    assert _fields.relevance_score(SAMPLE) == 9.0


def test_scores_default_to_zero_when_missing() -> None:
    assert _fields.urgency_score({}) == 0.0
    assert _fields.urgency_score({"scores": {}}) == 0.0
    assert _fields.urgency_score({"scores": {"urgency": {}}}) == 0.0


def test_pub_date_iso_returns_date_string() -> None:
    assert _fields.pub_date_iso(SAMPLE) == "2026-05-19"


def test_pub_date_iso_returns_empty_when_invalid() -> None:
    rec = {"pub_date": "2026-05-19", "pub_date_valid": False}
    assert _fields.pub_date_iso(rec) == ""


def test_pub_date_iso_returns_empty_when_missing() -> None:
    assert _fields.pub_date_iso({}) == ""


def test_pub_date_age_days_handles_iso_string() -> None:
    today = date(2026, 5, 19)
    assert _fields.pub_date_age_days(SAMPLE, today=today) == 0


def test_pub_date_age_days_handles_older_record() -> None:
    today = date(2026, 5, 19)
    rec = {"pub_date": "2026-02-18", "pub_date_valid": True}
    assert _fields.pub_date_age_days(rec, today=today) == 90


def test_pub_date_age_days_none_when_no_date() -> None:
    today = date(2026, 5, 19)
    assert _fields.pub_date_age_days({}, today=today) is None


def test_jurisdictions_returns_list_from_impacted_business() -> None:
    assert _fields.jurisdictions(SAMPLE) == ["US", "US-MN"]


def test_jurisdictions_returns_empty_list_when_missing() -> None:
    assert _fields.jurisdictions({}) == []


def test_us_states_filters_to_us_state_codes() -> None:
    rec = {"impacted_business": {"jurisdiction": ["US", "US-CA", "US-NY", "GB", "EU"]}}
    assert sorted(_fields.us_states(rec)) == ["US-CA", "US-NY"]


def test_regulator_display_combines_division() -> None:
    expected = "Commodity Futures Trading Commission — Division of Enforcement"
    assert _fields.regulator_display(SAMPLE) == expected


def test_regulator_display_without_division() -> None:
    rec = {"regulator_name": "SEC", "regulator_division": ""}
    assert _fields.regulator_display(rec) == "SEC"


def test_regulator_display_falls_back_to_topic_name() -> None:
    rec = {"regulator_name": "", "topic_name": "Topic Fallback"}
    assert _fields.regulator_display(rec) == "Topic Fallback"


def test_urgency_tier_returns_bucket_name() -> None:
    assert _fields.urgency_tier(9.0) == "critical"
    assert _fields.urgency_tier(7.5) == "high"
    assert _fields.urgency_tier(5.0) == "medium"
    assert _fields.urgency_tier(2.0) == "low"
    assert _fields.urgency_tier(0.0) == "low"
