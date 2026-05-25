"""Pull listed-market metadata from Kalshi's public API.

API: https://external-api.kalshi.com/trade-api/v2/markets
No auth required for read endpoints (per docs.kalshi.com).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

KALSHI_MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"


def parse_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Project a Kalshi market dict into Pred-Oracle's contract schema."""
    status_map = {
        "open": "active",
        "active": "active",
        "settled": "resolved",
        "closed": "resolved",
    }
    return {
        "external_id": raw.get("ticker", ""),
        "title": raw.get("title", ""),
        "subtitle": raw.get("subtitle", ""),
        "resolution_criteria": raw.get("rules_primary", raw.get("subtitle", "")),
        "listed_at": raw.get("open_time", ""),
        "expires_at": raw.get("close_time", ""),
        "status": status_map.get(raw.get("status", ""), "active"),
        "settlement_entities": [raw["settlement_source"]] if raw.get("settlement_source") else [],
        "platform": "kalshi",
        "payload": raw,
    }


def fetch_markets(limit: int = 200) -> list[dict[str, Any]]:
    """Hit Kalshi's public markets endpoint with pagination."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    page_size = 100

    while len(out) < limit:
        params: dict[str, Any] = {"limit": page_size}
        if cursor:
            params["cursor"] = cursor
        resp = httpx.get(KALSHI_MARKETS_URL, params=params, timeout=30.0)
        resp.raise_for_status()
        body = resp.json()
        markets = body.get("markets", [])
        if not markets:
            break
        out.extend(markets)
        cursor = body.get("cursor")
        if not cursor:
            break
    return out[:limit]


def main() -> int:
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "data" / "platforms" / "kalshi"
    out_dir.mkdir(parents=True, exist_ok=True)

    markets = fetch_markets(limit=200)
    parsed = [parse_market(m) for m in markets]
    out_path = out_dir / "contracts_raw.json"
    out_path.write_text(json.dumps(parsed, indent=2))
    print(f"Wrote {len(parsed)} Kalshi markets to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
