"""Tests for the prediction-market-relevance filter and projection logic."""

from pathlib import Path

import pytest

from build.pull_carver import is_prediction_market_relevant, load_filter_inputs, normalize_event


@pytest.fixture(scope="module")
def filter_inputs() -> tuple[set[str], set[str]]:
    return load_filter_inputs(Path(__file__).parent.parent / "data")


def test_filter_matches_business_type(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    event = {
        "impacted_business": {"type": ["Event Contracts"]},
        "regulatory_source": {"name": "Some Obscure Agency"},
        "entities": [],
    }
    assert is_prediction_market_relevant(event, regulators, entities) is True


def test_filter_matches_regulator_allowlist(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    event = {
        "impacted_business": {"type": ["Banking"]},
        "regulatory_source": {"name": "Commodity Futures Trading Commission"},
        "entities": [],
    }
    assert is_prediction_market_relevant(event, regulators, entities) is True


def test_filter_matches_platform_entity(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    event = {
        "impacted_business": {"type": ["Banking"]},
        "regulatory_source": {"name": "Some Obscure Agency"},
        "entities": ["Kalshi"],
    }
    assert is_prediction_market_relevant(event, regulators, entities) is True


def test_filter_rejects_unrelated(filter_inputs: tuple[set[str], set[str]]) -> None:
    regulators, entities = filter_inputs
    event = {
        "impacted_business": {"type": ["Telecom"]},
        "regulatory_source": {"name": "Some Telecom Regulator"},
        "entities": ["Unrelated Co."],
    }
    assert is_prediction_market_relevant(event, regulators, entities) is False


def test_load_filter_inputs_loads_seeds() -> None:
    regulators, entities = load_filter_inputs(Path(__file__).parent.parent / "data")
    assert len(regulators) >= 50
    assert "Kalshi" in entities


def test_normalize_event_merges_entry_and_annotation() -> None:
    """normalize_event combines the entry row and the annotation payload into one
    flat dict whose keys match what is_prediction_market_relevant expects."""
    entry = {
        "entry_id": "abc-123",
        "entry_title": "Some title",
        "entry_link": "https://example.com",
        "published_at": "2025-06-01",
        "feed_id": "feed-1",
        "topic_id": "topic-1",
    }
    annotation_payload = {
        "classification": {"update_type": "enforcement"},
        "metadata": {
            "regulatory_source": {"name": "Commodity Futures Trading Commission"},
            "impacted_business": {"type": ["Event Contracts"]},
        },
        "scores": {"impact_score": 8, "urgency_score": 9, "relevance_score": 9},
        "summary": "Brief summary.",
    }
    out = normalize_event(entry, annotation_payload)
    assert out["entry_id"] == "abc-123"
    assert out["update_type"] == "enforcement"
    assert out["regulatory_source"]["name"] == "Commodity Futures Trading Commission"
    assert out["impacted_business"]["type"] == ["Event Contracts"]
    assert out["scores"]["impact_score"] == 8
    assert out["title"] == "Some title"


def test_normalize_event_handles_empty_annotation() -> None:
    """When the annotation endpoint returns nothing for an entry, normalize_event
    must produce a record with empty (not None) annotation fields."""
    entry = {"entry_id": "xyz", "entry_title": "Test", "published_at": "2025-01-01"}
    out = normalize_event(entry, {})
    assert out["entry_id"] == "xyz"
    assert out["title"] == "Test"
    assert out["regulatory_source"] == {}
    assert out["impacted_business"] == {}
    assert out["entities"] == []
    assert out["scores"] == {}
    assert out["summary"] == ""
