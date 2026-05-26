from __future__ import annotations

from build._relevance import build_schema, _heuristic_judgment


def test_schema_includes_direction_field():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    props = schema["properties"]
    assert "direction" in props
    assert set(props["direction"]["enum"]) == {"bullish", "bearish", "neutral"}


def test_schema_includes_magnitude_field():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    props = schema["properties"]
    assert "magnitude" in props
    assert set(props["magnitude"]["enum"]) == {"high", "medium", "low"}


def test_schema_includes_timeline_shift_field():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    props = schema["properties"]
    assert "timeline_shift" in props
    assert set(props["timeline_shift"]["enum"]) == {"sooner", "later", "none"}


def test_all_new_fields_are_required():
    conditions = [{"id": "A", "label": "test", "summary": "test summary"}]
    schema = build_schema(conditions)
    required = schema["required"]
    assert "direction" in required
    assert "magnitude" in required
    assert "timeline_shift" in required


def test_heuristic_includes_direction_fields():
    rec = {
        "scores": {"urgency": {"score": 7, "label": "high"}},
        "entities": ["SEC"],
        "topic_name": "SEC",
    }
    result = _heuristic_judgment(rec)
    assert result["direction"] == "neutral"
    assert result["magnitude"] == "low"
    assert result["timeline_shift"] == "none"


from unittest.mock import patch

def test_judge_batch_propagates_direction_from_verdict():
    """Regression: judge_batch must copy direction/magnitude/timeline_shift
    from the LLM verdict into the enriched record dict."""
    contract = {
        "id": "test",
        "title": "Test",
        "resolution_criteria": "Test",
        "settlement_entities": ["SEC"],
    }
    conditions = [{"id": "A", "label": "test", "summary": "test"}]
    candidate = {
        "title": "SEC enforcement action",
        "feed_entry_id": "rec-1",
        "link": "https://example.com",
        "scores": {"urgency": {"score": 7, "label": "high"},
                   "relevance": {"score": 6, "label": "medium"}},
        "entities": ["SEC"],
        "topic_name": "SEC",
    }
    fake_verdict = {
        "relevant": True,
        "relevance_score": 8,
        "one_line_why": "Direct enforcement",
        "condition_tag": "A",
        "high_impact": True,
        "direction": "bearish",
        "magnitude": "high",
        "timeline_shift": "sooner",
    }
    with patch("build._relevance._llm.cache_key_for", return_value="fake-key"), \
         patch("build._relevance._llm.complete_json", return_value=fake_verdict):
        from build._relevance import judge_batch
        results = judge_batch(
            contract=contract,
            conditions=conditions,
            candidates=[candidate],
        )
    assert len(results) == 1
    rec = results[0]
    assert rec["direction"] == "bearish"
    assert rec["magnitude"] == "high"
    assert rec["timeline_shift"] == "sooner"
