"""Tests for build/_thesis.py."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_CACHE = Path(__file__).parent / "fixtures" / "llm"


def test_decompose_returns_cached_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    from build import _thesis

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # cache hit only
    result = _thesis.decompose(
        contract_id="ttb",
        title="Will TikTok be banned",
        resolution_criteria="Resolves YES if TikTok unavailable...",
        settlement_entities=["TikTok", "ByteDance"],
        cache_root=FIXTURE_CACHE,
    )
    assert len(result) == 2
    assert result[0]["id"] == "A"
    assert result[1]["label"] == "Federal divestiture order"


def test_decompose_falls_back_when_no_cache_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build import _thesis

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = _thesis.decompose(
        contract_id="missing",
        title="t", resolution_criteria="rc",
        settlement_entities=[],
        cache_root=tmp_path / "empty",
    )
    assert len(result) == 1
    assert result[0]["id"] == "A"
    assert result[0]["label"] == "Resolution criteria"
    assert "rc" in result[0]["summary"]
