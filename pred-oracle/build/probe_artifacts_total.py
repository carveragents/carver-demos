"""Probe total annotation corpus size and check param variations from carver-dags reference."""
import json
import os
import time
from collections import Counter

import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["CARVER_API_KEY"]
BASE = "https://app.carveragents.ai"
SOURCE_DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"


def probe(label, params):
    url = f"{BASE}/api/v1/artifacts/dags/{SOURCE_DAG}/artifacts"
    t = time.time()
    r = httpx.get(url, params=params, headers={"X-API-Key": API_KEY}, timeout=120.0)
    elapsed = time.time() - t
    if r.status_code != 200:
        print(f"\n=== {label}")
        print(f"  params: {params}")
        print(f"  status={r.status_code} elapsed={elapsed:.2f}s body={r.text[:300]}")
        return None
    body = r.json()
    n = len(body) if isinstance(body, list) else f"dict keys={list(body.keys())[:5]}"
    states = "—"
    types = "—"
    has_output = "—"
    distinct_topics = "—"
    if isinstance(body, list) and body:
        states = dict(Counter(a.get("state") for a in body))
        types = dict(Counter(a.get("artifact_type_id") for a in body))
        has_output = sum(1 for a in body if a.get("output_data"))
        distinct_topics = len(set(a.get("topic_id") for a in body if a.get("topic_id")))
    print(f"\n=== {label}")
    print(f"  params: {params}")
    print(f"  status={r.status_code} elapsed={elapsed:.2f}s count={n} states={states} types={types} with_output={has_output} distinct_topics={distinct_topics}")
    return body


# L: No topic filter, state=completed — how big is the corpus globally?
probe("L (no topic filter, state=completed, limit=1)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed", "limit": 1, "offset": 0})

# M: dag_state=completed (Carver-internal pattern), no topic filter
probe("M (dag_state=completed, return_type=single, limit=1)",
      {"dag_ids_in": SOURCE_DAG, "dag_state": "completed",
       "return_type": "single", "limit": 1, "offset": 0})

# N: dag_state=completed WITH dry_run=false (full asset_generation pattern)
probe("N (dag_state=completed, dry_run=false, return_type=single, limit=1)",
      {"dag_ids_in": SOURCE_DAG, "dag_state": "completed", "dry_run": "false",
       "return_type": "single", "limit": 1, "offset": 0})

# O: state=completed + return_type=multi (vector_embeddings pattern)
probe("O (state=completed, return_type=multi, limit=1)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed",
       "return_type": "multi", "limit": 1, "offset": 0})

# P: artifact_type_id explicit — what types exist? Try the default
probe("P (state=completed, artifact_type_id=annotations-v1, limit=1)",
      {"dag_ids_in": SOURCE_DAG, "state": "completed",
       "artifact_type_id": "annotations-v1", "limit": 1, "offset": 0})

# Q: Paginate to count — page 1 of 10K, no topic filter
b = probe("Q (no topic filter, state=completed, limit=10000, offset=0)",
          {"dag_ids_in": SOURCE_DAG, "state": "completed", "limit": 10000, "offset": 0})

# R: Page 2
b2 = probe("R (no topic filter, state=completed, limit=10000, offset=10000)",
           {"dag_ids_in": SOURCE_DAG, "state": "completed", "limit": 10000, "offset": 10000})

# S: Page 3
b3 = probe("S (no topic filter, state=completed, limit=10000, offset=20000)",
           {"dag_ids_in": SOURCE_DAG, "state": "completed", "limit": 10000, "offset": 20000})

# T: Page 10 — if there's >100K records this still has content
b4 = probe("T (no topic filter, state=completed, limit=10000, offset=100000)",
           {"dag_ids_in": SOURCE_DAG, "state": "completed", "limit": 10000, "offset": 100000})

# U: Even further
b5 = probe("U (no topic filter, state=completed, limit=10000, offset=200000)",
           {"dag_ids_in": SOURCE_DAG, "state": "completed", "limit": 10000, "offset": 200000})
