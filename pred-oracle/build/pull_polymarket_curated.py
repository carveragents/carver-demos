"""Curated-pull for Polymarket contracts. Same stale-flag policy as Kalshi."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import httpx
import yaml


GAMMA_BASE = "https://gamma-api.polymarket.com"
_TIMEOUT_S = 20.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lookup_market(lookup: dict[str, str]) -> dict[str, Any] | None:
    """Try slug first, then condition_id. Return None on any miss/error."""
    if "slug" in lookup:
        try:
            r = httpx.get(f"{GAMMA_BASE}/markets", params={"slug": lookup["slug"]}, timeout=_TIMEOUT_S)
        except httpx.RequestError:
            return None
        if r.status_code != 200:
            return None
        body = cast(list[dict[str, Any]], r.json())
        if isinstance(body, list) and body:
            return body[0]
        return None
    if "condition_id" in lookup:
        try:
            r = httpx.get(f"{GAMMA_BASE}/markets", params={"condition_ids": lookup["condition_id"]},
                          timeout=_TIMEOUT_S)
        except httpx.RequestError:
            return None
        if r.status_code != 200:
            return None
        body = cast(list[dict[str, Any]], r.json())
        if isinstance(body, list) and body:
            return body[0]
    return None


def _project(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": raw.get("question", ""),
        "subtitle": "",
        "resolution_criteria": raw.get("description", ""),
        "external_id": str(raw.get("id", "")),
        "slug": raw.get("slug", ""),
        "condition_id": raw.get("conditionId", ""),
        "status": "resolved" if raw.get("closed") else "active",
        "listed_at": raw.get("startDate", ""),
        "expires_at": raw.get("endDate", ""),
        "settlement_entities": [],
    }


def refresh(contracts_path: Path, mode: str = "fresh") -> dict[str, Any]:
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
            pick["stale"] = True
            pick["stale_reason"] = "upstream lookup returned no result"
            pick["stale_detected_at"] = _iso_now()

    contracts_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("cached", "fresh"), default="cached")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    contracts = repo / "data" / "platforms" / "polymarket" / "contracts.yml"
    doc = refresh(contracts, mode=args.mode)
    n_stale = sum(1 for p in doc["picks"] if p.get("stale"))
    n_fresh = sum(1 for p in doc["picks"] if p.get("cached") and not p.get("stale"))
    print(f"polymarket curated pull ({args.mode}): {n_fresh} fresh, {n_stale} stale, "
          f"{len(doc['picks'])} total picks", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
