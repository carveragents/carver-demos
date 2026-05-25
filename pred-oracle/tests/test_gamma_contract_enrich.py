"""Tests for build/gamma_contract_enrich.py."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURE_CACHE = Path(__file__).parent / "fixtures" / "llm"


def test_enrich_adds_all_required_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from build.gamma_contract_enrich import enrich_slice

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    slice_doc = {
        "scene": {},
        "contract": {
            "id": "ttb", "kind": "retrospective", "platform": "kalshi",
            "title": "TikTok ban?",
            "resolution_criteria": "Resolves YES if TikTok unavailable...",
            "listed_at": "2024-04-24", "resolved_at": "2025-04-30",
            "settlement_entities": [{"name": "TikTok", "role": "company"}],
            "heat": 25.0,
            "heat_history": [0] * 14,
        },
        "timeline": [
            {"pub_date": "2025-03-01", "title": "PAFACA reauth",
             "regulator": "Congress", "url": "u", "urgency": 8, "impact": 7,
             "matched_entity": "TikTok", "carver_feed_entry_id": "f1"},
        ],
        "open_tickets": [],
    }
    corpus = []  # empty corpus; relevance becomes a no-op via _hydrate_candidates

    enriched = enrich_slice(
        slice_doc=slice_doc, corpus=corpus, peer_heats=[10.0, 25.0, 40.0],
        today=date(2026, 5, 20), cache_root=FIXTURE_CACHE,
    )
    assert "conditions" in enriched["contract"]
    assert "narrative" in enriched["contract"]
    assert "heat_panel" in enriched
    assert enriched["heat_panel"]["tier"] in ("dormant", "watch", "active", "critical")
