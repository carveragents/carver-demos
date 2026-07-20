"""Bounded probe over an arbitrary record pool, reusing the shipped pipeline.

Calls `curate.probe_and_score_one` unmodified — same URL gate, same Stage A/B,
same judge, same scorers as a real run — but over a pool YOU choose and under its
own low ceiling. Use it to test a hypothesis for a couple of dollars instead of
committing to a full Phase 7 sweep.

    cd mastra-guardrail/prep && PYTHONPATH=. .venv/bin/python \
        tools/probe_targeted.py <pool.json> <out.json> <n> <ceiling_usd>

`pool.json` is a list of EXTRACTED records (`extract_record`'s flat shape).

NOTE ON THE CEILING: the budget reserves each call at the PROVIDER MAXIMUM
(~$5.09), not at expected cost, so a ceiling below ~$6 refuses the very first
call however cheap the run actually is. Observed real cost is ~$0.028/record.

MEASURED RESULT, 2026-07-20 (100 financial scenario-B records, $2.26): ZERO
survivors. Not because the baseline is strong — because the task never engages
the obligation. All 83 non-gated records scored `applies_to_draft: False`, 82/83
`citation_missing` (the baseline declines to cite, so it can never FABRICATE a
citation), and 73/83 had no ground-truth date to be wrong about. The scenario
task ("draft a promotional email") is too generic to be governed by a specific
record. Read that before spending on a full run.
"""
import json
import sys
from collections import Counter

from mastra_prep.budget import SpendBudget
from mastra_prep.config import load_settings
from mastra_prep.curate import probe_and_score_one
from mastra_prep.openai_client import load_env, make_client
from mastra_prep.scenarios import SCENARIO_B

POOL, OUT, N, CEILING = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])

cfg = load_settings("config.yaml")
load_env(cfg.dotenv_path)
client = make_client()
budget = SpendBudget(CEILING, cfg.price_input_per_million_usd, cfg.price_output_per_million_usd)

pool = json.load(open(POOL))
pool.sort(key=lambda r: str(r.get("reconciled_published_date") or ""), reverse=True)
selected = pool[:N]
print(f"pool {len(pool):,} -> probing {len(selected)} (most recent), ceiling ${CEILING}\n", flush=True)

results, survivors, reasons = [], [], Counter()
for i, rec in enumerate(selected, 1):
    try:
        res = probe_and_score_one(client, rec, SCENARIO_B, cfg, budget)
    except Exception as exc:
        print(f"[{i}/{len(selected)}] STOP: {type(exc).__name__}: {exc}", flush=True)
        break
    results.append(res)
    if res.get("disqualified_reason"):
        reasons[res["disqualified_reason"]] += 1
        label = res["disqualified_reason"]
    elif res.get("passes_failure_bar"):
        survivors.append(res)
        reasons["SURVIVOR"] += 1
        label = "SURVIVOR"
    else:
        reasons["probed_no_failure"] += 1
        label = "no-failure"
    print(f"[{i:>3}/{len(selected)}] {label:<32} ${budget.spend_so_far_usd:.3f}  "
          f"{(rec.get('title') or '')[:56]}", flush=True)

print(f"\n{'='*68}\nprobed    : {len(results)}\nSURVIVORS : {len(survivors)}"
      f"\nspend     : ${budget.spend_so_far_usd:.2f} of ${CEILING}\n{'='*68}")
for r, c in reasons.most_common():
    print(f"  {c:>4}  {r}")

# Outcome distribution is the real diagnostic — a zero survivor count says nothing
# on its own about WHY.
for field in ("citation", "date", "obligation"):
    dist = Counter((r.get(field) or {}).get("outcome") for r in results
                   if not r.get("disqualified_reason"))
    print(f"\n{field} outcomes:")
    for k, c in dist.most_common():
        print(f"  {c:>4}  {k}")

json.dump({"probed": len(results), "survivors": len(survivors),
           "spend_usd": budget.spend_so_far_usd, "reasons": dict(reasons),
           "results": results}, open(OUT, "w"), indent=2, default=str)
print(f"\nwrote {OUT}")
