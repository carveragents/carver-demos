#!/usr/bin/env python3
"""
Fetch regulatory intelligence entries from Carver Feeds API.

Identifies medical device / regulatory topics and pulls entries published
in the last 30 days. Also fetches AI annotations for scored entries.

Output: public/data/carver_raw.json

Usage:
    python scripts/fetch_feeds.py
    python scripts/fetch_feeds.py --days 60   # extend look-back window
"""

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
def load_env(path: str = ".env") -> None:
    """Minimal .env loader (no dependency on python-dotenv)."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        # Strip inline comments and surrounding quotes
        val = val.split("#")[0].strip().strip("'\"")
        os.environ.setdefault(key.strip(), val)


load_env()

BASE_URL = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai").rstrip("/")
API_KEY  = os.environ.get("CARVER_API_KEY", "")
USER_ID  = os.environ.get("CARVER_USER_ID", "")

if not API_KEY:
    log.error("CARVER_API_KEY not set — add it to .env")
    sys.exit(1)

# ── Topic matching ─────────────────────────────────────────────────────────────
# Keywords that identify medical device / health-product regulatory bodies.
# Ordered roughly by priority for logging clarity.
MEDDEV_KEYWORDS = [
    # Primary regulators for CardioWatch X1 markets
    "food and drug administration", "fda", "cdrh",
    "medicines and healthcare products", "mhra",
    "therapeutic goods administration", "tga",
    "swissmedic",
    "central drugs standard control", "cdsco",
    # EU
    "european medicines agency", "ema",
    "mdcg", "eu mdr", "ivdr", "eudamed",
    "notified body",
    # Major national competent authorities (EU MDR relevant)
    "agence nationale de sécurité du médicament", "ansm",
    "agencia española de medicamentos", "aemps",
    "paul-ehrlich-institut",
    "bundesinstitut für arzneimittel", "bfarm",
    "agenzia italiana del farmaco", "aifa",
    "lareb", "rivm",
    # Broader health-product safety
    "health canada",
    "medical device", "medtech",
    "pharmacovigilance", "vigilance",
]

# Which jurisdictions to tag per topic (keyword → list of markets)
JURISDICTION_MAP: dict[str, list[str]] = {
    "food and drug administration": ["US"],
    "fda": ["US"],
    "cdrh": ["US"],
    "mhra": ["UK"],
    "medicines and healthcare": ["UK"],
    "therapeutic goods": ["AU"],
    "tga": ["AU"],
    "swissmedic": ["CH"],
    "cdsco": ["IN"],
    "central drugs standard": ["IN"],
    "european medicines agency": ["EU"],
    "ema": ["EU"],
    "mdcg": ["EU"],
    "eu mdr": ["EU"],
    "ivdr": ["EU"],
    "eudamed": ["EU"],
    "notified body": ["EU"],
    "ansm": ["EU", "FR"],
    "aemps": ["EU", "ES"],
    "paul-ehrlich": ["EU", "DE"],
    "bfarm": ["EU", "DE"],
    "aifa": ["EU", "IT"],
    "health canada": ["CA"],
}

# ── HTTP helpers ───────────────────────────────────────────────────────────────
HEADERS = {
    "X-API-Key": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def api_get(path: str, params: dict | None = None) -> object:
    url = BASE_URL + path
    if params:
        query = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
        url += f"?{query}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        log.error("HTTP %s on %s — %s", e.code, path, body)
        raise
    except urllib.error.URLError as e:
        log.error("Connection error on %s: %s", path, e.reason)
        raise


# ── Topic filtering helpers ────────────────────────────────────────────────────
def _topic_text(topic: dict) -> str:
    return (topic.get("name", "") + " " + (topic.get("description") or "")).lower()


def is_meddev_topic(topic: dict) -> bool:
    text = _topic_text(topic)
    return any(kw in text for kw in MEDDEV_KEYWORDS)


def get_jurisdictions(topic: dict) -> list[str]:
    text = _topic_text(topic)
    seen: set[str] = set()
    result: list[str] = []
    for kw, markets in JURISDICTION_MAP.items():
        if kw in text:
            for m in markets:
                if m not in seen:
                    seen.add(m)
                    result.append(m)
    return result or ["INT"]


# ── Date filtering ─────────────────────────────────────────────────────────────
def parse_iso(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def is_within_window(entry: dict, cutoff: datetime) -> bool:
    for field in ("published_at", "created_at", "updated_at"):
        dt = parse_iso(entry.get(field))
        if dt is not None:
            return dt >= cutoff
    return True  # no date field → include (safe default)


# ── Annotation fetching ────────────────────────────────────────────────────────
def fetch_annotations_for_entries(entry_ids: list[str]) -> dict[str, dict]:
    """
    Fetch AI annotations keyed by feed_entry_id, batching by entry IDs.
    Uses feed_entry_ids_in filter so IDs match the entries we actually have.
    """
    annotations: dict[str, dict] = {}
    BATCH = 50  # API accepts comma-separated UUIDs; 50 keeps URLs manageable
    for i in range(0, len(entry_ids), BATCH):
        batch = entry_ids[i : i + BATCH]
        try:
            results = api_get(
                "/api/v1/core/annotations",
                {"feed_entry_ids_in": ",".join(batch)},
            )
            if isinstance(results, list):
                for item in results:
                    eid = item.get("feed_entry_id")
                    if eid:
                        annotations[eid] = item.get("annotation", {})
        except Exception as exc:
            log.warning("Annotations batch %d/%d failed: %s", i // BATCH + 1, -(-len(entry_ids) // BATCH), exc)
    return annotations


# ── Main ───────────────────────────────────────────────────────────────────────
def main(days: int = 30) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    log.info("Fetching entries published after %s (%d-day window)", cutoff.date(), days)

    # 1. Get all topics
    log.info("Loading topic list …")
    all_topics: list[dict] = api_get("/api/v1/feeds/topics")
    log.info("Total topics available: %d", len(all_topics))

    # 2. Filter to medical device topics
    meddev_topics = [t for t in all_topics if is_meddev_topic(t)]
    log.info("Medical device topics matched: %d", len(meddev_topics))
    for t in meddev_topics:
        log.debug("  ✓ %s", t["name"])

    if not meddev_topics:
        log.error("No medical device topics found — check MEDDEV_KEYWORDS")
        sys.exit(1)

    # 3. Fetch entries per topic, filter by date
    all_entries: list[dict] = []

    for topic in meddev_topics:
        tid = topic["id"]
        try:
            raw = api_get(f"/api/v1/feeds/topics/{tid}/entries", {"limit": 100})
            entries: list[dict] = raw.get("items", raw) if isinstance(raw, dict) else raw
        except Exception as exc:
            log.warning("Skipping topic '%s': %s", topic["name"], exc)
            continue

        recent = [e for e in entries if is_within_window(e, cutoff)]
        if not recent:
            continue

        jurisdictions = get_jurisdictions(topic)
        for entry in recent:
            entry["_topic_id"]       = tid
            entry["_topic_name"]     = topic["name"]
            entry["_jurisdictions"]  = jurisdictions

        log.info("  %-55s  %3d entries (last %dd)", topic["name"][:55], len(recent), days)
        all_entries.extend(recent)

    log.info("Total entries collected: %d", len(all_entries))

    # 4. Fetch AI annotations by entry ID (exact match, no ID mismatch)
    annotations: dict[str, dict] = {}
    all_entry_ids = [e["id"] for e in all_entries if e.get("id")]
    if all_entry_ids:
        log.info("Fetching AI annotations for %d entries …", len(all_entry_ids))
        annotations = fetch_annotations_for_entries(all_entry_ids)
        log.info("Annotations retrieved: %d", len(annotations))

    # Attach annotations to entries
    for entry in all_entries:
        eid = entry.get("id") or entry.get("entry_id") or entry.get("feed_entry_id")
        if eid and eid in annotations:
            entry["_annotation"] = annotations[eid]

    # 5. Write output
    out_path = Path("public/data/carver_raw.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
        "window_days":  days,
        "topic_count":  len(meddev_topics),
        "entry_count":  len(all_entries),
        "entries":      all_entries,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    log.info("Saved → %s  (%d entries)", out_path, len(all_entries))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Carver regulatory feed entries")
    parser.add_argument("--days", type=int, default=30, help="Look-back window in days (default: 30)")
    args = parser.parse_args()
    main(days=args.days)
