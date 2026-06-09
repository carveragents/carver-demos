# Accessing the Annotation Dataset

**Decision for this showcase: we use the direct Carver Artifacts API only** — raw
HTTP against the artifacts endpoint, authenticated with an `X-API-Key` header. The
`carver-feeds-sdk` is **not** used in the data pipeline (it can't reach this endpoint
and its `get_annotations` route doesn't paginate — see [Why this route](#why-this-route)).

## Prerequisites

- Python **3.10–3.12** (this repo ships a `.venv` on 3.10).
- A Carver API key (`CARVER_API_KEY`). Get one at <https://app.carveragents.ai>.

## Setup

```bash
# from this repo root — no SDK needed for the pipeline
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install httpx python-dotenv pandas

# .env in the repo root (CWD) — git-ignored, never commit the key
cat > .env <<'EOF'
CARVER_API_KEY=your_api_key_here
CARVER_BASE_URL=https://app.carveragents.ai
EOF
```

## The endpoint

```
GET {base}/api/v1/artifacts/dags/{dag_id}/artifacts
      ?state=completed
      &dry_run=true                 # required flag on the listing GET
      &artifact_type_id=annotations-v1
      &limit={limit}                # honored; keep ≤ 10000 (larger pages 502)
      &offset={offset}
      [&topic_ids_in=<uuid,uuid>]   # optional filter
Header: X-API-Key: {CARVER_API_KEY}
```

- **Annotations DAG (production):** `7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad`
- Returns a JSON **list** of artifact envelopes (see [shape](#artifact-shape)).

## The paginated pull (canonical loop)

This endpoint honors real `limit`/`offset`, so we page by offset until a short/empty
page. Pull once to a local `.jsonl`; present from the file.

```python
import json, os, time
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))  # explicit path (see LESSONS)

BASE  = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai")
KEY   = os.environ["CARVER_API_KEY"]
DAG   = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
CHUNK = 10_000          # max before the listing GET 502s
HEADERS = {"X-API-Key": KEY}

def pull(out_path="data/annotations.jsonl", start_offset=0):
    offset = start_offset
    total = 0
    with httpx.Client(timeout=180) as client, open(out_path, "a") as fh:
        while True:
            url = (f"{BASE}/api/v1/artifacts/dags/{DAG}/artifacts"
                   f"?state=completed&dry_run=true&artifact_type_id=annotations-v1"
                   f"&limit={CHUNK}&offset={offset}")
            rows = client.get(url, headers=HEADERS).raise_for_status().json()
            if not rows:                       # empty page → done
                break
            for art in rows:
                fh.write(json.dumps(art) + "\n")
            total += len(rows)
            print(f"offset={offset} fetched={len(rows)} total={total}")
            if len(rows) < CHUNK:              # short page → last page
                break
            offset += CHUNK
            time.sleep(0.2)
    return total
```

Resumability: the GET is read-only and offset-addressable, so a failed run resumes
from the last good `offset`. (The `run_backfill.sh` reference below does exactly this.)

## Artifact shape

Each list item is an **artifact envelope**. The annotation object lives in
**`output_data`** — and it is byte-for-byte the same shape as the feeds-view
`annotation` (`scores`, `entry_id`, `metadata`, `classification`,
`reconciled_published_date`); see [data-model.md](data-model.md).

```jsonc
{
  "id": "…", "artifact_id": "…",
  "dag_id": "…", "artifact_type_id": "annotations-v1",
  "topic_id": "…",                 // ← topic is on the envelope; no catalog join needed
  "state": "completed",
  "source_kind": "…", "source_table": "…", "source_id": "…",
  "input_data":  { "id": "<entry_id>", "feed_entry_id": "…", "source_id": "…",
                   "extracted_metadata": {…}, "current_published_date": "…" },
  "output_data": { /* ←★ THE ANNOTATION: scores, entry_id, metadata,
                        classification, reconciled_published_date */ },
  "execution_id": "…", "execution_metadata": {…},
  "error_message": null, "retry_count": 0, "max_retries": …,
  "created_at": "…", "sent_at": "…", "completed_at": "…", "updated_at": "…"
}
```

Ingest rule: treat **`artifact.output_data`** as the annotation; carry
`artifact.topic_id`, `state`, and the `*_at` timestamps from the envelope; use
`input_data.id` / `input_data.feed_entry_id` as join keys.

## Catalog (only if needed)

`topic_id` is already on every envelope, so most aggregations need no catalog join.
If you want topic **names/jurisdictions**, fetch the catalog with a direct GET too —
no SDK:

```
GET {base}/api/v1/feeds/topics?details=true     Header: X-API-Key: {KEY}
GET {base}/api/v1/feeds/categories              Header: X-API-Key: {KEY}
```

## Why this route

| | Feeds view (`/core/annotations`) | **Artifacts view (this showcase)** |
|---|---|---|
| Pagination | ❌ ignores `limit`/`offset` (verified, no headers) | ✅ real `limit`+`offset` (chunk ≤ 10k) |
| Full 200k+ corpus | only by looping every topic | ✅ one offset walk |
| In SDK | ✅ `get_annotations` | ❌ raw HTTP only |
| Annotation shape | `{annotation:{…}}` | `{…, output_data:{…}}` (same inner object) |
| Envelope extras | — | `topic_id`, `state`, timestamps, retry/exec metadata |

The artifacts route is the only one that paginates and the only one that exposes the
full corpus in a single ordered walk — hence the showcase commits to it exclusively.

## Authoritative references

- Reference pull implementation (offset-chunked, resumable):
  `carver-dags/workflows/jurisdiction_enrichment/steps/fetch_artifacts.py` + `run_backfill.sh`
- Annotations DAG id + `annotations-v1` config:
  `carver-dags/workflows/jurisdiction_enrichment/configs/production/config.completed.json`
- Artifacts-endpoint probes / samples: `carver-demos/pred-oracle/build/probe_artifacts_*.py`
- Annotation payload schema (= `output_data`): [data-model.md](data-model.md)
