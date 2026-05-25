"""Validate data/platforms/*/contracts.yml shape."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
KALSHI = REPO / "data" / "platforms" / "kalshi" / "contracts.yml"
POLYMARKET = REPO / "data" / "platforms" / "polymarket" / "contracts.yml"


def _validate(path: Path, expected_keys: set[str]) -> None:
    doc = yaml.safe_load(path.read_text())
    assert isinstance(doc, dict)
    assert doc["schema_version"] == 1
    assert isinstance(doc["picks"], list) and len(doc["picks"]) >= 1
    for p in doc["picks"]:
        assert "id" in p
        assert p.get("source_lookup", {}).keys() & expected_keys, \
            f"pick {p['id']} missing source_lookup key in {expected_keys}"
        # Cached block optional but if present must be a dict
        if "cached" in p:
            assert isinstance(p["cached"], dict)
        # stale flag must be bool if present
        if "stale" in p:
            assert isinstance(p["stale"], bool)


def test_kalshi_contracts_shape() -> None:
    _validate(KALSHI, {"event_ticker", "series_ticker", "ticker"})


def test_polymarket_contracts_shape() -> None:
    _validate(POLYMARKET, {"slug", "condition_id"})


def test_kalshi_pick_ids_unique() -> None:
    doc = yaml.safe_load(KALSHI.read_text())
    ids = [p["id"] for p in doc["picks"]]
    assert len(set(ids)) == len(ids)


def test_polymarket_pick_ids_unique() -> None:
    doc = yaml.safe_load(POLYMARKET.read_text())
    ids = [p["id"] for p in doc["picks"]]
    assert len(set(ids)) == len(ids)
