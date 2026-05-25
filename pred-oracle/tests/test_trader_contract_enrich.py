from __future__ import annotations

from datetime import date
from build._mechanism import classify, BINDING_ACTION, SIGNAL, CONTEXT


def _make_slice_doc():
    return {
        "contract": {
            "id": "test-contract",
            "platform": "kalshi",
            "kind": "active",
            "title": "Will test happen?",
            "resolution_criteria": "Resolves YES if test happens.",
            "settlement_entities": [{"name": "Test Entity", "role": "regulator"}],
        },
        "position": {"side": "YES", "size": 100, "entry_price": 0.50},
        "timeline": [
            {
                "pub_date": "2026-05-10",
                "title": "Test enforcement",
                "regulator": "Test Entity",
                "url": "https://example.com",
                "urgency": 8.0,
                "impact": 7.0,
                "matched_entity": "Test Entity",
                "carver_feed_entry_id": "e1",
            }
        ],
    }


def test_mechanism_applied_to_enriched_timeline():
    assert classify("enforcement") == BINDING_ACTION
    assert classify("proposed rule") == SIGNAL
    assert classify("speech") == CONTEXT


def test_project_timeline_fields_includes_direction():
    from build.trader_contract_enrich import _project_timeline_fields

    judged = [
        {
            "pub_date": "2026-05-10",
            "pub_date_valid": True,
            "title": "Test",
            "link": "https://x",
            "regulator_name": "Test Entity",
            "regulator_division": "",
            "topic_name": "Test Entity",
            "update_type": "enforcement",
            "entities": ["Test Entity"],
            "scores": {"urgency": {"score": 8}, "impact": {"score": 7}},
            "feed_entry_id": "e1",
            "relevant": True,
            "relevance_score": 8,
            "one_line_why": "Direct enforcement",
            "condition_tag": "A",
            "high_impact": True,
            "direction": "bullish",
            "magnitude": "high",
            "timeline_shift": "sooner",
        }
    ]
    result = _project_timeline_fields(judged)
    assert len(result) == 1
    event = result[0]
    assert event["direction"] == "bullish"
    assert event["magnitude"] == "high"
    assert event["timeline_shift"] == "sooner"
    assert event["mechanism"] == BINDING_ACTION
