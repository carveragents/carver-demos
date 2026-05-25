"""Probe the artifacts API with multiple state filters against a CFTC topic.

Stage 1 A0' follow-up — determine whether `dag_state=completed` or `state=completed`
is the right filter to get artifacts with populated `output_data`.
"""
import os
import time
from collections import Counter

import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["CARVER_API_KEY"]
BASE = "https://app.carveragents.ai"
SOURCE_DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
CFTC_TOPIC = "6559f9b0-5add-4ad4-a94e-80f9e035e372"


def probe(label, params):
    url = f"{BASE}/api/v1/artifacts/dags/{SOURCE_DAG}/artifacts"
    t = time.time()
    r = httpx.get(url, params=params, headers={"X-API-Key": API_KEY}, timeout=60.0)
    elapsed = time.time() - t
    body = r.json() if r.status_code == 200 else r.text
    n = len(body) if isinstance(body, list) else "—"
    states = "—"
    has_output = "—"
    if isinstance(body, list) and body:
        states = dict(Counter(a.get("state") for a in body))
        has_output = sum(1 for a in body if a.get("output_data"))
    print(f"\n=== {label}")
    print(f"  params: {params}")
    print(f"  status={r.status_code} elapsed={elapsed:.2f}s count={n} state_counts={states} with_output_data={has_output}")


probe("F (CFTC, dag_state=completed, limit=100)",
      {"dag_ids_in": SOURCE_DAG, "dag_state": "completed",
       "topic_id_in": CFTC_TOPIC, "limit": 100, "offset": 0})

probe("G (CFTC, state=completed, limit=100)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed",
       "topic_id_in": CFTC_TOPIC, "limit": 100, "offset": 0})

probe("H (CFTC, no state filter, limit=100)",
      {"dag_ids_in": SOURCE_DAG,
       "topic_id_in": CFTC_TOPIC, "limit": 100, "offset": 0})

probe("I (CFTC, state=completed, created_after=2024-01-01, limit=100)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed",
       "topic_id_in": CFTC_TOPIC, "created_after": "2024-01-01T00:00:00Z",
       "limit": 100, "offset": 0})

probe("J (CFTC, state=completed, limit=10000)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed",
       "topic_id_in": CFTC_TOPIC, "limit": 10000, "offset": 0})

probe("K (CFTC, state=completed, limit=10000, offset=10000)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed",
       "topic_id_in": CFTC_TOPIC, "limit": 10000, "offset": 10000})
