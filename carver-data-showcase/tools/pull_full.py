"""Pull the FULL annotation corpus via the direct Artifacts API (no SDK, no LLM).

The showcase v1 used a 58,982-record category-stratified sample (Finance capped at
40K) for visual balance.  For an externally-consumable showcase with *complete*
statistics, this puller takes the entire corpus via a plain offset walk (the whole
corpus is ~211K records; a probe confirmed a no-filter walk paginates cleanly).

Category is recovered at normalize time by joining data/topic_categories.csv
(topic_id -> most-specific category); topics absent from that map — including the
~461 uncategorized institutions and any topic not in the catalog — become
"Uncategorized", which the apps render honestly.

Writes:
  data/annotations.jsonl   the full corpus (atomic: temp file then rename)
  data/snapshot_meta.json  provenance: pull date (UTC), scope="full", total

Run: .venv/bin/python tools/pull_full.py
"""

import datetime
import json
import os
import sys

import httpx
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))

BASE = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai")
KEY = os.environ["CARVER_API_KEY"]
DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
HEADERS = {"X-API-Key": KEY}
CHUNK = 10_000
HARD_CAP = 400_000  # safety ceiling well above the observed ~211K corpus

OUT = os.path.join(ROOT, "data", "annotations.jsonl")
TMP = OUT + ".tmp"
PARQUET = os.path.join(ROOT, "data", "annotations.parquet")
META = os.path.join(ROOT, "data", "snapshot_meta.json")


def pull_all(client, fh):
    """Offset-walk the whole corpus (no topic filter), writing each envelope."""
    offset, total = 0, 0
    while total < HARD_CAP:
        # dry_run=true is the catalog's standard read mode for this artifact type — it
        # returns the full real annotation rows (not a truncated preview); the existing
        # snapshots were built this way. Do not "fix" it to false.
        url = (f"{BASE}/api/v1/artifacts/dags/{DAG}/artifacts?state=completed&dry_run=true"
               f"&artifact_type_id=annotations-v1&limit={CHUNK}&offset={offset}")
        rows = client.get(url, headers=HEADERS).raise_for_status().json()
        if not rows:
            break
        for art in rows:
            fh.write(json.dumps(art) + "\n")
        total += len(rows)
        offset += len(rows)
        print(f"  offset={offset:>8,}  total={total:,}", flush=True)
        if len(rows) < CHUNK:
            break
    return total


def main():
    with httpx.Client(timeout=300) as client, open(TMP, "w") as out:
        total = pull_all(client, out)

    if total < 100_000:
        # The full corpus is ~211K; a short read means a transient API problem.
        os.remove(TMP)
        raise SystemExit(f"ERROR: only {total:,} records pulled (<100K) — refusing to "
                         "clobber the snapshot with a partial read")

    os.replace(TMP, OUT)

    # Invalidate the cached parquet so the apps don't silently serve the OLD snapshot:
    # load_normalized only rebuilds when the parquet is missing (or rebuild=True).
    if os.path.exists(PARQUET):
        os.remove(PARQUET)
        print(f"removed stale parquet {PARQUET} — apps will rebuild on next load", flush=True)

    meta = {
        "snapshot_date": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "pulled_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "full",
        "total_records": total,
        "source": "carver artifacts api — full offset walk (no topic filter)",
    }
    with open(META, "w") as mf:
        json.dump(meta, mf, indent=2)

    print(f"\nFULL SNAPSHOT total={total:,} -> {OUT}", flush=True)
    print(f"wrote {META}: {meta}", flush=True)

    # Re-render the downloadable "State of Carver Data" deck so the link the
    # gallery serves always matches the just-pulled snapshot. build_deck() calls
    # load_normalized(), which rebuilds the parquet from the fresh JSONL we wrote
    # above (we removed the stale one), then renders the PDF. The deck is a
    # downstream artifact — a render failure must NOT fail the pull.
    try:
        from carver_showcase.deck import build_deck

        deck_path = build_deck()
        print(f"re-rendered deck -> {deck_path}", flush=True)
    except Exception as exc:  # noqa: BLE001 - the pull already succeeded
        print(
            f"WARNING: deck re-render failed ({exc!r}); the pull succeeded — run "
            "tools/build_deck.py to regenerate the deck.",
            flush=True,
        )


if __name__ == "__main__":
    main()
