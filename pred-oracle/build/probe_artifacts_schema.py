"""Inspect a completed artifact's full schema."""
import json
import os
from collections import Counter

import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ["CARVER_API_KEY"]
BASE = "https://app.carveragents.ai"
SOURCE_DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
CFTC_TOPIC = "6559f9b0-5add-4ad4-a94e-80f9e035e372"

r = httpx.get(
    f"{BASE}/api/v1/artifacts/dags/{SOURCE_DAG}/artifacts",
    params={"dag_ids_in": SOURCE_DAG, "state": "completed",
            "topic_id_in": CFTC_TOPIC, "limit": 1, "offset": 0},
    headers={"X-API-Key": API_KEY}, timeout=30.0,
)
artifact = r.json()[0]
print("Full artifact JSON (first completed CFTC):")
print(json.dumps(artifact, indent=2)[:10000])
print("\n\n--- top-level keys:", sorted(artifact.keys()))
print("\n--- input_data keys:", sorted((artifact.get("input_data") or {}).keys()))
print("\n--- input_data.extracted_metadata keys:",
      sorted(((artifact.get("input_data") or {}).get("extracted_metadata") or {}).keys()))
print("\n--- output_data keys:", sorted((artifact.get("output_data") or {}).keys()))
od = artifact.get("output_data") or {}
for k in od:
    v = od[k]
    if isinstance(v, dict):
        print(f"--- output_data.{k} keys:", sorted(v.keys()))
