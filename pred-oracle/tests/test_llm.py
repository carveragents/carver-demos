"""Tests for build/_llm.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_cache_hit_returns_cached_response_without_calling_openai(tmp_path: Path) -> None:
    from build import _llm

    cache_root = tmp_path / "cache"
    purpose_dir = cache_root / "thesis"
    purpose_dir.mkdir(parents=True)

    payload = {"conditions": [{"id": "A", "label": "Test", "summary": "x"}]}
    (purpose_dir / "ctr-1.json").write_text(json.dumps({
        "request": {"model": "gpt-5", "system": "s", "user": "u"},
        "response": payload,
    }))

    # No OPENAI_API_KEY needed: cache hit short-circuits before the client.
    result = _llm.complete_json(
        purpose="thesis", cache_key="ctr-1",
        model="gpt-5", system="s", user="u",
        schema={"type": "object"}, cache_root=cache_root,
    )
    assert result == payload


def test_cache_miss_without_api_key_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build import _llm
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = _llm.complete_json(
        purpose="thesis", cache_key="missing",
        model="gpt-5", system="s", user="u",
        schema={"type": "object"}, cache_root=tmp_path / "empty",
    )
    assert result is None


def test_cache_key_sha_is_stable(tmp_path: Path) -> None:
    from build._llm import cache_key_for

    k1 = cache_key_for(model="gpt-5", system="s", user="u",
                       schema={"type": "object", "properties": {"a": 1}})
    k2 = cache_key_for(model="gpt-5", system="s", user="u",
                       schema={"properties": {"a": 1}, "type": "object"})
    assert k1 == k2  # JSON serialization is sorted


def test_is_available_reflects_env_and_import(monkeypatch: pytest.MonkeyPatch) -> None:
    from build import _llm
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert _llm.is_available() is True
    monkeypatch.delenv("OPENAI_API_KEY")
    assert _llm.is_available() is False
