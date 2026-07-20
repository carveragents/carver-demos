"""Which DOMAIN gives the strongest grounded-vs-ungrounded contrast?

Zero API calls. Scores each industry domain on the levers goal.md ranks: how
unlikely the model is to know the regulator, how long the regulator tail is, and
how deep the obligations are.

    cd mastra-guardrail/prep && PYTHONPATH=. .venv/bin/python tools/mine_domains.py [out.json]

THE SCORE IS A HEURISTIC, NOT A MEASUREMENT. It predicts where the baseline should
be weak; only a probe confirms it. Use it to pick what to probe, never as evidence.

Measured 2026-07-20: cybersecurity is 100% non-famous regulators, insurance is
97% across 157 bodies. `financial services` is the WORST domain in the corpus
(54% famous bodies) — a frontier model knows those cold.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict

from mastra_prep.candidates import is_candidate
from mastra_prep.config import load_settings
from mastra_prep.extract import extract_record
from mastra_prep.reader import stream_annotations

MIN_DOMAIN_SIZE = 80
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/scratch/domain-scores.json"

# Bodies a frontier model plausibly knows cold — contrast is weakest here.
FAMOUS = {
    "securities and exchange commission", "u.s. securities and exchange commission",
    "federal trade commission", "european commission", "financial conduct authority",
    "food and drug administration", "u.s. food and drug administration", "federal reserve",
    "commodity futures trading commission", "european central bank", "bank of england",
    "federal communications commission", "consumer financial protection bureau",
    "united states food and drug administration", "european banking authority",
    "european securities and markets authority", "internal revenue service",
}

cfg = load_settings("config.yaml")
domains = defaultdict(lambda: {"n": 0, "regs": Counter(), "famous": 0, "reqs": [],
                               "cdate": 0, "samples": []})

for raw in stream_annotations(cfg.annotations_path):
    rec = extract_record(raw)
    if rec is None:
        continue
    ok, _ = is_candidate(rec)
    if not ok:
        continue
    regulator = (rec.get("regulator_name") or "?").strip()
    is_famous = regulator.lower() in FAMOUS
    for industry in ((rec.get("impacted_business") or {}).get("industry") or []):
        d = domains[str(industry).lower().strip()]
        d["n"] += 1
        d["regs"][regulator] += 1
        d["famous"] += int(is_famous)
        d["reqs"].append(len(rec.get("key_requirements") or []))
        d["cdate"] += int(bool(rec.get("compliance_date")))
        if len(d["samples"]) < 5 and not is_famous:
            d["samples"].append({
                "date": rec.get("reconciled_published_date"),
                "regulator": regulator,
                "title": (rec.get("title") or "")[:70],
            })

rows = []
for name, d in domains.items():
    if d["n"] < MIN_DOMAIN_SIZE:
        continue
    obscurity = 1 - d["famous"] / d["n"]        # higher = model less likely to know it
    reg_spread = len(d["regs"]) / d["n"]        # higher = longer tail
    med_reqs = statistics.median(d["reqs"]) if d["reqs"] else 0
    rows.append({
        "domain": name, "n": d["n"], "regulators": len(d["regs"]),
        "obscurity": obscurity, "median_reqs": med_reqs,
        "compliance_date_pct": 100 * d["cdate"] / d["n"],
        "score": obscurity * (0.5 + reg_spread) * min(med_reqs, 8) / 8,
        "samples": d["samples"],
    })
rows.sort(key=lambda r: r["score"], reverse=True)

print(f"{'domain':<22}{'n':>7}{'regs':>6}{'obscure':>9}{'medReq':>8}{'cdate%':>8}{'score':>7}")
print("-" * 67)
for r in rows[:20]:
    print(f"{r['domain'][:21]:<22}{r['n']:>7,}{r['regulators']:>6}{r['obscurity']:>8.0%}"
          f"{r['median_reqs']:>8.0f}{r['compliance_date_pct']:>7.0f}%{r['score']:>7.2f}")

print("\n== samples from the top 5 domains (non-famous regulators only) ==")
for r in rows[:5]:
    print(f"\n--- {r['domain']}  (n={r['n']:,}, {r['regulators']} regulators, "
          f"{r['obscurity']:.0%} non-famous) ---")
    for s in r["samples"]:
        print(f"   {s['date']} · {s['regulator'][:32]} · {s['title']}")

with open(OUT, "w") as fh:
    json.dump(rows, fh, indent=2)
print(f"\nwrote {OUT}")
