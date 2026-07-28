#!/usr/bin/env python3
"""
Phase 6 analysis for the cost-accuracy-latency experiment.
Spec: docs/superpowers/specs/2026-07-27-cost-accuracy-experiment-plan.md

Consumes runs.jsonl + grades.jsonl, emits figures/frontier-data.json — which becomes the
single source of truth for every number the whitepaper would render, exactly as
whitepaper-data.json already is for v1.1.

Scoring rule (from the plan): accuracy for a run is passed/total of that question's checks,
EXCEPT that failing any must-pass check caps the run at 0. Must-pass checks are the precision
side (cite-real, no-fabricated-obligation) — the old regex rubric measured recall only, so a
confidently-hallucinating arm could have scored 100%.

Two stratifications are reported:
  DESIGNED   — the a-priori labels in questions.json
  EMPIRICAL  — questions regrouped by whether the memory-only baseline actually answered them,
               because a 2026 record date does not prove the obligation was unknowable in 2024.
               The empirical split is the defensible one; the designed split is kept so the
               difference between intent and outcome stays visible.
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
RUNS = HERE / "runs.jsonl"
GRADES = HERE / "grades.jsonl"
OUT = PROJECT / "whitepaper" / "figures" / "frontier-data.json"

ARMS = ["baseline", "web", "carver-full", "carver-domain"]
BASELINE_KNOWABLE_THRESHOLD = 0.5  # mean baseline accuracy above which a question is "knowable"


def load(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


runs = load(RUNS)
grades = load(GRADES)
spec = json.loads((HERE / "questions.json").read_text())
questions = {q["id"]: q for q in spec["questions"]}

main = [r for r in runs if r["phase"] == "main" and not r["error"]]
replay = [r for r in runs if r["phase"] == "replay" and not r["error"]]

# ---------------------------------------------------------------- scoring

by_run = defaultdict(list)
for g in grades:
    by_run[g["run_id"]].append(g)


def score_run(run_id):
    """Return (accuracy, error_types, ungraded_count) for one run."""
    gs = by_run.get(run_id, [])
    if not gs:
        return None, [], 0
    ungraded = sum(1 for g in gs if g["pass"] is None)
    graded = [g for g in gs if g["pass"] is not None]
    if not graded:
        return None, [], ungraded
    must_fail = [g for g in graded if g["must_pass"] and not g["pass"]]
    errs = [g["error_type"] for g in graded if not g["pass"] and g["error_type"]]
    if must_fail:
        return 0.0, errs, ungraded
    return sum(1 for g in graded if g["pass"]) / len(graded), errs, ungraded


scored = []
for r in main:
    acc, errs, ung = score_run(r["run_id"])
    if acc is None:
        continue
    scored.append({**r, "accuracy": acc, "error_types": errs, "ungraded": ung})

# ---------------------------------------------------------------- empirical strata

base_by_q = defaultdict(list)
for s in scored:
    if s["arm"] == "baseline":
        base_by_q[s["question_id"]].append(s["accuracy"])
baseline_knowable = {q: (st.mean(v) >= BASELINE_KNOWABLE_THRESHOLD) for q, v in base_by_q.items()}


def empirical_stratum(s):
    if s["stratum"] == "tail-silent-trigger":
        return "tail-silent-trigger"
    return "baseline-knowable" if baseline_knowable.get(s["question_id"]) else "baseline-blind"


for s in scored:
    s["empirical_stratum"] = empirical_stratum(s)

# ---------------------------------------------------------------- aggregates


def iqr(v):
    if len(v) < 4:
        return [round(min(v), 4), round(max(v), 4)]
    q = st.quantiles(v, n=4)
    return [round(q[0], 4), round(q[2], 4)]


def agg(rows):
    if not rows:
        return None
    acc = [r["accuracy"] for r in rows]
    cost = [r["cost_usd"] for r in rows]
    lat = [r["latency_ms"] / 1000 for r in rows]
    tok = [r["usage"]["total"] for r in rows]
    errs = defaultdict(int)
    for r in rows:
        for e in r["error_types"]:
            errs[e] += 1
    # reproducibility: mean per-question spread across repeats
    per_q = defaultdict(list)
    for r in rows:
        per_q[r["question_id"]].append(r["accuracy"])
    spreads = [max(v) - min(v) for v in per_q.values() if len(v) > 1]
    return {
        "n_runs": len(rows),
        "n_questions": len(per_q),
        "accuracy_mean": round(st.mean(acc), 4),
        "accuracy_zero_rate": round(sum(1 for a in acc if a == 0) / len(acc), 4),
        "cost_usd_median": round(st.median(cost), 4),
        "cost_usd_iqr": iqr(cost),
        "cost_usd_p90": round(sorted(cost)[min(len(cost) - 1, int(0.9 * len(cost)))], 4),
        "cost_per_1k_median": round(1000 * st.median(cost), 2),
        "latency_s_median": round(st.median(lat), 1),
        "latency_s_range": [round(min(lat), 1), round(max(lat), 1)],
        "latency_s_p90": round(sorted(lat)[min(len(lat) - 1, int(0.9 * len(lat)))], 1),
        "tokens_median": int(st.median(tok)),
        "error_counts": dict(errs),
        "repeat_accuracy_spread_mean": round(st.mean(spreads), 4) if spreads else 0.0,
    }


report = {
    "_meta": {
        "source_runs": str(RUNS.relative_to(PROJECT)),
        "source_grades": str(GRADES.relative_to(PROJECT)),
        "model": main[0]["model"] if main else None,
        "rates": main[0]["rates"] if main else None,
        "corpus": spec["_meta"]["corpus"],
        "arms": spec["_meta"]["arms"],
        "scoring": "accuracy = passed/total checks; ANY must-pass failure caps the run at 0",
        "known_bias": spec["_meta"]["known_bias"],
        "runs_total": len(runs),
        "runs_failed": sum(1 for r in runs if r["error"]),
        "runs_scored": len(scored),
        "checks_ungraded": sum(s["ungraded"] for s in scored),
        "spend_usd": round(sum(r["cost_usd"] or 0 for r in runs), 2),
    },
    "pooled": {},
    "by_designed_stratum": {},
    "by_empirical_stratum": {},
    "frontier": [],
    "breakeven": {},
    "replay": {},
    "baseline_knowable_questions": baseline_knowable,
}

for a in ARMS:
    report["pooled"][a] = agg([s for s in scored if s["arm"] == a])

for key, field in [("by_designed_stratum", "stratum"), ("by_empirical_stratum", "empirical_stratum")]:
    strata = sorted({s[field] for s in scored})
    for stratum in strata:
        report[key][stratum] = {a: agg([s for s in scored if s[field] == stratum and s["arm"] == a]) for a in ARMS}

# ---------------------------------------------------------------- frontier

for a in ARMS:
    p = report["pooled"][a]
    if p:
        report["frontier"].append({"arm": a, "cost_usd_median": p["cost_usd_median"], "accuracy_mean": p["accuracy_mean"], "latency_s_median": p["latency_s_median"]})

# Pareto: an arm is dominated if another is >= on accuracy AND <= on cost (strict on one).
for pt in report["frontier"]:
    dom = [
        o["arm"]
        for o in report["frontier"]
        if o["arm"] != pt["arm"]
        and o["accuracy_mean"] >= pt["accuracy_mean"]
        and o["cost_usd_median"] <= pt["cost_usd_median"]
        and (o["accuracy_mean"] > pt["accuracy_mean"] or o["cost_usd_median"] < pt["cost_usd_median"])
    ]
    pt["dominated_by"] = dom
    pt["on_frontier"] = not dom

# ---------------------------------------------------------------- breakeven

base = report["pooled"]["baseline"]
if base:
    # flawed-answer rate: share of baseline runs with at least one failed check
    flawed = [s for s in scored if s["arm"] == "baseline"]
    flawed_rate = sum(1 for s in flawed if s["accuracy"] < 1.0) / len(flawed)
    for a in ["carver-full", "carver-domain", "web"]:
        p = report["pooled"][a]
        if not p:
            continue
        delta = p["cost_usd_median"] - base["cost_usd_median"]
        acc_gain = p["accuracy_mean"] - base["accuracy_mean"]
        report["breakeven"][a] = {
            "extra_cost_per_question_usd": round(delta, 4),
            "baseline_flawed_answer_rate": round(flawed_rate, 4),
            "accuracy_gain_over_baseline": round(acc_gain, 4),
            "cost_per_flawed_answer_avoided_usd": round(delta / acc_gain, 4) if acc_gain > 0 else None,
            "definition": "flawed = baseline run with >=1 failed check; cost per avoided flaw = extra $/question / accuracy gain",
        }

# ---------------------------------------------------------------- replay

first = {(r["question_id"], r["arm"]): r for r in main if r["repeat"] == 1}
for a in ["web", "carver-full", "carver-domain"]:
    pairs = [(first[(r["question_id"], r["arm"])], r) for r in replay if r["arm"] == a and (r["question_id"], r["arm"]) in first]
    if not pairs:
        continue
    f = st.median(p[0]["cost_usd"] for p in pairs)
    p_ = st.median(p[1]["cost_usd"] for p in pairs)
    cached_share = st.median(
        p[1]["usage"]["cached_input"] / max(1, p[1]["usage"]["fresh_input"] + p[1]["usage"]["cache_write_input"] + p[1]["usage"]["cached_input"])
        for p in pairs
    )
    report["replay"][a] = {
        "n_pairs": len(pairs),
        "first_run_cost_per_1k": round(1000 * f, 2),
        "replay_cost_per_1k": round(1000 * p_, 2),
        "change_pct": round(100 * (p_ - f) / f, 1),
        "cached_input_share": round(cached_share, 4),
    }
report["replay"]["_whitepaper_projection"] = {
    "projected_cost_per_1k": 22.57,
    "projected_assumption": "~90% of fresh input tokens cache on replay",
    "verdict": "SUPERSEDED — see measured cached_input_share and replay_cost_per_1k above",
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))
print(f"wrote {OUT.relative_to(PROJECT)}")

# ---------------------------------------------------------------- console summary

print(f"\n{report['_meta']['runs_scored']} scored runs · {report['_meta']['checks_ungraded']} ungraded checks · ${report['_meta']['spend_usd']} spent\n")
print(f"{'arm':<16}{'acc':>7}{'zero%':>7}{'$/q':>9}{'p90 $':>8}{'lat s':>7}{'errors'}")
for a in ARMS:
    p = report["pooled"][a]
    if not p:
        continue
    e = ", ".join(f"{k} {v}" for k, v in sorted(p["error_counts"].items(), key=lambda x: -x[1]))
    print(f"{a:<16}{100*p['accuracy_mean']:>6.0f}%{100*p['accuracy_zero_rate']:>6.0f}%{p['cost_usd_median']:>9.3f}{p['cost_usd_p90']:>8.3f}{p['latency_s_median']:>7.1f}  {e}")

for label, key in [("DESIGNED", "by_designed_stratum"), ("EMPIRICAL", "by_empirical_stratum")]:
    print(f"\n--- accuracy by {label} stratum ---")
    print(f"{'stratum':<22}" + "".join(f"{a:>16}" for a in ARMS))
    for stratum, d in report[key].items():
        cells = "".join(f"{100*d[a]['accuracy_mean']:>15.0f}%" if d[a] else f"{'-':>16}" for a in ARMS)
        print(f"{stratum:<22}{cells}")

print("\n--- frontier ---")
for pt in report["frontier"]:
    tag = "ON FRONTIER" if pt["on_frontier"] else f"dominated by {', '.join(pt['dominated_by'])}"
    print(f"  {pt['arm']:<16} ${pt['cost_usd_median']:.3f}  {100*pt['accuracy_mean']:.0f}%  -> {tag}")

print("\n--- replay vs whitepaper projection ($22.57/1k) ---")
for a, d in report["replay"].items():
    if a.startswith("_"):
        continue
    print(f"  {a:<16} first ${d['first_run_cost_per_1k']:,.0f}/1k -> replay ${d['replay_cost_per_1k']:,.0f}/1k  ({d['change_pct']:+.0f}%, cached {100*d['cached_input_share']:.0f}%)")
