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
