"""Tests for build/_narrative.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_summarize_returns_cached_narrative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._narrative import _timeline_hash, summarize

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    timeline = [{"pub_date": "2025-03-01", "title": "X", "condition_tag": "A",
                 "one_line_why": "Y"}]
    contract = {"id": "ttb", "title": "T", "kind": "retrospective"}
    h = _timeline_hash(timeline)
    cache_dir = tmp_path / "narrative"
    cache_dir.mkdir(parents=True)
    (cache_dir / f"ttb__{h}.json").write_text(json.dumps({
        "request": {},
        "response": {"text": "Between July 2024 and April 2025, the contract..."},
    }))
    result = summarize(contract=contract, timeline=timeline,
                       cache_root=tmp_path)
    assert "Between July" in result


def test_summarize_returns_empty_when_no_cache_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build._narrative import summarize

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = summarize(
        contract={"id": "x", "title": "t", "kind": "active"},
        timeline=[], cache_root=tmp_path / "empty",
    )
    assert result == ""
