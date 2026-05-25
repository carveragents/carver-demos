"""Tests for build/_relevance.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from build import _llm


def test_judge_uses_cache_drops_irrelevant_and_sorts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._relevance import (
        SYSTEM_PROMPT,
        build_schema,
        build_user_prompt,
        judge_batch,
    )

    contract = {
        "id": "ttb", "title": "TikTok ban?", "resolution_criteria": "...",
        "settlement_entities": ["TikTok"],
    }
    conditions = [{"id": "A", "label": "x", "summary": "y"}]
    candidates = [
        {"feed_entry_id": "r1", "title": "PAFACA reauth", "pub_date": "2025-03-01",
         "pub_date_valid": True,
         "scores": {"urgency": {"score": 8}}, "entities": ["TikTok"], "link": "u1"},
        {"feed_entry_id": "r2", "title": "Irrelevant", "pub_date": "2025-02-01",
         "pub_date_valid": True,
         "scores": {"urgency": {"score": 6}}, "entities": ["TikTok"], "link": "u2"},
    ]

    # Pre-write cache entries for both candidates
    cache_dir = tmp_path / "cache" / "relevance"
    cache_dir.mkdir(parents=True)
    for cand, payload in [
        (candidates[0], {"relevant": True, "relevance_score": 9,
                         "one_line_why": "PAFACA reauth moves deadline",
                         "condition_tag": "A", "high_impact": True}),
        (candidates[1], {"relevant": False, "relevance_score": 0,
                         "one_line_why": "", "condition_tag": "background",
                         "high_impact": False}),
    ]:
        key = _llm.cache_key_for(
            model=_llm.MODEL_FAST,
            system=SYSTEM_PROMPT,
            user=build_user_prompt(contract, conditions, cand),
            schema=build_schema(conditions),
        )
        (cache_dir / f"{key}.json").write_text(json.dumps({
            "request": {}, "response": payload,
        }))

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Opt out of soft-fallback so we test pure LLM-relevant filtering.
    judged = judge_batch(
        contract=contract, conditions=conditions, candidates=candidates,
        cache_root=tmp_path / "cache", min_results=1,
    )
    assert len(judged) == 1
    assert judged[0]["feed_entry_id"] == "r1"
    assert judged[0]["one_line_why"] == "PAFACA reauth moves deadline"
    assert judged[0]["condition_tag"] == "A"


def test_judge_falls_back_when_no_cache_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._relevance import judge_batch

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    contract = {"id": "x", "title": "t", "resolution_criteria": "r",
                "settlement_entities": ["E"]}
    conditions = [{"id": "A", "label": "x", "summary": "y"}]
    candidates = [
        {"feed_entry_id": "r1", "title": "X", "pub_date": "2025-01-01",
         "pub_date_valid": True,
         "scores": {"urgency": {"score": 5}}, "entities": ["E"],
         "topic_name": "Topic-X", "link": "u"},
    ]
    judged = judge_batch(
        contract=contract, conditions=conditions, candidates=candidates,
        cache_root=tmp_path / "empty",
    )
    # Heuristic fallback keeps the record with a generated one_line_why
    assert len(judged) == 1
    assert "Topic-X" in judged[0]["one_line_why"] or "E" in judged[0]["one_line_why"]
    assert judged[0]["condition_tag"] == "background"
