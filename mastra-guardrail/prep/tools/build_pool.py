"""Build a probe pool: candidates filtered to one or more industry domains.

Zero API calls. Output feeds `probe_recency.py` / `probe_targeted.py`.

    cd mastra-guardrail/prep && PYTHONPATH=. .venv/bin/python \
        tools/build_pool.py <out.json> <domain> [<domain> …]

e.g. tools/build_pool.py data/scratch/cyber.json cybersecurity

Filters on `impacted_business.industry` — the taxonomy field, not free text — so
the pool is precise. See `mine_domains.py` for which domains are worth picking.
"""
import json
import sys
from collections import Counter

from mastra_prep.candidates import is_candidate
from mastra_prep.config import load_settings
from mastra_prep.extract import extract_record
from mastra_prep.reader import stream_annotations

OUT, DOMAINS = sys.argv[1], {d.lower().strip() for d in sys.argv[2:]}
if not DOMAINS:
    raise SystemExit("give at least one domain — see tools/mine_domains.py for the ranking")

cfg = load_settings("config.yaml")
pool, by_regulator, by_type = [], Counter(), Counter()

for raw in stream_annotations(cfg.annotations_path):
    rec = extract_record(raw)
    if rec is None:
        continue
    ok, _ = is_candidate(rec)
    if not ok:
        continue
    industries = {str(i).lower().strip() for i in
                  ((rec.get("impacted_business") or {}).get("industry") or [])}
    if not (industries & DOMAINS):
        continue
    pool.append(rec)
    by_regulator[(rec.get("regulator_name") or "?").strip()] += 1
    by_type[str(rec.get("update_type") or "").lower()] += 1

pool.sort(key=lambda r: str(r.get("reconciled_published_date") or ""), reverse=True)
print(f"domains {sorted(DOMAINS)} -> {len(pool):,} records, "
      f"{len(by_regulator):,} regulators")
print("\nby update_type:")
for t, c in by_type.most_common():
    print(f"  {c:>5,}  {t}")
print("\ntop regulators:")
for r, c in by_regulator.most_common(15):
    print(f"  {c:>5,}  {r}")
print("\n10 most recent:")
for r in pool[:10]:
    print(f"  {r.get('reconciled_published_date')}  "
          f"{(r.get('regulator_name') or '?')[:34]:<34} {(r.get('title') or '')[:52]}")

json.dump(pool, open(OUT, "w"), indent=2, default=str)
print(f"\nwrote {len(pool):,} records to {OUT}")
