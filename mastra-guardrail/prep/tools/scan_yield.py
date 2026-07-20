"""Free yield gate: how many candidates does the filter find, and what are they?

Zero API calls. Run this BEFORE spending anything — it is the cheap answer to
"is the pool there?", and it is what P8.0's yield gate should be reading.

    cd mastra-guardrail/prep && PYTHONPATH=. .venv/bin/python tools/scan_yield.py [out.json]

Measured 2026-07-20 against the 2026-07-06 snapshot: 7,036 candidates of 244,545
records (goal.md's 8,260 was the 2026-07-11 snapshot; the gap is almost entirely
July, 136 vs 373).
"""
import json
import sys
from collections import Counter

from mastra_prep.candidates import CANDIDATE_CUTOFF_DATE, SNAPSHOT_DATE, is_candidate
from mastra_prep.config import load_settings
from mastra_prep.extract import extract_record
from mastra_prep.reader import stream_annotations

OUT = sys.argv[1] if len(sys.argv) > 1 else "data/scratch/yield-report.json"

cfg = load_settings("config.yaml")
total = candidates = 0
fail_reasons = Counter()
by_month = Counter()
by_update_type = Counter()
by_jurisdiction = Counter()
by_regulator = Counter()
affordances = Counter()

for raw in stream_annotations(cfg.annotations_path):
    total += 1
    if total % 25000 == 0:
        print(f"  scanned {total:,} … {candidates:,} candidates", flush=True)
    rec = extract_record(raw)
    if rec is None:
        continue
    ok, failed = is_candidate(rec)
    if not ok:
        for f in failed:
            fail_reasons[f] += 1
        continue
    candidates += 1
    by_month[str(rec.get("reconciled_published_date") or "")[:7]] += 1
    by_update_type[str(rec.get("update_type") or "").lower().strip()] += 1
    by_jurisdiction[rec.get("jurisdiction_country") or rec.get("jurisdiction_bloc") or "?"] += 1
    by_regulator[(rec.get("regulator_name") or "?").strip()] += 1
    # Which deterministic failure modes even have material to work with.
    if rec.get("compliance_date"):
        affordances["compliance_date"] += 1
    if rec.get("effective_date"):
        affordances["effective_date"] += 1
    if rec.get("penalties_consequences"):
        affordances["penalties"] += 1

print("\n" + "=" * 68)
print(f"window     : {CANDIDATE_CUTOFF_DATE} .. {SNAPSHOT_DATE}")
print(f"records    : {total:,}")
print(f"CANDIDATES : {candidates:,}")
print(f"regulators : {len(by_regulator):,} distinct")
print("=" * 68)

print("\n-- failure-mode affordances (what the scorers have to work with) --")
for k, n in affordances.most_common():
    print(f"  {n:>6,} ({100*n/candidates:>5.1f}%)  {k}")

for title, counter, limit in (
    ("rejection reasons (a record can fail several)", fail_reasons, None),
    ("by month", by_month, None),
    ("by update_type", by_update_type, None),
    ("by jurisdiction", by_jurisdiction, 15),
    ("by regulator", by_regulator, 20),
):
    print(f"\n-- {title} --")
    items = sorted(counter.items()) if title == "by month" else counter.most_common(limit)
    for k, n in items:
        print(f"  {n:>7,}  {k}")

with open(OUT, "w") as fh:
    json.dump({
        "window": [CANDIDATE_CUTOFF_DATE, SNAPSHOT_DATE],
        "total_records": total, "candidates": candidates,
        "affordances": dict(affordances), "fail_reasons": dict(fail_reasons),
        "by_month": dict(by_month), "by_update_type": dict(by_update_type),
        "by_jurisdiction": dict(by_jurisdiction), "by_regulator": dict(by_regulator),
    }, fh, indent=2)
print(f"\nwrote {OUT}")
