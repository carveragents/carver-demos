"""Fetch + cache probability time series from Kalshi and Polymarket APIs."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

import httpx

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "_cache" / "prices"

KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"
KALSHI_HISTORICAL_BASE = "https://external-api.kalshi.com/trade-api/v2/historical"
POLYMARKET_CLOB_BASE = "https://clob.polymarket.com"
POLYMARKET_GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclass
class PriceData:
    contract_id: str
    platform: str
    ticker: str
    fetched_at: str
    series: list[dict[str, Any]]


def normalize_kalshi_candles(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for c in candles:
        price = c.get("price", {})
        # Historical API uses "close"; active API uses "close_dollars"
        close = price.get("close") or price.get("close_dollars")
        if close is None:
            continue
        result.append({"t": c["end_period_ts"], "p": float(close)})
    return result


def normalize_polymarket_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"t": h["t"], "p": h["p"]} for h in history]


def save_cache(data: PriceData, *, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{data.contract_id}.json"
    path.write_text(json.dumps(asdict(data), indent=2))
    return path


def load_cached(
    contract_id: str, *, cache_dir: Path = DEFAULT_CACHE_DIR,
) -> PriceData | None:
    path = cache_dir / f"{contract_id}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return PriceData(**raw)


def fetch_kalshi(
    *,
    ticker: str,
    start_ts: int,
    end_ts: int,
    is_historical: bool = False,
) -> list[dict[str, Any]]:
    if is_historical:
        url = f"{KALSHI_HISTORICAL_BASE}/markets/{ticker}/candlesticks"
    else:
        url = f"{KALSHI_BASE}/series/{ticker}/markets/{ticker}/candlesticks"
    params = {"period_interval": 1440, "start_ts": start_ts, "end_ts": end_ts}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("candlesticks", [])


def fetch_polymarket(
    *, slug: str, condition_id: str = "", token_id: str = "",
) -> list[dict[str, Any]]:
    if token_id:
        price_resp = httpx.get(
            f"{POLYMARKET_CLOB_BASE}/prices-history",
            params={"market": token_id, "interval": "max", "fidelity": 720},
            timeout=30,
        )
        price_resp.raise_for_status()
        return price_resp.json().get("history", [])
    gamma_resp = httpx.get(
        f"{POLYMARKET_GAMMA_BASE}/markets",
        params={"slug": slug},
        timeout=30,
    )
    gamma_resp.raise_for_status()
    markets = gamma_resp.json()
    if not markets:
        return []
    market = markets[0] if isinstance(markets, list) else markets
    token_ids = market.get("clobTokenIds", [])
    if isinstance(token_ids, str):
        import json as _json
        token_ids = _json.loads(token_ids)
    if not token_ids:
        return []
    token_id = token_ids[0]
    price_resp = httpx.get(
        f"{POLYMARKET_CLOB_BASE}/prices-history",
        params={"market": token_id, "interval": "max", "fidelity": 720},
        timeout=30,
    )
    price_resp.raise_for_status()
    return price_resp.json().get("history", [])


def fetch_and_cache(
    *,
    contract_id: str,
    platform: str,
    ticker: str,
    slug: str = "",
    token_id: str = "",
    start_ts: int = 0,
    end_ts: int = 0,
    is_historical: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> PriceData:
    cached = load_cached(contract_id, cache_dir=cache_dir)
    if cached is not None:
        return cached

    if platform == "kalshi":
        raw = fetch_kalshi(
            ticker=ticker, start_ts=start_ts, end_ts=end_ts,
            is_historical=is_historical,
        )
        series = normalize_kalshi_candles(raw)
    elif platform == "polymarket":
        raw = fetch_polymarket(slug=slug or contract_id, token_id=token_id)
        series = normalize_polymarket_history(raw)
    else:
        series = []

    data = PriceData(
        contract_id=contract_id,
        platform=platform,
        ticker=ticker,
        fetched_at=date.today().isoformat(),
        series=series,
    )
    save_cache(data, cache_dir=cache_dir)
    return data
