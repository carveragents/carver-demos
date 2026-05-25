"""A5 — Pull full annotation corpus for PM-relevant topics.

Strategy: loop one topic at a time, calling:
  1. client.get_annotations(topic_ids=[topic_id])  → annotation rows
  2. qe.chain().filter_by_topic(topic_id=...).filter_by_date(...).to_dataframe()
     → entries sidecar (for entry_link)

Output: data/_scratch/annotations.jsonl  (one record per line)
        data/_scratch/a5-manifest.json
        data/_scratch/a5-summary.md

Usage:
    uv run python build/pull_annotations.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
SCRATCH_DIR = DATA_DIR / "_scratch"
ANNOTATIONS_OUT = SCRATCH_DIR / "annotations.jsonl"
MANIFEST_OUT = SCRATCH_DIR / "a5-manifest.json"
SUMMARY_OUT = SCRATCH_DIR / "a5-summary.md"

DATE_START = datetime(2024, 1, 1)
DATE_END = datetime.now()

SLEEP_BETWEEN_TOPICS = 0.1
PROGRESS_EVERY = 10


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------


def load_pm_topics(data_dir: Path) -> list[dict[str, Any]]:
    """Load regulator-topics.yml and return only pm_relevant=True entries."""
    raw = yaml.safe_load((data_dir / "regulator-topics.yml").read_text())
    return [t for t in raw if t.get("pm_relevant") is True]


def build_topics_catalog(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Build a dict keyed on topic_id from carver-topics.json for join lookups."""
    raw = json.loads((data_dir / "carver-topics.json").read_text())
    return {t["id"]: t for t in raw}


# ---------------------------------------------------------------------------
# Per-topic entries sidecar lookup
# ---------------------------------------------------------------------------


def fetch_entries_lookup(
    qe: Any, topic_id: str
) -> dict[str, str]:
    """Return {entry_id: entry_link} for a topic, handling TypeError fallback."""
    try:
        df = (
            qe.chain()
            .filter_by_topic(topic_id=topic_id)
            .filter_by_date(start_date=DATE_START, end_date=DATE_END)
            .to_dataframe()
        )
    except TypeError:
        # Date filter unsupported for this topic; pull unfiltered, filter client-side
        df = qe.chain().filter_by_topic(topic_id=topic_id).to_dataframe()
        if "entry_published_at" in df.columns:
            df = df[
                (df["entry_published_at"] >= DATE_START.isoformat())
                & (df["entry_published_at"] <= DATE_END.isoformat())
            ]
        elif "published_date" in df.columns:
            df = df[
                (df["published_date"] >= DATE_START.isoformat())
                & (df["published_date"] <= DATE_END.isoformat())
            ]

    if df.empty:
        return {}

    # entry_id column may be 'entry_id' or 'id'
    id_col = "entry_id" if "entry_id" in df.columns else "id"
    # link column may be 'entry_link' or 'link'
    link_col = "entry_link" if "entry_link" in df.columns else "link"

    result: dict[str, str] = {}
    for _, row in df.iterrows():
        eid = str(row.get(id_col, "") or "")
        link = str(row.get(link_col, "") or "")
        if eid:
            result[eid] = link
    return result


# ---------------------------------------------------------------------------
# Normalize one annotation row
# ---------------------------------------------------------------------------


def normalize_record(
    row: dict[str, Any],
    topics_catalog: dict[str, dict[str, Any]],
    pm_topic: dict[str, Any],
    entries_lookup: dict[str, str],
) -> dict[str, Any]:
    """Build a normalized flat record from one annotation row."""
    feed_entry_id: str = row.get("feed_entry_id", "")
    topic_id: str = row.get("topic_id", "")
    ann: dict[str, Any] = row.get("annotation") or {}

    classification: dict[str, Any] = ann.get("classification") or {}
    cls_metadata: dict[str, Any] = classification.get("metadata") or {}
    reg_source: dict[str, Any] = classification.get("regulatory_source") or {}
    metadata: dict[str, Any] = ann.get("metadata") or {}
    rec_pub: dict[str, Any] = ann.get("reconciled_published_date") or {}

    catalog_entry = topics_catalog.get(topic_id) or {}

    return {
        "feed_entry_id": feed_entry_id,
        "topic_id": topic_id,
        # Joins from topics catalog
        "topic_name": catalog_entry.get("name") or pm_topic.get("name", ""),
        "topic_acronym": catalog_entry.get("acronym") or pm_topic.get("acronym"),
        "topic_jurisdiction_code": pm_topic.get("jurisdiction_code"),
        "topic_scope": pm_topic.get("scope"),
        # From annotation.classification.metadata
        "title": cls_metadata.get("title", ""),
        "base_url": cls_metadata.get("base_url", ""),
        # From entries sidecar
        "link": entries_lookup.get(feed_entry_id, ""),
        # From annotation.classification.regulatory_source
        "regulator_name": reg_source.get("name", ""),
        "regulator_division": reg_source.get("division_office", ""),
        "regulator_other": reg_source.get("other_agency", []),
        # From annotation.classification
        "update_type": classification.get("update_type", ""),
        "update_subtype": classification.get("update_subtype", ""),
        "jurisdiction_tier": classification.get("jurisdiction_tier") or {},
        # Canonical publication date
        "pub_date": rec_pub.get("date", ""),
        "pub_date_valid": rec_pub.get("valid", False),
        # annotation.metadata sub-objects
        "critical_dates": metadata.get("critical_dates") or {},
        "impact_summary": metadata.get("impact_summary") or {},
        "reg_references": metadata.get("reg_references") or {},
        "impacted_business": metadata.get("impacted_business") or {},
        "impacted_functions": metadata.get("impacted_functions") or [],
        "penalties_consequences": metadata.get("penalties_consequences") or [],
        "actionables": metadata.get("actionables") or {},
        "tags": metadata.get("tags") or [],
        "entities": metadata.get("entities") or [],
        # Scores — preserve nested shape
        "scores": ann.get("scores") or {},
    }


# ---------------------------------------------------------------------------
# Main pull loop
# ---------------------------------------------------------------------------


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    if not os.environ.get("CARVER_API_KEY"):
        print("ERROR: CARVER_API_KEY not set.", file=sys.stderr)
        return 1

    from carver_feeds import create_query_engine, get_client

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    pm_topics = load_pm_topics(DATA_DIR)
    topics_catalog = build_topics_catalog(DATA_DIR)

    print(f"Loaded {len(pm_topics)} PM-relevant topics", file=sys.stderr)

    client = get_client()
    qe = create_query_engine()

    total_topics = len(pm_topics)
    topics_attempted = 0
    topics_succeeded = 0
    topics_failed = 0
    total_annotations = 0
    failed_topic_ids: list[dict[str, str]] = []

    pull_start = time.time()

    # Open JSONL output (truncate at start)
    with ANNOTATIONS_OUT.open("w") as out_f:
        for idx, pm_topic in enumerate(pm_topics, start=1):
            topic_id: str = pm_topic["topic_id"]
            topic_name: str = pm_topic.get("name", "")
            topics_attempted += 1

            topic_start = time.time()
            try:
                # Step 1: fetch annotations for this topic
                ann_rows = client.get_annotations(topic_ids=[topic_id])
                ann_rows = ann_rows or []

                # Step 2: entries sidecar for entry_link
                try:
                    entries_lookup = fetch_entries_lookup(qe, topic_id)
                except Exception as e:
                    print(
                        f"WARN topic {topic_id} ({topic_name}): entries sidecar failed: {e}",
                        file=sys.stderr,
                    )
                    entries_lookup = {}

                # Step 3: normalize and write
                topic_count = 0
                for row in ann_rows:
                    record = normalize_record(row, topics_catalog, pm_topic, entries_lookup)
                    out_f.write(json.dumps(record, default=str) + "\n")
                    topic_count += 1

                total_annotations += topic_count
                topics_succeeded += 1

                elapsed = time.time() - topic_start
                if idx % PROGRESS_EVERY == 0 or idx == total_topics:
                    print(
                        f"Topic {idx}/{total_topics}: {topic_name} → {topic_count} annotations ({elapsed:.1f}s)",
                        file=sys.stderr,
                    )

            except Exception as e:
                topics_failed += 1
                reason = str(e)
                failed_topic_ids.append({"topic_id": topic_id, "name": topic_name, "reason": reason})
                print(
                    f"ERROR topic {topic_id} ({topic_name}): {reason}",
                    file=sys.stderr,
                )

            time.sleep(SLEEP_BETWEEN_TOPICS)

    wall_time = time.time() - pull_start

    # Write manifest
    manifest = {
        "pulled_at": datetime.now().isoformat(),
        "topics_attempted": topics_attempted,
        "topics_succeeded": topics_succeeded,
        "topics_failed": topics_failed,
        "total_annotations": total_annotations,
        "wall_time_seconds": round(wall_time, 1),
        "failed_topic_ids": failed_topic_ids,
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest written to {MANIFEST_OUT}", file=sys.stderr)

    # Build summary
    build_summary(ANNOTATIONS_OUT, MANIFEST_OUT, SUMMARY_OUT, manifest)
    print(f"Summary written to {SUMMARY_OUT}", file=sys.stderr)

    print(
        f"\nDONE: {total_annotations} annotations from {topics_succeeded}/{topics_attempted} topics "
        f"in {wall_time:.0f}s",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


def build_summary(
    jsonl_path: Path,
    manifest_path: Path,
    summary_path: Path,
    manifest: dict[str, Any],
) -> None:
    """Read JSONL, compute breakdowns, write a5-summary.md."""
    from collections import Counter

    annotations: list[dict[str, Any]] = []
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                annotations.append(json.loads(line))

    if not annotations:
        summary_path.write_text("# A5 Summary\n\nNo annotations pulled.\n")
        return

    topic_counts: Counter = Counter()
    update_type_counts: Counter = Counter()
    jt_label_counts: Counter = Counter()
    jcode_counts: Counter = Counter()

    for rec in annotations:
        topic_counts[rec.get("topic_name", "")] += 1
        update_type_counts[rec.get("update_type", "(empty)") or "(empty)"] += 1

        jt = rec.get("jurisdiction_tier") or {}
        label = jt.get("label", "(empty)") if isinstance(jt, dict) else "(empty)"
        jt_label_counts[label or "(empty)"] += 1

        jcode = rec.get("topic_jurisdiction_code") or "(empty)"
        jcode_counts[jcode] += 1

    # Top 10 topics
    top_topics = topic_counts.most_common(10)
    # Top 15 update_types
    top_update = update_type_counts.most_common(15)
    # All jurisdiction tier labels
    all_jt = sorted(jt_label_counts.items(), key=lambda x: -x[1])
    # Top 20 jurisdiction codes
    top_jcodes = jcode_counts.most_common(20)

    # Sample 5 records
    sample_recs = annotations[:5]

    lines = [
        "# A5 — Full Annotation Pull Summary",
        "",
        f"**Pulled at:** {manifest['pulled_at']}",
        f"**Total annotations:** {manifest['total_annotations']}",
        f"**Topics attempted:** {manifest['topics_attempted']}",
        f"**Topics succeeded:** {manifest['topics_succeeded']}",
        f"**Topics failed:** {manifest['topics_failed']}",
        f"**Wall time:** {manifest['wall_time_seconds']}s",
        "",
        "---",
        "",
        "## Top 10 Topics by Annotation Count",
        "",
        "| Topic | Count |",
        "|-------|-------|",
    ]
    for name, cnt in top_topics:
        lines.append(f"| {name} | {cnt} |")

    lines += [
        "",
        "---",
        "",
        "## Breakdown by update_type (top 15)",
        "",
        "| update_type | Count |",
        "|-------------|-------|",
    ]
    for utype, cnt in top_update:
        lines.append(f"| {utype} | {cnt} |")

    lines += [
        "",
        "---",
        "",
        "## Breakdown by jurisdiction_tier.label",
        "",
        "| label | Count |",
        "|-------|-------|",
    ]
    for label, cnt in all_jt:
        lines.append(f"| {label} | {cnt} |")

    lines += [
        "",
        "---",
        "",
        "## Breakdown by topic_jurisdiction_code (top 20)",
        "",
        "| jurisdiction_code | Count |",
        "|-------------------|-------|",
    ]
    for jcode, cnt in top_jcodes:
        lines.append(f"| {jcode} | {cnt} |")

    lines += [
        "",
        "---",
        "",
        "## Sample 5 Normalized Records",
        "",
    ]
    for i, rec in enumerate(sample_recs, 1):
        lines.append(f"### Record {i}")
        lines.append("```json")
        lines.append(json.dumps(rec, indent=2, default=str))
        lines.append("```")
        lines.append("")

    summary_path.write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
