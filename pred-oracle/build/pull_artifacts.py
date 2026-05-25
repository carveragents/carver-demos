#!/usr/bin/env python3
"""
Pull annotated artifacts from Carver DAG Artifacts API for pm_relevant topics.

Writes normalized records to data/_scratch/artifacts.jsonl and a manifest +
summary report alongside it.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

CARVER_API_KEY = os.getenv("CARVER_API_KEY", "")
BASE_URL = "https://app.carveragents.ai"
SOURCE_DAG_ID = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
CREATED_AFTER = "2024-01-01T00:00:00Z"
PAGE_SIZE = 10000
SLEEP_BETWEEN_TOPICS = 0.1
LOG_EVERY_N = 10

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
SCRATCH_DIR = DATA_DIR / "_scratch"

TOPICS_YAML = DATA_DIR / "regulator-topics.yml"
TOPICS_JSON = DATA_DIR / "carver-topics.json"
OUTPUT_JSONL = SCRATCH_DIR / "artifacts.jsonl"
MANIFEST_PATH = SCRATCH_DIR / "a5-prime-manifest.json"
SUMMARY_PATH = SCRATCH_DIR / "a5-prime-summary.md"


# ── Helpers ───────────────────────────────────────────────────────────────────


def load_pm_relevant_topics() -> list[dict]:
    """Return list of pm_relevant topics from regulator-topics.yml."""
    with open(TOPICS_YAML) as f:
        all_topics = yaml.safe_load(f)
    return [t for t in all_topics if t.get("pm_relevant")]


def build_topics_catalog(pm_topics: list[dict]) -> dict[str, dict]:
    """Map topic_id → topic dict (from YAML, enriched with carver-topics.json name)."""
    with open(TOPICS_JSON) as f:
        carver_topics = json.load(f)
    carver_by_id = {t["id"]: t for t in carver_topics}

    catalog: dict[str, dict] = {}
    for t in pm_topics:
        tid = t["topic_id"]
        carver_name = carver_by_id.get(tid, {}).get("name", t.get("name", ""))
        catalog[tid] = {
            "name": carver_name or t.get("name", ""),
            "acronym": t.get("acronym"),
            "jurisdiction_code": t.get("jurisdiction_code"),
            "scope": t.get("scope"),
        }
    return catalog


def normalize(artifact: dict, topic_meta: dict) -> dict:
    """Flatten one artifact dict into the normalized schema."""
    od = artifact.get("output_data") or {}
    cls = od.get("classification") or {}
    md = od.get("metadata") or {}
    inp = artifact.get("input_data") or {}
    em = inp.get("extracted_metadata") or {}

    return {
        # Identifiers
        "artifact_id": artifact.get("id", ""),
        "feed_entry_id": inp.get("feed_entry_id", ""),
        "topic_id": artifact.get("topic_id", ""),
        # Topic catalog join
        "topic_name": topic_meta["name"],
        "topic_acronym": topic_meta.get("acronym"),
        "topic_jurisdiction_code": topic_meta.get("jurisdiction_code"),
        "topic_scope": topic_meta.get("scope"),
        # Title + link from input_data
        "title": em.get("title", ""),
        "link": em.get("url", ""),
        "feed_id": em.get("feed_id", ""),
        "current_published_date": inp.get("current_published_date", ""),
        # Classification
        "update_type": cls.get("update_type", ""),
        "update_subtype": cls.get("update_subtype", ""),
        "jurisdiction_tier": cls.get("jurisdiction_tier", {}),
        "regulator_name": (cls.get("regulatory_source") or {}).get("name", ""),
        "regulator_division": (cls.get("regulatory_source") or {}).get("division_office", ""),
        "regulator_other": (cls.get("regulatory_source") or {}).get("other_agency", []),
        "classification_base_url": (cls.get("metadata") or {}).get("base_url", ""),
        "classification_summary": (cls.get("metadata") or {}).get("summary", ""),
        # Reconciled publication date
        "pub_date": (od.get("reconciled_published_date") or {}).get("date", ""),
        "pub_date_valid": (od.get("reconciled_published_date") or {}).get("valid", False),
        # Metadata (annotation body)
        "critical_dates": md.get("critical_dates", {}),
        "impact_summary": md.get("impact_summary", {}),
        "reg_references": md.get("reg_references", {}),
        "impacted_business": md.get("impacted_business", {}),
        "impacted_functions": md.get("impacted_functions", []),
        "penalties_consequences": md.get("penalties_consequences", []),
        "actionables": md.get("actionables", {}),
        "tags": md.get("tags", []),
        "entities": md.get("entities", []),
        # Scores
        "scores": od.get("scores", {}),
        # Artifact timestamps
        "created_at": artifact.get("created_at", ""),
        "completed_at": artifact.get("completed_at", ""),
    }


def fetch_topic_artifacts(
    client: httpx.Client, topic_id: str
) -> tuple[list[dict], int, float]:
    """
    Fetch all completed artifacts for one topic via pagination.

    Returns (artifacts, page_count, elapsed_seconds).
    """
    url = f"{BASE_URL}/api/v1/artifacts/dags/{SOURCE_DAG_ID}/artifacts"
    headers = {"X-API-Key": CARVER_API_KEY}
    all_artifacts: list[dict] = []
    offset = 0
    pages = 0
    t0 = time.monotonic()

    while True:
        params = {
            "dag_ids_in": SOURCE_DAG_ID,
            "state": "completed",
            "topic_id_in": topic_id,
            "created_after": CREATED_AFTER,
            "limit": PAGE_SIZE,
            "offset": offset,
        }
        resp = client.get(url, params=params, headers=headers, timeout=60.0)
        resp.raise_for_status()
        page: list[dict] = resp.json()
        pages += 1

        if not page:
            break

        all_artifacts.extend(page)

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    elapsed = time.monotonic() - t0
    return all_artifacts, pages, elapsed


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    if not CARVER_API_KEY:
        print("ERROR: CARVER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    pm_topics = load_pm_relevant_topics()
    catalog = build_topics_catalog(pm_topics)
    total_topics = len(pm_topics)

    print(
        f"Loaded {total_topics} pm_relevant topics. Starting artifact pull...",
        file=sys.stderr,
    )

    wall_start = time.monotonic()
    pulled_at = datetime.now(timezone.utc).isoformat()

    topics_succeeded = 0
    topics_failed = 0
    failed_topic_ids: list[str] = []
    total_artifacts = 0

    # Per-topic counts for summary
    topic_counts: dict[str, int] = {}
    update_type_counts: dict[str, int] = {}
    jurisdiction_tier_counts: dict[str, int] = {}
    jurisdiction_code_counts: dict[str, int] = {}

    sample_records: list[dict] = []

    with (
        open(OUTPUT_JSONL, "w") as out_f,
        httpx.Client(timeout=60.0) as client,
    ):
        for idx, topic in enumerate(pm_topics, start=1):
            tid = topic["topic_id"]
            topic_meta = catalog[tid]
            topic_label = topic_meta["acronym"] or topic_meta["name"]

            try:
                artifacts, pages, elapsed = fetch_topic_artifacts(client, tid)

                count = 0
                for artifact in artifacts:
                    # Defensive skip (should not happen with state=completed filter)
                    if artifact.get("state") != "completed":
                        continue
                    if artifact.get("output_data") is None:
                        continue

                    rec = normalize(artifact, topic_meta)
                    out_f.write(json.dumps(rec) + "\n")
                    count += 1

                    # Aggregate for summary
                    ut = rec.get("update_type") or "unknown"
                    update_type_counts[ut] = update_type_counts.get(ut, 0) + 1

                    jt = (rec.get("jurisdiction_tier") or {}).get("label") or "unknown"
                    jurisdiction_tier_counts[jt] = jurisdiction_tier_counts.get(jt, 0) + 1

                    jc = rec.get("topic_jurisdiction_code") or "unknown"
                    jurisdiction_code_counts[jc] = jurisdiction_code_counts.get(jc, 0) + 1

                    if len(sample_records) < 3:
                        sample_records.append(rec)

                topic_counts[tid] = count
                total_artifacts += count
                topics_succeeded += 1

                if idx % LOG_EVERY_N == 0 or idx == total_topics:
                    print(
                        f"Topic {idx}/{total_topics}: {topic_label} → "
                        f"{count} artifacts ({elapsed:.1f}s, {pages} pages)",
                        file=sys.stderr,
                    )

            except Exception as exc:
                topics_failed += 1
                failed_topic_ids.append(tid)
                print(
                    f"ERROR Topic {idx}/{total_topics} [{topic_label}]: {exc}",
                    file=sys.stderr,
                )

            time.sleep(SLEEP_BETWEEN_TOPICS)

    wall_time = time.monotonic() - wall_start

    # ── Manifest ─────────────────────────────────────────────────────────────

    manifest = {
        "pulled_at": pulled_at,
        "endpoint": f"/api/v1/artifacts/dags/{SOURCE_DAG_ID}/artifacts",
        "state_filter": "completed",
        "topics_attempted": total_topics,
        "topics_succeeded": topics_succeeded,
        "topics_failed": topics_failed,
        "total_artifacts": total_artifacts,
        "wall_time_seconds": round(wall_time, 1),
        "failed_topic_ids": failed_topic_ids,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest written: {MANIFEST_PATH}", file=sys.stderr)

    # ── Summary report ────────────────────────────────────────────────────────

    top10_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top15_update = sorted(update_type_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    top_tiers = sorted(jurisdiction_tier_counts.items(), key=lambda x: x[1], reverse=True)
    top20_jc = sorted(jurisdiction_code_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    lines: list[str] = [
        "# A5' — Artifacts Pull Summary",
        "",
        f"**Pulled at:** {pulled_at}",
        f"**Total artifacts:** {total_artifacts:,}",
        f"**Topics attempted:** {total_topics}",
        f"**Topics succeeded:** {topics_succeeded}",
        f"**Topics failed:** {topics_failed}",
        f"**Wall time:** {wall_time:.1f}s",
        "",
        "---",
        "",
        "## Top 10 Topics by Artifact Count",
        "",
        "| # | Topic ID | Name | Artifacts |",
        "|---|----------|------|-----------|",
    ]
    for rank, (tid, cnt) in enumerate(top10_topics, 1):
        name = catalog.get(tid, {}).get("name", tid[:8])
        lines.append(f"| {rank} | {tid[:8]}... | {name} | {cnt:,} |")

    lines += [
        "",
        "## Breakdown by update_type (top 15)",
        "",
        "| update_type | count |",
        "|-------------|-------|",
    ]
    for ut, cnt in top15_update:
        lines.append(f"| {ut} | {cnt:,} |")

    lines += [
        "",
        "## Breakdown by jurisdiction_tier.label",
        "",
        "| tier | count |",
        "|------|-------|",
    ]
    for tier, cnt in top_tiers:
        lines.append(f"| {tier} | {cnt:,} |")

    lines += [
        "",
        "## Breakdown by topic_jurisdiction_code (top 20)",
        "",
        "| jurisdiction_code | count |",
        "|-------------------|-------|",
    ]
    for jc, cnt in top20_jc:
        lines.append(f"| {jc} | {cnt:,} |")

    lines += ["", "## Sample Records (3)", ""]
    for i, rec in enumerate(sample_records, 1):
        raw = json.dumps(rec, indent=2, default=str)
        truncated = raw[:1500] + ("\n... (truncated)" if len(raw) > 1500 else "")
        lines += [f"### Record {i}", "", "```json", truncated, "```", ""]

    SUMMARY_PATH.write_text("\n".join(lines))
    print(f"Summary written: {SUMMARY_PATH}", file=sys.stderr)

    # Print manifest to stdout for the caller
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
