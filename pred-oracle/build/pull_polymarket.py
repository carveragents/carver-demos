"""Pull market metadata from Polymarket Gamma API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"


def parse_market(raw: dict[str, Any]) -> dict[str, Any]:
    # TODO: Polymarket's `closed` boolean collapses archived/disputed/paused markets
    # into "active". Demo accepts this lossiness; production should expand to a richer
    # state machine when those states appear in the corpus.
    return {
        "external_id": str(raw.get("id", "")),
        "title": raw.get("question", ""),
        "subtitle": "",
        "resolution_criteria": raw.get("description", ""),
        "listed_at": raw.get("startDate", ""),
        "expires_at": raw.get("endDate", ""),
        "status": "resolved" if raw.get("closed") else "active",
        "settlement_entities": [],  # TODO: UMA Optimistic Oracle, not named agency
        "platform": "polymarket",
        "payload": raw,
    }


def fetch_markets(limit: int = 200) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    page_size = 100

    while len(out) < limit:
        resp = httpx.get(
            GAMMA_MARKETS_URL,
            params={
                "limit": page_size,
                "offset": offset,
                "order": "startDate",
                "ascending": "false",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        if not isinstance(body, list) or not body:
            break
        out.extend(body)
        if len(body) < page_size:
            break
        offset += page_size
    return out[:limit]


def main() -> int:
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "data" / "platforms" / "polymarket"
    out_dir.mkdir(parents=True, exist_ok=True)

    markets = fetch_markets(limit=200)
    parsed = [parse_market(m) for m in markets]
    out_path = out_dir / "contracts_raw.json"
    out_path.write_text(json.dumps(parsed, indent=2))
    print(f"Wrote {len(parsed)} Polymarket markets to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
