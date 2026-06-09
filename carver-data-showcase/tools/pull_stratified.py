"""Build a CATEGORY-STRATIFIED annotation snapshot spanning all 3 categories.

The first contiguous offset walk (tools/pull_annotations.py) landed ~99% in Finance
(Medical Devices = 0 records), so it can't demonstrate range ACROSS the 3 categories —
the showcase's #1 objective. This puller fixes that, still via the direct Artifacts API
(no SDK, no LLM), using the `topic_ids_in` filter + the categories catalog:

  Medical Devices  : all annotations for its 24 topics  (~8,850)
  Data protection  : all annotations for its 54 topics  (~10,224)
  Finance          : FINANCE_CAP records reused from the existing Finance-heavy snapshot

Also emits data/topic_categories.csv (topic_id -> category + key topic attributes) built
from the catalog, so the pipeline can join category and enrich range views deterministically.

Hardened after a runaway incident: the catalog fetch is validated against each category's
topic_count (retried on transient partial responses), pull_by_topics REFUSES an empty
topic-id filter (an empty `topic_ids_in` is treated as "no filter" by the API and would pull
the whole corpus), and a hard global cap bounds the total.

Run: .venv/bin/python tools/pull_stratified.py
"""

import csv
import json
import os
import time

import httpx
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))

BASE = os.environ.get("CARVER_BASE_URL", "https://app.carveragents.ai")
KEY = os.environ["CARVER_API_KEY"]
DAG = "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad"
HEADERS = {"X-API-Key": KEY}
CHUNK = 10_000
FINANCE_CAP = 40_000
MAX_TOTAL = 95_000           # hard safety ceiling (stay < 100K no matter what)
CATEGORY_FETCH_RETRIES = 5

OUT = os.path.join(ROOT, "data", "annotations.jsonl")
PREV = os.path.join(ROOT, "data", "annotations.prev.jsonl")  # existing Finance-heavy snapshot
CATCSV = os.path.join(ROOT, "data", "topic_categories.csv")

TOPIC_ATTRS = ["jurisdiction_code", "jurisdiction_detail", "scope", "govt_body",
               "acronym", "hq", "base_domain", "sectors", "industries", "entity_type"]


def fetch_category_topics(client, cid, expected):
    """GET a category's topics, retrying until the count matches `expected` (the catalog's
    topic_count). Guards against the transient partial/empty responses that caused a runaway."""
    for attempt in range(1, CATEGORY_FETCH_RETRIES + 1):
        r = client.get(BASE + f"/api/v1/feeds/categories/{cid}/topics", headers=HEADERS)
        topics = r.json() if r.status_code == 200 else []
        if isinstance(topics, list) and len(topics) == expected:
            return topics
        print(f"  [retry {attempt}] category {cid}: got {len(topics) if isinstance(topics,list) else 'ERR'} "
              f"!= expected {expected}; backing off", flush=True)
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"category {cid}: could not fetch {expected} topics after "
                       f"{CATEGORY_FETCH_RETRIES} retries — aborting (refusing a partial map)")


def fetch_catalog(client):
    """Build topic -> MOST-SPECIFIC category. Topics are multi-category and the smaller
    categories (Medical Devices, Data protection) are subsets of Finance, so we assign each
    topic to its smallest (most-specific) category: MD > DP > Finance. This yields a clean
    1-category-per-topic partition (MD 24 / DP 53 / Finance 533) for an honest 3-way split."""
    cats = client.get(BASE + "/api/v1/feeds/categories", headers=HEADERS).json()
    topic_cat, topic_meta = {}, {}
    # smallest topic_count first => most-specific category wins via setdefault
    for ct in sorted(cats, key=lambda c: c["topic_count"]):
        topics = fetch_category_topics(client, ct["id"], ct["topic_count"])
        for t in topics:
            topic_cat.setdefault(t["id"], ct["name"])
            topic_meta.setdefault(t["id"], {a: t.get(a) for a in TOPIC_ATTRS})
        print(f"  catalog: {ct['name']} -> {len(topics)} topics", flush=True)
    from collections import Counter
    print(f"  priority-assigned partition: {dict(Counter(topic_cat.values()))}", flush=True)
    return cats, topic_cat, topic_meta


def pull_by_topics(client, topic_ids, fh, cap):
    if not topic_ids:
        raise ValueError("pull_by_topics called with empty topic_ids — refusing "
                         "(empty topic_ids_in would pull the whole corpus)")
    ids = ",".join(topic_ids)
    offset, total = 0, 0
    while total < cap:
        limit = min(CHUNK, cap - total)
        url = (f"{BASE}/api/v1/artifacts/dags/{DAG}/artifacts?state=completed&dry_run=true"
               f"&artifact_type_id=annotations-v1&limit={limit}&offset={offset}&topic_ids_in={ids}")
        rows = client.get(url, headers=HEADERS).raise_for_status().json()
        if not rows:
            break
        for art in rows:
            fh.write(json.dumps(art) + "\n")
        total += len(rows)
        offset += len(rows)
        if len(rows) < limit:
            break
        time.sleep(0.1)
    return total


def main():
    if os.path.exists(OUT) and not os.path.exists(PREV):
        os.rename(OUT, PREV)

    with httpx.Client(timeout=300) as client:
        cats, topic_cat, topic_meta = fetch_catalog(client)
        names = {c["name"] for c in cats}
        required = {"Finance", "Medical Devices", "Data protection and cybersecurity"}
        missing = required - names
        if missing:
            raise RuntimeError(f"catalog missing categories: {missing}")
        # Confirm every required category actually contributed topics to the map.
        mapped = set(topic_cat.values())
        if required - mapped:
            raise RuntimeError(f"map missing topics for: {required - mapped}")

        with open(CATCSV, "w", newline="") as cf:
            w = csv.writer(cf)
            w.writerow(["topic_id", "category"] + TOPIC_ATTRS)
            for tid, cat in topic_cat.items():
                m = topic_meta.get(tid, {})
                w.writerow([tid, cat] + [
                    ";".join(m[a]) if isinstance(m.get(a), list) else m.get(a)
                    for a in TOPIC_ATTRS])
        print(f"wrote {CATCSV} ({len(topic_cat)} topics)", flush=True)

        finance_topics = {t for t, c in topic_cat.items() if c == "Finance"}
        counts = {}
        total_written = 0
        with open(OUT, "w") as out:
            for name in ["Medical Devices", "Data protection and cybersecurity"]:
                tids = [t for t, c in topic_cat.items() if c == name]
                budget = min(CHUNK * 10, MAX_TOTAL - total_written)
                n = pull_by_topics(client, tids, out, cap=budget)
                counts[name] = n
                total_written += n
                print(f"{name}: pulled {n:,} records ({len(tids)} topics)", flush=True)

            fin = 0
            fin_cap = min(FINANCE_CAP, MAX_TOTAL - total_written)
            if os.path.exists(PREV):
                with open(PREV) as prev:
                    for line in prev:
                        if fin >= fin_cap:
                            break
                        try:
                            tid = json.loads(line).get("topic_id")
                        except json.JSONDecodeError:
                            continue
                        if tid in finance_topics:
                            out.write(line)
                            fin += 1
            counts["Finance"] = fin
            print(f"Finance: reused {fin:,} records from {os.path.basename(PREV)}", flush=True)

    total = sum(counts.values())
    print(f"\nSTRATIFIED SNAPSHOT total={total:,} -> {OUT}", flush=True)
    for k, v in counts.items():
        print(f"  {k}: {v:,} ({100*v/total:.1f}%)", flush=True)
    if not (30_000 <= total <= 100_000):
        raise SystemExit(f"ERROR: total {total} outside 30K-100K band")


if __name__ == "__main__":
    main()
