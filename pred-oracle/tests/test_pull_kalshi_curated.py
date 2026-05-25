"""Tests for build/pull_kalshi_curated.py — non-destructive refresh."""
from pathlib import Path
from typing import Any

import pytest
import yaml


def _write_contracts(path: Path, picks: list[dict[str, Any]]) -> None:
    path.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def test_refresh_populates_cached_on_success(tmp_path: Path, monkeypatch) -> None:
    from build import pull_kalshi_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{"id": "kx-x", "source_lookup": {"event_ticker": "KX-X"}}])

    def fake_lookup(lookup: dict[str, str]) -> dict[str, Any] | None:
        return {"ticker": "KX-X", "title": "X", "status": "active",
                "open_time": "2026-01-01T00:00:00Z", "close_time": "2027-01-01T00:00:00Z",
                "subtitle": "", "rules_primary": "rule", "settlement_source": "FOMC"}

    monkeypatch.setattr(m, "lookup_market", fake_lookup)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    assert doc["picks"][0]["cached"]["title"] == "X"
    assert doc["picks"][0]["cached"]["status"] == "active"
    assert "last_pulled_at" in doc["picks"][0]
    assert doc["picks"][0].get("stale", False) is False


def test_refresh_demotes_to_stale_on_404(tmp_path: Path, monkeypatch) -> None:
    from build import pull_kalshi_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{
        "id": "kx-retired",
        "source_lookup": {"event_ticker": "KX-RETIRED"},
        "cached": {"title": "Retired", "status": "active"},
        "last_pulled_at": "2026-01-01T00:00:00Z",
    }])

    monkeypatch.setattr(m, "lookup_market", lambda lookup: None)
    m.refresh(contracts)
    doc = yaml.safe_load(contracts.read_text())
    # Cached block preserved
    assert doc["picks"][0]["cached"]["title"] == "Retired"
    # Stale flag set; reason recorded
    assert doc["picks"][0]["stale"] is True
    assert "stale_reason" in doc["picks"][0]


def test_refresh_skips_in_cached_mode(tmp_path: Path, monkeypatch) -> None:
    from build import pull_kalshi_curated as m

    contracts = tmp_path / "contracts.yml"
    _write_contracts(contracts, [{"id": "kx-x", "source_lookup": {"event_ticker": "KX-X"}}])

    called = []
    monkeypatch.setattr(m, "lookup_market", lambda lookup: called.append(lookup) or None)
    m.refresh(contracts, mode="cached")
    assert called == [], "cached mode must not hit the network"
    doc = yaml.safe_load(contracts.read_text())
    # No cached block added (was never there); no stale flag
    assert "cached" not in doc["picks"][0]
