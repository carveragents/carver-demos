"""Curated-pull for Kalshi contracts.

Reads data/platforms/kalshi/contracts.yml pick-list. For each pick, looks up
the live market via Kalshi's public API. On success, updates the `cached` block
in-place and records `last_pulled_at`. On 404 (or any unsuccessful lookup),
LEAVES the existing `cached` block intact and sets `stale: true` plus
`stale_reason` and `stale_detected_at`.

Modes:
  --mode=cached   (default) — no network. YAML untouched.
  --mode=fresh    — hit the API for each pick; non-destructive on failure.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import httpx
import yaml


KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"
_TIMEOUT_S = 20.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lookup_market(lookup: dict[str, str]) -> dict[str, Any] | None:
    """Return a single raw market dict from Kalshi, or None on miss/error.

    Tries the lookup keys in priority order: ticker > event_ticker > series_ticker.
    """
    params: dict[str, Any] = {"limit": 1}
    if "ticker" in lookup:
        try:
            r = httpx.get(f"{KALSHI_BASE}/markets/{lookup['ticker']}", timeout=_TIMEOUT_S)
            if r.status_code == 200:
                market = cast(dict[str, Any] | None, r.json().get("market"))
                return market
        except httpx.RequestError:
            return None
        return None
    if "event_ticker" in lookup:
        params["event_ticker"] = lookup["event_ticker"]
    elif "series_ticker" in lookup:
        params["series_ticker"] = lookup["series_ticker"]
    else:
        return None
    try:
        r = httpx.get(f"{KALSHI_BASE}/markets", params=params, timeout=_TIMEOUT_S)
    except httpx.RequestError:
        return None
    if r.status_code != 200:
        return None
    markets = (r.json() or {}).get("markets") or []
    return markets[0] if markets else None


def _project(raw: dict[str, Any]) -> dict[str, Any]:
    """Project the raw Kalshi market into our cached metadata shape."""
    return {
        "title": raw.get("title", ""),
        "subtitle": raw.get("subtitle", ""),
        "resolution_criteria": raw.get("rules_primary", "") or raw.get("subtitle", ""),
        "ticker": raw.get("ticker", ""),
        "status": "resolved" if raw.get("status") in {"settled", "closed"} else "active",
        "listed_at": raw.get("open_time", ""),
        "expires_at": raw.get("close_time", ""),
        "settlement_entities": [raw["settlement_source"]] if raw.get("settlement_source") else [],
    }


def refresh(contracts_path: Path, mode: str = "fresh") -> dict[str, Any]:
    """Refresh-or-cache. Returns the resulting YAML doc."""
    doc = cast(dict[str, Any], yaml.safe_load(contracts_path.read_text()))
    if mode == "cached":
        return doc

    for pick in doc["picks"]:
        raw = lookup_market(pick["source_lookup"])
        if raw is not None:
            pick["cached"] = _project(raw)
            pick["last_pulled_at"] = _iso_now()
            pick.pop("stale", None)
            pick.pop("stale_reason", None)
            pick.pop("stale_detected_at", None)
        else:
            # Non-destructive: keep existing cached if any; set stale flags
            pick["stale"] = True
            pick["stale_reason"] = "upstream lookup returned no result (404 or empty)"
            pick["stale_detected_at"] = _iso_now()

    contracts_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("cached", "fresh"), default="cached")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    contracts = repo / "data" / "platforms" / "kalshi" / "contracts.yml"
    doc = refresh(contracts, mode=args.mode)
    n_stale = sum(1 for p in doc["picks"] if p.get("stale"))
    n_fresh = sum(1 for p in doc["picks"] if p.get("cached") and not p.get("stale"))
    print(f"kalshi curated pull ({args.mode}): {n_fresh} fresh, {n_stale} stale, "
          f"{len(doc['picks'])} total picks", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
