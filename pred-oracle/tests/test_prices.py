from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from build._prices import (
    normalize_kalshi_candles,
    normalize_polymarket_history,
    load_cached,
    save_cache,
    PriceData,
)


def test_normalize_kalshi_candles():
    raw = [
        {"end_period_ts": 1700000000, "price": {"close": "0.5500"}, "volume": "10"},
        {"end_period_ts": 1700086400, "price": {"close": "0.6200"}, "volume": "5"},
    ]
    result = normalize_kalshi_candles(raw)
    assert len(result) == 2
    assert result[0] == {"t": 1700000000, "p": 0.55}
    assert result[1] == {"t": 1700086400, "p": 0.62}


def test_normalize_polymarket_history():
    raw = [
        {"t": 1700000000, "p": 0.45},
        {"t": 1700086400, "p": 0.51},
    ]
    result = normalize_polymarket_history(raw)
    assert result == raw


def test_cache_round_trip(tmp_path: Path):
    data = PriceData(
        contract_id="test-contract",
        platform="kalshi",
        ticker="TEST-TICKER",
        fetched_at="2026-05-25",
        series=[{"t": 1700000000, "p": 0.55}],
    )
    save_cache(data, cache_dir=tmp_path)
    loaded = load_cached("test-contract", cache_dir=tmp_path)
    assert loaded is not None
    assert loaded.contract_id == "test-contract"
    assert loaded.series == [{"t": 1700000000, "p": 0.55}]


def test_load_cached_returns_none_when_missing(tmp_path: Path):
    result = load_cached("nonexistent", cache_dir=tmp_path)
    assert result is None
