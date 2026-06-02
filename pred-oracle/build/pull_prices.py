"""Fetch probability time series for all trader contracts."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build._prices import fetch_and_cache  # noqa: E402


def main() -> None:
    REPO = Path(__file__).resolve().parent.parent
    curation = yaml.safe_load(
        (REPO / "data" / "trader-curation.yml").read_text()
    )

    kalshi_doc = yaml.safe_load(
        (REPO / "data" / "platforms" / "kalshi" / "contracts.yml").read_text()
    )
    poly_doc = yaml.safe_load(
        (REPO / "data" / "platforms" / "polymarket" / "contracts.yml").read_text()
    )

    kalshi_picks = {p["id"]: p for p in kalshi_doc.get("picks", [])}
    poly_picks = {p["id"]: p for p in poly_doc.get("picks", [])}

    all_contracts = curation["portfolio"] + curation.get("retrospectives", [])

    for entry in all_contracts:
        cid = entry["id"]
        platform = entry["platform"]

        if platform == "kalshi":
            pick = kalshi_picks.get(cid)
            if not pick:
                retro_path = REPO / "data" / "platforms" / "kalshi" / "contracts" / f"{cid}.yml"
                if retro_path.exists():
                    retro = yaml.safe_load(retro_path.read_text())
                    ticker = cid.upper()
                    listed = retro.get("listed_at", "2025-01-01")
                    start_ts = int(datetime.fromisoformat(listed + "T00:00:00").timestamp())
                    resolved = retro.get("resolved_at", "")
                    end_ts = int(datetime.fromisoformat(
                        (resolved or date.today().isoformat()) + "T23:59:59"
                    ).timestamp())
                    try:
                        data = fetch_and_cache(
                            contract_id=cid, platform="kalshi", ticker=ticker,
                            start_ts=start_ts, end_ts=end_ts,
                            is_historical=bool(resolved),
                        )
                        print(f"  {cid}: {len(data.series)} price points")
                    except Exception as e:
                        print(f"  WARN: {cid} fetch failed: {e}")
                    continue
                print(f"  WARN: {cid} not found in kalshi picks or retrospectives")
                continue
            cached = pick["cached"]
            ticker = cached.get("ticker", "")
            listed = cached.get("listed_at", "2025-01-01T00:00:00Z")
            start_ts = int(datetime.fromisoformat(listed.replace("Z", "+00:00")).timestamp())
            end_ts = int(datetime.now().timestamp())
            try:
                data = fetch_and_cache(
                    contract_id=cid, platform="kalshi", ticker=ticker,
                    start_ts=start_ts, end_ts=end_ts,
                )
                print(f"  {cid}: {len(data.series)} price points")
            except Exception as e:
                print(f"  WARN: {cid} fetch failed: {e}")

        elif platform == "polymarket":
            pick = poly_picks.get(cid)
            slug = cid
            token_id = ""
            if pick:
                slug = pick.get("source_lookup", {}).get("slug", cid)
                cached = pick.get("cached", {})
                clob_tokens = cached.get("clob_token_ids", [])
                if clob_tokens:
                    token_id = clob_tokens[0]
            if not token_id:
                retro_path = REPO / "data" / "platforms" / "polymarket" / "contracts" / f"{cid}.yml"
                if retro_path.exists():
                    retro = yaml.safe_load(retro_path.read_text())
                    clob_tokens = retro.get("clob_token_ids", [])
                    if clob_tokens:
                        token_id = clob_tokens[0]
                    slug = retro.get("polymarket_slug", slug)
            try:
                data = fetch_and_cache(
                    contract_id=cid, platform="polymarket", ticker=slug, slug=slug,
                    token_id=token_id,
                )
                print(f"  {cid}: {len(data.series)} price points (platform={data.platform})")
            except Exception as e:
                print(f"  WARN: {cid} fetch failed: {e}")
        else:
            print(f"  WARN: unknown platform {platform} for {cid}")


if __name__ == "__main__":
    main()
