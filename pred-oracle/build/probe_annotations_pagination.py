"""Probe Carver Feeds /api/v1/core/annotations endpoint for pagination support.

Determines if the endpoint honors limit/offset (or cursor-based) pagination,
or silently ignores pagination params and returns full result.

Usage:
    uv run python build/probe_annotations_pagination.py

Environment:
    CARVER_API_KEY  Required. Carver Feeds API key.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env
load_dotenv()
api_key = os.getenv("CARVER_API_KEY")
if not api_key:
    raise ValueError("CARVER_API_KEY not set")

BASE_URL = "https://app.carveragents.ai"
HEADERS = {"X-API-Key": api_key}

# Load topic_id from first event in carver-events.json
events_path = Path("data/carver-events.json")
with open(events_path) as f:
    events = json.load(f)
    topic_id = events[0]["topic_id"]

print(f"Probing with topic_id: {topic_id}\n")

# Four probe calls
probes = [
    ("A (baseline, no pagination)", {}),
    ("B (small limit: 10)", {"limit": 10, "offset": 0}),
    ("C (next page: offset 10)", {"limit": 10, "offset": 10}),
    ("D (large limit: 10000)", {"limit": 10000, "offset": 0}),
]

results = []

for label, pagination_params in probes:
    params = {"topic_ids_in": topic_id, **pagination_params}
    url = f"{BASE_URL}/api/v1/core/annotations"

    start = time.time()
    resp = httpx.get(url, headers=HEADERS, params=params)
    elapsed = time.time() - start

    # Parse response
    status = resp.status_code
    data = resp.json() if resp.status_code == 200 else None

    # Extract info
    is_list = isinstance(data, list)
    count = len(data) if is_list else None

    first_item = data[0] if (is_list and data) else None
    first_entry_id = first_item.get("feed_entry_id") if first_item else None

    # Pagination-flavored headers
    headers_of_interest = {}
    for key in ["X-Total-Count", "Link", "Content-Range", "X-Limit", "X-Offset"]:
        if key in resp.headers:
            headers_of_interest[key] = resp.headers[key]

    result = {
        "label": label,
        "params": pagination_params,
        "status": status,
        "elapsed_s": round(elapsed, 3),
        "response_type": "list" if is_list else "dict",
        "count": count,
        "first_entry_id": first_entry_id,
        "headers": headers_of_interest,
        "response_sample": (
            [data[0], data[1]] if (is_list and len(data) >= 2)
            else [data[0]] if (is_list and len(data) == 1)
            else data
        ),
    }
    results.append(result)

    print(f"{label}")
    print(f"  Status: {status}")
    print(f"  Time: {result['elapsed_s']}s")
    print(f"  Response: {result['response_type']}, count={count}")
    if first_entry_id:
        print(f"  First entry_id: {first_entry_id}")
    if headers_of_interest:
        print(f"  Pagination headers: {headers_of_interest}")
    print()

# Write results to JSON for markdown report generation
output_path = Path("data/a0-pagination-probe.json")
with open(output_path, "w") as f:
    json.dump({
        "timestamp": datetime.utcnow().isoformat(),
        "topic_id": topic_id,
        "results": results,
    }, f, indent=2, default=str)

print(f"\nProbe complete. Results saved to {output_path}")

# Quick verdict based on results
a_count = results[0]["count"]
b_count = results[1]["count"]
c_count = results[2]["count"]
d_count = results[3]["count"]

print("\n--- Verdict ---")
if b_count == 10 and c_count == 10:
    print("✓ limit/offset HONORED — server-side pagination works")
elif a_count == b_count == c_count == d_count:
    print("✗ limit/offset IGNORED — server returns full result regardless")
elif all(r["status"] != 200 for r in results[1:]):
    print("✗ Endpoint ERRORS on pagination params")
else:
    print("? Unclear — mixed behavior or cursor-based pagination")
