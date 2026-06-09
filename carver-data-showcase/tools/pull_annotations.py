"""Pull a snapshot of Carver annotation artifacts to a local JSONL file.

Offset-paginated, resumable, read-only GET against the direct Artifacts API
(see docs/data-access.md). Capped at MAX_RECORDS to keep the showcase sample inside
the required 30K-100K band. Run once; present from the file.

Run: .venv/bin/python tools/pull_annotations.py
Resume after interruption: it appends, and you can pass --start-offset N.
"""

import argparse
import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))  # explicit path (see LESSONS)

BASE = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai")
KEY = os.environ["CARVER_API_KEY"]
DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
CHUNK = 10_000           # max page before the listing GET 502s
MAX_RECORDS = 60_000     # stay within the 30K-100K showcase band
HEADERS = {"X-API-Key": KEY}


def pull(out_path: str, start_offset: int = 0, max_records: int = MAX_RECORDS) -> int:
    offset = start_offset
    total = 0
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    mode = "a" if start_offset > 0 else "w"
    with httpx.Client(timeout=300) as client, open(out_path, mode) as fh:
        while total < max_records:
            limit = min(CHUNK, max_records - total)
            url = (
                f"{BASE}/api/v1/artifacts/dags/{DAG}/artifacts"
                f"?state=completed&dry_run=true&artifact_type_id=annotations-v1"
                f"&limit={limit}&offset={offset}"
            )
            rows = client.get(url, headers=HEADERS).raise_for_status().json()
            if not rows:                       # empty page -> done
                break
            for art in rows:
                fh.write(json.dumps(art) + "\n")
            fh.flush()
            total += len(rows)
            print(f"offset={offset} fetched={len(rows)} total={total}", flush=True)
            if len(rows) < limit:              # short page -> last page
                break
            offset += len(rows)
            time.sleep(0.2)
    print(f"DONE total={total} -> {out_path}", flush=True)
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "annotations.jsonl"))
    ap.add_argument("--start-offset", type=int, default=0)
    ap.add_argument("--max-records", type=int, default=MAX_RECORDS)
    args = ap.parse_args()
    n = pull(args.out, args.start_offset, args.max_records)
    if n < 30_000:
        print(f"WARNING: pulled {n} < 30K floor", file=sys.stderr)
