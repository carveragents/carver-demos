"""Pull the full monitored-institutions catalog to data/topic_catalog.csv.

Fetches all topics from GET /api/v1/feeds/topics?details=true and assigns the
most-specific category (Medical Devices > Data protection > Finance) by joining
each category's topic membership from GET /api/v1/feeds/categories and
GET /api/v1/feeds/categories/{id}/topics.

Topics absent from all category lists are assigned category = "Uncategorized".

The per-category fetch is validated against the catalog's topic_count and retried
on transient partial responses (same pattern as pull_stratified.py).

An empty topic_ids filter is refused at any point — passing empty IDs to the
artifacts API would pull the entire corpus without filtering.

Output: data/topic_catalog.csv
Columns: topic_id, name, acronym, category, jurisdiction_code,
         jurisdiction_detail, entity_type, govt_body, scope, sectors,
         industries, hq, base_domain

Run: .venv/bin/python tools/pull_topic_catalog.py
"""

import csv
import os
import sys
import time
from collections import Counter

import httpx
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))  # explicit path (see LESSONS)

BASE = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai")
KEY = os.environ["CARVER_API_KEY"]
HEADERS = {"X-API-Key": KEY}

CATEGORY_FETCH_RETRIES = 5

OUT = os.path.join(ROOT, "data", "topic_catalog.csv")

CSV_COLUMNS = [
    "topic_id",
    "name",
    "acronym",
    "category",
    "jurisdiction_code",
    "jurisdiction_detail",
    "entity_type",
    "govt_body",
    "scope",
    "sectors",
    "industries",
    "hq",
    "base_domain",
]

TOPIC_ATTRS = [
    "name",
    "acronym",
    "jurisdiction_code",
    "jurisdiction_detail",
    "entity_type",
    "govt_body",
    "scope",
    "sectors",
    "industries",
    "hq",
    "base_domain",
]


def _fetch_category_topics(client: httpx.Client, cid: str, expected: int) -> list[dict]:
    """GET a category's topics, retrying until count matches `expected`.

    Guards against transient partial/empty API responses that could cause a
    corrupt category map (same pattern as pull_stratified.py::fetch_category_topics).
    """
    for attempt in range(1, CATEGORY_FETCH_RETRIES + 1):
        r = client.get(BASE + f"/api/v1/feeds/categories/{cid}/topics", headers=HEADERS)
        topics = r.json() if r.status_code == 200 else []
        if isinstance(topics, list) and len(topics) == expected:
            return topics
        print(
            f"  [retry {attempt}] category {cid}: got "
            f"{len(topics) if isinstance(topics, list) else 'ERR'} "
            f"!= expected {expected}; backing off",
            flush=True,
        )
        time.sleep(1.5 * attempt)
    raise RuntimeError(
        f"category {cid}: could not fetch {expected} topics after "
        f"{CATEGORY_FETCH_RETRIES} retries — aborting (refusing a partial map)"
    )


def fetch_catalog(client: httpx.Client) -> tuple[dict[str, str], dict[str, dict]]:
    """Build topic → most-specific-category map and topic → attribute metadata map.

    Fetches all topics from /feeds/topics?details=true for the full institution
    universe, then iterates categories sorted smallest-first so that setdefault
    assigns the most-specific category (MD > DP > Finance) to multi-category topics.

    Returns:
        topic_cat: dict[topic_id -> category_name]
        topic_meta: dict[topic_id -> {name, acronym, jurisdiction_code, …}]
    """
    # 1. Fetch all topics (the full universe, with details)
    r = client.get(BASE + "/api/v1/feeds/topics", params={"details": "true"}, headers=HEADERS)
    r.raise_for_status()
    all_topics: list[dict] = r.json()
    print(f"  /feeds/topics: {len(all_topics)} institutions", flush=True)

    # Build meta from the full /feeds/topics response (has name + all attrs)
    topic_meta: dict[str, dict] = {}
    for t in all_topics:
        tid = t.get("id")
        if not tid:
            continue
        topic_meta[tid] = {attr: t.get(attr) for attr in TOPIC_ATTRS}

    # 2. Build category assignments — smallest category first so most-specific wins
    cats_r = client.get(BASE + "/api/v1/feeds/categories", headers=HEADERS)
    cats_r.raise_for_status()
    cats: list[dict] = cats_r.json()

    topic_cat: dict[str, str] = {}
    # Sort ascending by topic_count so smallest (most-specific) is processed first
    for ct in sorted(cats, key=lambda c: c["topic_count"]):
        cat_topics = _fetch_category_topics(client, ct["id"], ct["topic_count"])
        for t in cat_topics:
            tid = t.get("id") if isinstance(t, dict) else t
            if not tid:
                continue
            # setdefault: first write wins → most-specific category wins
            topic_cat.setdefault(tid, ct["name"])
        print(f"  catalog: {ct['name']} -> {len(cat_topics)} topics", flush=True)

    print(
        f"  priority-assigned partition: {dict(Counter(topic_cat.values()))}",
        flush=True,
    )

    return topic_cat, topic_meta


def write_csv(
    topic_cat: dict[str, str],
    topic_meta: dict[str, dict],
    out_path: str,
) -> int:
    """Write the catalog CSV from the topic_cat and topic_meta dicts.

    Returns the number of rows written.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for tid, meta in topic_meta.items():
            row = {"topic_id": tid, "category": topic_cat.get(tid, "Uncategorized")}
            for attr in TOPIC_ATTRS:
                val = meta.get(attr)
                if isinstance(val, list):
                    val = ";".join(str(v) for v in val)
                elif val is None:
                    val = ""
                row[attr] = val
            writer.writerow(row)
    return len(topic_meta)


def pull_topic_catalog(out_path: str = OUT) -> int:
    """Fetch the full monitored-institutions catalog and write to out_path CSV.

    Returns the number of rows written.
    """
    with httpx.Client(timeout=300) as client:
        topic_cat, topic_meta = fetch_catalog(client)

    n = write_csv(topic_cat, topic_meta, out_path)
    print(f"\nWrote {n} rows -> {out_path}", flush=True)
    return n


if __name__ == "__main__":
    n = pull_topic_catalog()
    if n < 1000:
        print(f"WARNING: only {n} institutions — expected ~1,071", file=sys.stderr)
