"""Pull prediction-market-relevant regulatory events from Carver Feeds SDK.

Two-endpoint pattern (DP1 case A-two-endpoint):
  1. QueryEngine.filter_by_topic(...).to_dataframe()  → entries (no annotation fields)
  2. CarverFeedsAPIClient.get_annotations(feed_entry_ids=[...])
     → annotations keyed by feed_entry_id
  3. Join on feed_entry_id, normalize, filter for PM relevance, write outputs.

Usage:
    uv run python build/pull_carver.py

Environment variables (all optional except CARVER_API_KEY):
    CARVER_API_KEY          Required. Carver Feeds API key.
    PRED_ORACLE_PULL_FROM   ISO date string; default "2024-01-01".
    PRED_ORACLE_PULL_TO     ISO date string; default today.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PM_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        "Event Contracts",
        "Sports Betting",
        "Derivatives Exchanges",
        "Prediction Markets",
        "Sweepstakes",
        "Online Gambling",
        "Commodity Exchanges",
        "Cryptocurrency Exchanges",
    }
)

ANNOTATION_BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Pure-function helpers (tested without SDK)
# ---------------------------------------------------------------------------


def load_filter_inputs(data_dir: Path) -> tuple[set[str], set[str]]:
    """Load regulator allowlist and platform-entity allowlist from YAML seed files.

    Returns:
        (regulators, entities) where each is a set of canonical names and aliases.
    """
    regulators: set[str] = set()
    raw_regs = yaml.safe_load((data_dir / "known_regulators.yml").read_text())
    for entry in raw_regs:
        regulators.add(entry["canonical_name"])
        for alias in entry.get("aliases", []):
            regulators.add(alias)

    entities: set[str] = set()
    platforms_dir = data_dir / "platforms"
    for entities_file in platforms_dir.glob("*/entities.yml"):
        raw_entities = yaml.safe_load(entities_file.read_text())
        for entry in raw_entities:
            entities.add(entry["canonical_name"])
            for alias in entry.get("aliases", []):
                entities.add(alias)

    return regulators, entities


def is_prediction_market_relevant(
    event: dict[str, Any],
    regulators: set[str],
    entities: set[str],
) -> bool:
    """Return True if the event is relevant to prediction-market operators.

    Three OR clauses:
      A: any business type in PM_BUSINESS_TYPES
      B: regulatory_source.name is in the regulator allowlist
      C: any entity in the event entities list matches platform entities
    """
    # Clause A: business type intersection
    business_types: list[str] = event.get("impacted_business", {}).get("type") or []
    if set(business_types) & PM_BUSINESS_TYPES:
        return True

    # Clause B: regulator allowlist
    reg_name: str = event.get("regulatory_source", {}).get("name") or ""
    if reg_name in regulators:
        return True

    # Clause C: platform entity mention
    event_entities: list[str] = event.get("entities") or []
    if set(event_entities) & entities:
        return True

    return False


def normalize_event(entry: dict[str, Any], annotation_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge an entry row and annotation payload into one flat record.

    Maps annotation sub-objects (classification, metadata, scores, summary) to
    top-level keys that is_prediction_market_relevant expects.

    Args:
        entry: Row dict from QueryEngine.to_dataframe() (entry surface).
        annotation_payload: The `annotation` dict from get_annotations()
                            (may be empty {} when annotation is absent).

    Returns:
        Flat dict with both entry fields and normalized annotation fields.
    """
    classification: dict[str, Any] = annotation_payload.get("classification") or {}
    metadata: dict[str, Any] = annotation_payload.get("metadata") or {}
    scores: dict[str, Any] = annotation_payload.get("scores") or {}
    summary: str = annotation_payload.get("summary") or ""

    # Derive canonical entry_id and title regardless of key variant
    entry_id = entry.get("entry_id") or entry.get("id") or ""
    title = entry.get("entry_title") or entry.get("title") or ""

    return {
        # Entry-surface fields
        "entry_id": entry_id,
        "title": title,
        "entry_link": entry.get("entry_link") or entry.get("link") or "",
        "published_at": str(entry.get("published_at") or ""),
        "feed_id": entry.get("feed_id") or "",
        "topic_id": entry.get("topic_id") or "",
        "description": entry.get("description") or "",
        # Annotation-surface fields (Appendix-A shape)
        "update_type": classification.get("update_type") or "",
        "regulatory_source": metadata.get("regulatory_source") or {},
        "impacted_business": metadata.get("impacted_business") or {},
        "critical_dates": metadata.get("critical_dates") or {},
        "impact_summary": metadata.get("impact_summary") or {},
        "entities": metadata.get("entities") or [],
        "scores": scores,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Two-endpoint pull
# ---------------------------------------------------------------------------


def _is_pm_relevant_topic(topic_name: str, regulators: set[str], entities: set[str]) -> bool:
    """Pre-filter: topic name contains a known regulator, entity, or PM business type."""
    all_known = regulators | entities | PM_BUSINESS_TYPES
    topic_lower = topic_name.lower()
    return any(k.lower() in topic_lower for k in all_known if k)


def pull_carver_events(
    date_from: str,
    date_to: str,
    limit: int = 10000,
    regulators: set[str] | None = None,
    entities: set[str] | None = None,
) -> tuple[list[dict[str, Any]], int, int, int]:
    """Pull entries + annotations from Carver SDK and join on feed_entry_id.

    Pre-filters topics to PM-relevant ones (by matching against the regulator/entity
    allowlists) before pulling entries, so the raw entry limit is not wasted on
    irrelevant topics.

    Returns:
        (normalized_events, topics_scanned, annotated_count, topics_date_filter_noops)
    """
    from carver_feeds import create_data_manager, create_query_engine, get_client

    dm = create_data_manager()
    client = get_client()

    # 1. Discover available topics and pre-filter to PM-relevant ones
    topics_df = dm.get_topics_df()
    all_topic_names: list[str] = topics_df["name"].dropna().unique().tolist()

    if regulators is not None and entities is not None:
        topic_names = [t for t in all_topic_names if _is_pm_relevant_topic(t, regulators, entities)]
        print(
            f"Topic pre-filter: {len(topic_names)}/{len(all_topic_names)} topics matched",
            file=sys.stderr,
        )
    else:
        topic_names = all_topic_names

    # 2. Pull entries per topic within the date range
    start_dt = datetime.fromisoformat(date_from)
    end_dt = datetime.fromisoformat(date_to)

    all_entries: list[dict[str, Any]] = []
    topics_scanned = 0
    topics_date_filter_noops = 0

    qe = create_query_engine()
    for topic in topic_names:
        try:
            topic_df = (
                qe.chain()
                .filter_by_topic(topic_name=topic)
                .filter_by_date(start_date=start_dt, end_date=end_dt)
                .to_dataframe()
            )
        except TypeError as e:
            # SDK doesn't support filter_by_date for this topic.
            # Fall back to unfiltered pull; apply client-side date filter below.
            print(
                f"WARN: topic '{topic}' date filter unsupported ({e}); pulling unfiltered",
                file=sys.stderr,
            )
            topics_date_filter_noops += 1
            try:
                topic_df = qe.chain().filter_by_topic(topic_name=topic).to_dataframe()
            except Exception as e2:
                print(f"WARN: topic '{topic}' pull failed entirely: {e2}", file=sys.stderr)
                continue
            # Client-side date filter
            if "published_at" in topic_df.columns:
                topic_df = topic_df[
                    (topic_df["published_at"] >= date_from) & (topic_df["published_at"] <= date_to)
                ]
        except Exception as e:
            print(f"WARN: topic '{topic}' pull failed: {e}", file=sys.stderr)
            continue

        topics_scanned += 1
        if topic_df.empty:
            continue

        all_entries.extend(topic_df.to_dict(orient="records"))
        if len(all_entries) >= limit:
            break

    all_entries = all_entries[:limit]

    # 3. Collect entry IDs and fetch annotations in batches of ANNOTATION_BATCH_SIZE
    entry_ids: list[str] = [str(e.get("entry_id") or e.get("id") or "") for e in all_entries]
    entry_ids = [eid for eid in entry_ids if eid]

    annotation_by_id: dict[str, dict[str, Any]] = {}
    for i in range(0, len(entry_ids), ANNOTATION_BATCH_SIZE):
        batch = entry_ids[i : i + ANNOTATION_BATCH_SIZE]
        try:
            anns = client.get_annotations(feed_entry_ids=batch)
        except Exception as e:
            print(
                f"WARN: get_annotations failed for batch starting at {i}: {e}",
                file=sys.stderr,
            )
            continue
        for ann in anns or []:
            fid = ann.get("feed_entry_id")
            if fid:
                annotation_by_id[fid] = ann.get("annotation") or {}

    annotated_count = len(annotation_by_id)

    # 4. Join + normalize (soft-fail for missing annotations)
    normalized: list[dict[str, Any]] = []
    for entry in all_entries:
        eid = str(entry.get("entry_id") or entry.get("id") or "")
        ann_payload = annotation_by_id.get(eid, {})
        normalized.append(normalize_event(entry, ann_payload))

    return normalized, topics_scanned, annotated_count, topics_date_filter_noops


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    from dotenv import load_dotenv

    root = Path(__file__).parent.parent
    load_dotenv(root / ".env")

    if not os.environ.get("CARVER_API_KEY"):
        print(
            "ERROR: CARVER_API_KEY not set. Add it to .env or export it.",
            file=sys.stderr,
        )
        return 1

    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load filter inputs from YAML seed catalogs
    regulators, entities = load_filter_inputs(data_dir)

    # Date range from env (default: 2024-01-01 → today)
    date_from = os.environ.get("PRED_ORACLE_PULL_FROM", "2024-01-01")
    date_to = os.environ.get("PRED_ORACLE_PULL_TO", datetime.now().date().isoformat())

    print(f"Pulling Carver entries from {date_from} to {date_to} …", file=sys.stderr)

    all_events, topics_scanned, annotated_count, topics_date_filter_noops = pull_carver_events(
        date_from, date_to, regulators=regulators, entities=entities
    )

    raw_count = len(all_events)

    # Filter for PM relevance
    kept: list[dict[str, Any]] = [
        e for e in all_events if is_prediction_market_relevant(e, regulators, entities)
    ]
    kept_count = len(kept)

    # Resolve carver_feeds SDK version
    try:
        import carver_feeds

        sdk_version = getattr(carver_feeds, "__version__", "unknown")
    except Exception:
        sdk_version = "unknown"

    # Write outputs
    events_path = data_dir / "carver-events.json"
    manifest_path = data_dir / "carver-pull-manifest.json"

    events_path.write_text(json.dumps(kept, indent=2, default=str))

    manifest: dict[str, Any] = {
        "pulled_at": datetime.now().isoformat(),
        "carver_sdk_version": sdk_version,
        "date_from": date_from,
        "date_to": date_to,
        "topics_scanned": topics_scanned,
        "topics_date_filter_noops": topics_date_filter_noops,
        "raw_count_before_filter": raw_count,
        "annotated_entry_count": annotated_count,
        "kept_count": kept_count,
        "dp1_case": "A-two-endpoint",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(
        f"Wrote {kept_count} events to data/carver-events.json"
        f" (raw={raw_count}, annotated={annotated_count}, topics={topics_scanned})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
