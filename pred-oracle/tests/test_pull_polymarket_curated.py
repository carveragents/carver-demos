"""Tests for build/pull_polymarket_curated.py — non-destructive refresh."""
from pathlib import Path
from typing import Any

import yaml


def _write_contracts(path: Path, picks: list[dict[str, Any]]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def test_refresh_polymarket_populates_cached(tmp_path: Path, monkeypatch) -> None:
    from build import pull_polymarket_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{"id": "pm-x", "source_lookup": {"slug": "pm-x"}}])

    def fake_lookup(lookup: dict[str, str]) -> dict[str, Any] | None:
        return {"id": "12345", "slug": "pm-x", "question": "Q", "description": "D",
                "closed": False, "startDate": "2026-01-01T00:00:00Z",
                "endDate": "2026-12-31T00:00:00Z", "conditionId": "0xabc"}

    monkeypatch.setattr(m, "lookup_market", fake_lookup)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    assert doc["picks"][0]["cached"]["title"] == "Q"
    assert doc["picks"][0]["cached"]["status"] == "active"
    assert "last_pulled_at" in doc["picks"][0]


def test_refresh_polymarket_demotes_to_stale(tmp_path: Path, monkeypatch) -> None:
    from build import pull_polymarket_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{
        "id": "pm-retired",
        "source_lookup": {"slug": "pm-retired"},
        "cached": {"title": "Retired"},
    }])

    monkeypatch.setattr(m, "lookup_market", lambda lookup: None)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    assert doc["picks"][0]["cached"]["title"] == "Retired"
    assert doc["picks"][0]["stale"] is True
