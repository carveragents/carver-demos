"""Tests for build/_country.py — per-country aggregation."""
from datetime import date

from build import _country
from tests.conftest import make_row


def test_country_code_prefers_topic_then_jurisdiction() -> None:
    r = make_row(topic_jurisdiction_code="FR", impacted_business={"jurisdiction": ["DE"]})
    assert _country.country_code(r) == "FR"
    r2 = make_row(topic_jurisdiction_code="", impacted_business={"jurisdiction": ["DE"]})
    assert _country.country_code(r2) == "DE"


def test_country_code_skips_us_states_for_world_map() -> None:
    """US-CA / US-NY should aggregate to the US-states inset, not the world map."""
    r = make_row(topic_jurisdiction_code="US-CA")
    assert _country.country_code(r, world_only=True) is None
    assert _country.country_code(r, world_only=False) == "US-CA"


def test_country_code_rejects_non_iso_strings() -> None:
    """Free-form / placeholder codes from the corpus must not appear on the map."""
    for bad in ("-", "Members: EU Member States", "us", "USA1", " ", ""):
        r = make_row(topic_jurisdiction_code=bad, impacted_business={"jurisdiction": []})
        assert _country.country_code(r) is None, f"{bad!r} should be rejected"


def test_country_code_excludes_all_subdivisions_from_world() -> None:
    """world_only must drop subdivisions of every country, not just US-XX."""
    for code in ("CA-ON", "CA-QC", "AU-NSW"):
        r = make_row(topic_jurisdiction_code=code)
        assert _country.country_code(r, world_only=True) is None
        assert _country.country_code(r, world_only=False) == code


def test_aggregate_basic() -> None:
    rows = [
        make_row(topic_jurisdiction_code="FR", scores={"urgency": {"score": 8}}),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR",
                 scores={"urgency": {"score": 6}}),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="DE",
                 scores={"urgency": {"score": 9}}),
    ]
    agg = _country.aggregate(rows, today=date(2026, 5, 19), window_days=90)
    assert agg["FR"]["count"] == 2
    assert agg["FR"]["avg_urgency"] == 7.0
    assert agg["FR"]["max_urgency"] == 8.0
    assert agg["DE"]["count"] == 1


def test_aggregate_filters_outside_window() -> None:
    rows = [
        make_row(topic_jurisdiction_code="FR", pub_date="2026-05-19"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", pub_date="2024-01-01"),
    ]
    agg = _country.aggregate(rows, today=date(2026, 5, 19), window_days=90)
    assert agg["FR"]["count"] == 1


def test_pressure_score_composite() -> None:
    """count * avg_urgency, normalized to 0-100 for visual contrast."""
    rows = [make_row(topic_jurisdiction_code="FR", scores={"urgency": {"score": 9}})] * 10
    rows += [make_row(feed_entry_id=f"q{i}", topic_jurisdiction_code="DE",
                       scores={"urgency": {"score": 5}}) for i in range(3)]
    agg = _country.aggregate(rows, today=date(2026, 5, 19), window_days=90)
    assert _country.pressure_score(agg["FR"]) > _country.pressure_score(agg["DE"])


def test_weekly_buckets_for_country() -> None:
    rows = [
        make_row(topic_jurisdiction_code="FR", pub_date="2026-05-19"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", pub_date="2026-05-05"),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="FR", pub_date="2025-12-01"),
    ]
    buckets = _country.weekly_buckets(rows, code="FR",
                                      today=date(2026, 5, 19), weeks=78)
    assert len(buckets) == 78
    assert sum(buckets) == 3
