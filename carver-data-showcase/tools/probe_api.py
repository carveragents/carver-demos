"""Read-only probe of the Carver Artifacts API.

Confirms credentials work and prints the real shape of one annotation record so we
can validate docs/data-model.md against the live payload before the full pull.
Run: .venv/bin/python tools/probe_api.py
"""

import json
import os

import httpx
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))  # explicit path (see LESSONS)

BASE = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai")
KEY = os.environ["CARVER_API_KEY"]
DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
HEADERS = {"X-API-Key": KEY}


def probe(limit: int = 2, offset: int = 0) -> list:
    url = (
        f"{BASE}/api/v1/artifacts/dags/{DAG}/artifacts"
        f"?state=completed&dry_run=true&artifact_type_id=annotations-v1"
        f"&limit={limit}&offset={offset}"
    )
    with httpx.Client(timeout=120) as client:
        resp = client.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


def summarize_keys(obj, prefix="", depth=0, max_depth=3):
    """Print nested key structure (not values) to inspect shape safely."""
    if depth > max_depth or not isinstance(obj, dict):
        return
    for k, v in obj.items():
        kind = type(v).__name__
        if isinstance(v, dict):
            print(f"{'  ' * depth}{k}: dict")
            summarize_keys(v, prefix + k + ".", depth + 1, max_depth)
        elif isinstance(v, list):
            inner = type(v[0]).__name__ if v else "empty"
            print(f"{'  ' * depth}{k}: list[{inner}] (len={len(v)})")
        else:
            print(f"{'  ' * depth}{k}: {kind}")


if __name__ == "__main__":
    rows = probe(limit=2, offset=0)
    print(f"=== returned {len(rows)} envelope(s) ===\n")
    if not rows:
        raise SystemExit("No rows returned — check credentials / DAG id.")
    env = rows[0]
    print("=== ENVELOPE keys ===")
    for k in env:
        print(f"  {k}: {type(env[k]).__name__}")
    print("\n=== output_data (the annotation) structure ===")
    summarize_keys(env.get("output_data", {}), max_depth=3)
    print("\n=== sample scalar values (truncated) ===")
    od = env.get("output_data", {})
    print("  topic_id:", env.get("topic_id"))
    print("  state:", env.get("state"))
    print("  created_at:", env.get("created_at"))
    cls = od.get("classification", {})
    print("  classification.update_type:", cls.get("update_type"))
    juris = cls.get("jurisdiction")
    print("  classification.jurisdiction keys:", list(juris.keys()) if isinstance(juris, dict) else juris)
    print("  has jurisdiction_tier:", "jurisdiction_tier" in cls)
    scores = od.get("scores", {})
    print("  scores keys:", list(scores.keys()))
