"""Sample what topics live at high offsets and compare to our 165-topic allowlist."""
import os, json, httpx
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.environ["CARVER_API_KEY"]
URL = "https://app.carveragents.ai/api/v1/artifacts/dags/7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad/artifacts"

# Load our PM-relevant topic ids
import yaml
with open("data/regulator-topics.yml") as f:
    classified = yaml.safe_load(f)
pm_topic_ids = {c["topic_id"] for c in classified if c["pm_relevant"]}
topics_by_id = {c["topic_id"]: c for c in classified}
print(f"Our PM-relevant allowlist: {len(pm_topic_ids)} topics\n")

# Sample 1000 records from a high offset
r = httpx.get(URL, params={"dag_ids_in": "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad",
                             "state": "completed", "limit": 1000, "offset": 100000},
              headers={"X-API-Key": API_KEY}, timeout=120.0)
body = r.json()
print(f"Sampled {len(body)} records at offset=100000\n")

# Bucket by whether topic is in our allowlist
in_list = [a for a in body if a.get("topic_id") in pm_topic_ids]
not_in_list = [a for a in body if a.get("topic_id") not in pm_topic_ids]
print(f"  In our allowlist: {len(in_list)}")
print(f"  NOT in allowlist: {len(not_in_list)}")

# Top topics NOT in allowlist
print("\nTop 20 topics in this page NOT in our allowlist:")
ttoo = Counter(a.get("topic_id") for a in not_in_list)
for tid, n in ttoo.most_common(20):
    info = topics_by_id.get(tid)
    if info:
        print(f"  {n:>4}  {info['name']}  [{info.get('jurisdiction_code')}, {info.get('sub_entity_type') or '—'}]")
    else:
        # Topic exists in pull but not in our catalog — odd
        print(f"  {n:>4}  <unknown topic_id={tid}>")

# Sample some records' regulator_name / update_type to see if they look PM-relevant
print("\nSample 10 NOT-IN-LIST records — regulator + title + update_type:")
import random
random.seed(0)
for a in random.sample(not_in_list, min(10, len(not_in_list))):
    od = a.get("output_data") or {}
    cls = od.get("classification") or {}
    em = (a.get("input_data") or {}).get("extracted_metadata") or {}
    title = em.get("title", "")[:70]
    reg = (cls.get("regulatory_source") or {}).get("name", "")[:50]
    ut = cls.get("update_type", "")
    tid = a.get("topic_id")
    tinfo = topics_by_id.get(tid, {})
    tname = tinfo.get('name', '?')[:40] if tinfo else '?'
    print(f"  [{ut:<15}] {reg:<50} | {title:<70} | topic={tname}")
