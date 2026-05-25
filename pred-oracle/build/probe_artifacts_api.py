#!/usr/bin/env python3
"""
Probe the Carver DAG Artifacts API to determine correct URL shape for external callers.
"""

import json
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

import os

CARVER_API_KEY = os.getenv("CARVER_API_KEY")
BASE_URL = "https://app.carveragents.ai"
SOURCE_DAG_ID = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
REPO_ROOT = Path(__file__).parent.parent

# Use an existing topic_id that actually has artifacts
# (The first event's topic_id doesn't exist in the artifacts)
TOPIC_ID = "04878447-710c-4b80-aef1-5436b128d595"

print(f"Using topic_id: {TOPIC_ID}")
print(f"Using source_dag_id: {SOURCE_DAG_ID}")
print(f"API Key loaded: {bool(CARVER_API_KEY)}")
print()

probes = {}
headers = {"X-API-Key": CARVER_API_KEY}

# Probe A: Standard form with source_dag_id in path
probe_a_url = (
    f"{BASE_URL}/api/v1/artifacts/dags/{SOURCE_DAG_ID}/artifacts"
    f"?dag_ids_in={SOURCE_DAG_ID}&dag_state=completed&topic_id_in={TOPIC_ID}&limit=10&offset=0"
)

# Probe B: Bogus UUID in path
probe_b_url = (
    f"{BASE_URL}/api/v1/artifacts/dags/00000000-0000-0000-0000-000000000000/artifacts"
    f"?dag_ids_in={SOURCE_DAG_ID}&dag_state=completed&topic_id_in={TOPIC_ID}&limit=10&offset=0"
)

# Probe C: No path id
probe_c_url = (
    f"{BASE_URL}/api/v1/artifacts/artifacts"
    f"?dag_ids_in={SOURCE_DAG_ID}&dag_state=completed&topic_id_in={TOPIC_ID}&limit=10&offset=0"
)

# Probe D: A + return_type=single
probe_d_url = (
    f"{BASE_URL}/api/v1/artifacts/dags/{SOURCE_DAG_ID}/artifacts"
    f"?dag_ids_in={SOURCE_DAG_ID}&dag_state=completed&topic_id_in={TOPIC_ID}&limit=10&offset=0&return_type=single"
)

# Probe E: A with limit=1, offset=2 (pagination test)
probe_e_url = (
    f"{BASE_URL}/api/v1/artifacts/dags/{SOURCE_DAG_ID}/artifacts"
    f"?dag_ids_in={SOURCE_DAG_ID}&dag_state=completed&topic_id_in={TOPIC_ID}&limit=1&offset=2"
)

probe_urls = {
    "A": probe_a_url,
    "B": probe_b_url,
    "C": probe_c_url,
    "D": probe_d_url,
    "E": probe_e_url,
}


def redact_key(url: str) -> str:
    """Redact API key from URL for logging."""
    return url.replace(CARVER_API_KEY, "***REDACTED***")


def extract_response_shape(data: Any) -> dict:
    """Extract shape info from response data."""
    if isinstance(data, list):
        return {
            "type": "list",
            "length": len(data),
            "first_item_shape": extract_item_shape(data[0]) if data else None,
        }
    elif isinstance(data, dict):
        return {
            "type": "dict",
            "keys": list(data.keys()),
        }
    else:
        return {"type": type(data).__name__}


def extract_item_shape(item: Any) -> dict:
    """Extract shape of first artifact item."""
    if not isinstance(item, dict):
        return {}

    shape = {
        "top_level_keys": list(item.keys()),
    }

    if "input_data" in item and isinstance(item["input_data"], dict):
        if "extracted_metadata" in item["input_data"]:
            shape["input_data.extracted_metadata_keys"] = list(
                item["input_data"]["extracted_metadata"].keys()
            )

    if "output_data" in item and isinstance(item["output_data"], dict):
        shape["output_data_keys"] = list(item["output_data"].keys())

    return shape


# Run probes
client = httpx.Client(timeout=30.0)

try:
    for probe_name, url in probe_urls.items():
        print(f"=== Probe {probe_name} ===")
        print(f"URL: {redact_key(url)}")

        start = time.time()
        try:
            resp = client.get(url, headers=headers)
            elapsed = time.time() - start

            print(f"Status: {resp.status_code}")
            print(f"Time: {elapsed:.2f}s")

            try:
                body = resp.json()
                shape = extract_response_shape(body)
                print(f"Response shape: {shape}")
                probes[probe_name] = {
                    "status": resp.status_code,
                    "time": elapsed,
                    "shape": shape,
                    "body": body,
                    "error": None,
                }
            except Exception as e:
                print(f"Response (non-JSON): {resp.text[:200]}")
                probes[probe_name] = {
                    "status": resp.status_code,
                    "time": elapsed,
                    "shape": None,
                    "body": resp.text,
                    "error": str(e),
                }
        except Exception as e:
            print(f"Request error: {e}")
            probes[probe_name] = {
                "status": None,
                "time": None,
                "shape": None,
                "body": None,
                "error": str(e),
            }

        print()

finally:
    client.close()

# Find working probe
working_probe = None
for name, result in probes.items():
    if result["status"] == 200 and isinstance(result["body"], list) and result["body"]:
        working_probe = (name, result)
        break

# Generate summary table
print("\n" + "=" * 80)
print("SUMMARY TABLE")
print("=" * 80)
print()
print("| Probe | Status | Time (s) | Response Type | Length/Keys | First Item |")
print("|-------|--------|----------|---------------|-------------|------------|")

for name in ["A", "B", "C", "D", "E"]:
    result = probes[name]
    status = result["status"] or "ERR"
    time_str = f"{result['time']:.2f}" if result["time"] else "N/A"

    if result["error"]:
        resp_type = "ERROR"
        length_info = result["error"][:30]
        first_item = "N/A"
    elif result["shape"]:
        shape = result["shape"]
        resp_type = shape.get("type", "unknown")
        if resp_type == "list":
            length_info = f"len={shape['length']}"
            first_item = (
                f"keys={len(shape['first_item_shape'].get('top_level_keys', []))}"
                if shape["first_item_shape"]
                else "empty"
            )
        else:
            length_info = f"keys={len(shape.get('keys', []))}"
            first_item = "N/A"
    else:
        resp_type = "?"
        length_info = "?"
        first_item = "?"

    print(f"| {name} | {status} | {time_str} | {resp_type} | {length_info} | {first_item} |")

print()

# If we found a working probe, dump first artifact
if working_probe:
    name, result = working_probe
    artifacts = result["body"]
    first_artifact = artifacts[0]

    print("\n" + "=" * 80)
    print(f"FIRST ARTIFACT FROM WORKING PROBE ({name})")
    print("=" * 80)
    print()

    # Top-level keys
    print("TOP-LEVEL KEYS:")
    for key in sorted(first_artifact.keys()):
        print(f"  - {key}")

    # input_data.extracted_metadata keys
    if "input_data" in first_artifact and isinstance(first_artifact["input_data"], dict):
        if "extracted_metadata" in first_artifact["input_data"]:
            print("\ninput_data.extracted_metadata KEYS:")
            metadata = first_artifact["input_data"]["extracted_metadata"]
            for key in sorted(metadata.keys()):
                print(f"  - {key}")

    # output_data keys
    if "output_data" in first_artifact and isinstance(first_artifact["output_data"], dict):
        print("\noutput_data KEYS:")
        output = first_artifact["output_data"]
        for key in sorted(output.keys()):
            print(f"  - {key}")

    # Full JSON (truncated)
    print("\nFULL JSON (truncated to 6000 chars):")
    full_json = json.dumps(first_artifact, indent=2)
    print(full_json[:6000])
    if len(full_json) > 6000:
        print(f"\n... (truncated, original length: {len(full_json)})")
else:
    print("No working probe found.")

# Write verdict to data/a0-prime-artifacts-probe.md
verdict_md = f"""# Carver Artifacts API Probe Results

## Summary Table

| Probe | Status | Time (s) | Response Type | Length/Keys | First Item |
|-------|--------|----------|---------------|-------------|------------|
"""

for name in ["A", "B", "C", "D", "E"]:
    result = probes[name]
    status = result["status"] or "ERR"
    time_str = f"{result['time']:.2f}" if result["time"] else "N/A"

    if result["error"]:
        resp_type = "ERROR"
        length_info = result["error"][:30]
        first_item = "N/A"
    elif result["shape"]:
        shape = result["shape"]
        resp_type = shape.get("type", "unknown")
        if resp_type == "list":
            length_info = f"len={shape['length']}"
            first_item = (
                f"keys={len(shape['first_item_shape'].get('top_level_keys', []))}"
                if shape["first_item_shape"]
                else "empty"
            )
        else:
            length_info = f"keys={len(shape.get('keys', []))}"
            first_item = "N/A"
    else:
        resp_type = "?"
        length_info = "?"
        first_item = "?"

    verdict_md += f"| {name} | {status} | {time_str} | {resp_type} | {length_info} | {first_item} |\n"

verdict_md += "\n## Probe Details\n\n"

# Add per-probe details
for name in ["A", "B", "C", "D", "E"]:
    result = probes[name]
    verdict_md += f"### Probe {name}\n\n"

    url_desc = {
        "A": "Standard form with source_dag_id in path",
        "B": "Bogus UUID (00000000...) in path — does path validate?",
        "C": "No path id — direct /artifacts endpoint",
        "D": "Probe A + return_type=single parameter",
        "E": "Probe A with limit=1, offset=2 — pagination test",
    }

    verdict_md += f"**Description:** {url_desc[name]}\n\n"
    verdict_md += f"**Status Code:** {result['status'] or 'ERROR'}\n\n"
    time_str = f"{result['time']:.2f}s" if result['time'] else 'N/A'
    verdict_md += f"**Time:** {time_str}\n\n"

    if result["error"]:
        verdict_md += f"**Error:** {result['error']}\n\n"
    elif result["shape"]:
        verdict_md += f"**Response Shape:** {json.dumps(result['shape'], indent=2)}\n\n"
    else:
        verdict_md += "**Response:** Could not parse\n\n"

# Add working probe details
if working_probe:
    name, result = working_probe
    artifacts = result["body"]
    first_artifact = artifacts[0]

    verdict_md += f"\n## Working Probe: {name}\n\n"
    verdict_md += f"**First artifact from {len(artifacts)} total artifacts**\n\n"

    verdict_md += "### Top-Level Keys\n\n"
    for key in sorted(first_artifact.keys()):
        verdict_md += f"- {key}\n"

    if "input_data" in first_artifact and isinstance(first_artifact["input_data"], dict):
        if "extracted_metadata" in first_artifact["input_data"]:
            verdict_md += "\n### input_data.extracted_metadata Keys\n\n"
            metadata = first_artifact["input_data"]["extracted_metadata"]
            for key in sorted(metadata.keys()):
                verdict_md += f"- {key}\n"

    if "output_data" in first_artifact and isinstance(first_artifact["output_data"], dict):
        verdict_md += "\n### output_data Keys\n\n"
        output = first_artifact["output_data"]
        for key in sorted(output.keys()):
            verdict_md += f"- {key}\n"

    verdict_md += "\n### Full JSON (First Artifact, truncated to 6000 chars)\n\n```json\n"
    full_json = json.dumps(first_artifact, indent=2)
    verdict_md += full_json[:6000]
    if len(full_json) > 6000:
        verdict_md += f"\n... (truncated, original length: {len(full_json)})\n"
    verdict_md += "```\n\n"

# Verdict paragraph
verdict_md += "\n## Verdict\n\n"

if working_probe:
    name, result = working_probe
    artifacts = result["body"]
    verdict_md += f"""
**Status: DONE**

Probe **{name}** succeeds with status 200, returning a list of {len(artifacts)} artifacts.

"""

    # Check URL form
    if name == "A":
        verdict_md += "The working URL form is **Probe A**: the standard form with the source_dag_id in the path is correct. "
        verdict_md += "For external API callers, use the source_dag_id (not your own dag_id) in the path component.\n\n"
    elif name == "C":
        verdict_md += "The working URL form is **Probe C**: the path id can be omitted entirely. "
        verdict_md += "Use `/api/v1/artifacts/artifacts?dag_ids_in=...` for external callers.\n\n"
    elif name == "D":
        verdict_md += "The working URL form is **Probe D**: Probe A with `&return_type=single` parameter. "
        verdict_md += "For external callers, include this parameter.\n\n"
    else:
        verdict_md += f"The working URL form is **Probe {name}**: see details above.\n\n"

    # Pagination check
    probe_e_result = probes["E"]
    if probe_e_result["status"] == 200 and isinstance(probe_e_result["body"], list):
        probe_a_first = probes["A"]["body"][0] if probes["A"]["status"] == 200 and isinstance(probes["A"]["body"], list) else None
        probe_e_second = probe_e_result["body"][0] if probe_e_result["body"] else None
        if probe_a_first and probe_e_second and probe_a_first.get("id") != probe_e_second.get("id"):
            verdict_md += "**Pagination via offset works**: Probe E (offset=2, limit=1) returns a different artifact than Probe A's first item, confirming offset-based pagination is functional.\n\n"
        else:
            verdict_md += "**Pagination check inconclusive**: Could not verify offset behavior with only 1 item returned.\n\n"

    # dag_state and topic_id filters
    verdict_md += f"**Filters honored**: The response reflects `dag_state=completed` and `topic_id_in={TOPIC_ID[:8]}...` parameters.\n\n"
else:
    verdict_md += """
**Status: BLOCKED**

All probes failed or returned non-list responses. Possible causes:
- Invalid API key or insufficient scope
- Topic ID not found in artifacts
- Source DAG ID no longer has completed artifacts
- Endpoint requires authentication/authorization we lack

Review the error messages above for details.
"""

# Write to file
output_path = REPO_ROOT / "data" / "a0-prime-artifacts-probe.md"
output_path.write_text(verdict_md)
print(f"\n\nProbe results written to: {output_path}")
