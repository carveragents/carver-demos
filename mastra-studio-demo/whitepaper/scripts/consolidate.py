#!/usr/bin/env python3
"""Merge the mined section figures with the measured demo numbers (section 3),
the lending exemplar (section 4) and retrieval evidence (section 5) into a
single source-of-truth file the whitepaper build reads. Every hardcoded number
below is transcribed from docs/DEMO.md (measured 2026-07-23) or the curated
data/state-lending-records.json — no invented values."""
import json, os

BASE = "/home/ubuntu/work/scribble/code/repos/carver-demos-docs-carver-whitepaper/mastra-studio-demo/whitepaper/figures"
s1 = json.load(open(os.path.join(BASE, "section1.json")))
s2 = json.load(open(os.path.join(BASE, "section2.json")))

# --- clean freshness to a sensible window (drop calendar-conversion artifacts
#     like year 1442/2567 and stray future dates); keep 2016..2026 ---
years = {r["year"]: r["count"] for r in s1["published_by_year"]}
fresh = [{"year": y, "count": years.get(y, 0)} for y in [str(x) for x in range(2016, 2027)]]
recent_2y = years.get("2025", 0) + years.get("2026", 0)
recent_share = round(100 * recent_2y / s1["total_records"], 1)

# --- section 3: measured operational cost (docs/DEMO.md Beat 4, 2026-07-23) ---
section3 = {
    "measured_date": "2026-07-23",
    "model": "openai/gpt-5.6-sol",
    "rates": {"input_per_m": 5, "cached_per_m": 0.50, "output_per_m": 30, "web_search_per_call": 0.01},
    "tokens": [
        {"arm": "baseline", "total": 995, "fresh_input": 710, "cached_input": 0, "output": 285},
        {"arm": "web search", "total": 18873, "fresh_input": 8399, "cached_input": 9678, "output": 744},
        {"arm": "Carver", "total": 5577, "fresh_input": 5000, "cached_input": 0, "output": 594},
    ],
    "cost_per_1k": [
        {"arm": "baseline", "warm": 12.70, "cold": 12.70, "answer": "4/5, no citations"},
        {"arm": "web search", "warm": 78.04, "cold": 121.59, "answer": "misses the state obligation"},
        {"arm": "Carver", "warm": 44.45, "cold": 44.45, "answer": "surfaces it"},
    ],
    "headline_pct_warm": 43,   # Carver vs web cache-warm
    "headline_pct_cold": 63,   # Carver vs web cold
    "latency": {"carver_s": 18, "web_s": 16, "note": "wash — applicant lookup dominates both; NOT a speed win"},
    "web_cost_is_floor": True,
}

# derived: cost per single check = cost_per_1k / 1000
section3["per_check_usd"] = [
    {"arm": r["arm"], "warm": round(r["warm"] / 1000, 4), "cold": round(r["cold"] / 1000, 4)}
    for r in section3["cost_per_1k"]
]

# fee-accounting asymmetry: the web arm's $78.04/$121.59 includes ~$10/1k of the
# hosted web-search tool fee; the Carver arm is model inference only (no Carver fee
# modeled). Headroom = how much Carver could charge per 1k queries and stay cheaper.
_web = next(r for r in section3["cost_per_1k"] if r["arm"] == "web search")
_carver = next(r for r in section3["cost_per_1k"] if r["arm"] == "Carver")
section3["fee_accounting"] = {
    "web_arm_includes_vendor_fee": True,
    "carver_arm_includes_vendor_fee": False,
    "headroom_per_1k_warm": round(_web["warm"] - _carver["warm"], 2),
    "headroom_per_1k_cold": round(_web["cold"] - _carver["cold"], 2),
    "note": "web arm cost includes the web-search tool fee (~$10/1k); Carver arm is inference only — headroom is the max Carver fee per 1k queries that keeps Carver cheaper",
}

# PROJECTED (not measured): replay economics if ~90% of the 5,000 fresh input tokens
# cache on a repeated run (4,500 cached / 500 fresh), output unchanged.
_r = section3["rates"]
_replay = (500 * _r["input_per_m"] + 4500 * _r["cached_per_m"] + 594 * _r["output_per_m"]) / 1e6
section3["replay_projection"] = {
    "status": "PROJECTED - not measured",
    "assumption": "~90% of the 5,000 fresh input tokens cache on replay (4,500 cached / 500 fresh); output 594 unchanged",
    "cost_per_1k": round(_replay * 1000, 2),
    "note": "web search re-fetches live on every replay; its cost does not decline with repetition",
}

# --- section 4: the lending exemplar (curated records) ---
section4 = {
    "applicants": [
        {"id": "CO-1001", "state": "Colorado", "extra_obligation": "Colorado AI Act (SB 24-205, amended by SB 26-189) — consumer notice after an AI/ADMT adverse decision"},
        {"id": "CA-1001", "state": "California", "extra_obligation": "Holden Act (California Housing Financial Discrimination Act) — Fair Lending Notice + statement of reasons"},
        {"id": "NY-1001", "state": "New York", "extra_obligation": None},
    ],
    "shared_facts": "Identical declined home-improvement loan, denied by an automated model; the applicant's state is the only variable and is supplied by the CRM lookup, never typed by the applicant.",
    "arms": [
        {"arm": "baseline (memory only)", "co_result": "MISS", "note": "recites federal adverse-action rules; never surfaces the state AI/lending obligation"},
        {"arm": "web search", "co_result": "MISS", "note": "searches generic adverse-action guidance; 0/5 on Colorado — never reformulates toward a state AI statute"},
        {"arm": "Carver", "co_result": "HIT", "note": "queries its obligation index with the situation (state + automated) and returns the state record"},
    ],
    "federal_baseline": ["Regulation B § 1002.9 (ECOA adverse-action notice)", "FCRA § 615 (consumer-report adverse-action notice)"],
}

# --- section 5: retrieval-level evidence (docs/DEMO.md) ---
section5 = {
    "haystack_size": 7146,
    "co_rank_situation_aware": 1,       # CO AI Act ranks #1 of 7,146 for a situation-aware query
    "co_rank_naive": ">6",              # not top-6 on the bare user words
    "web_co_hit_rate": "0/5",
    "ablation": "Drop the 4 curated records and re-run against the 7,142 real records alone: the Carver arm collapses to parity (MISS on CO and CA).",
    "state_tagged_examples": [          # from section1 jurisdictions_top — real state-level coverage in the corpus
        {"jur": "US-CA", "records": next((j["count"] for j in s1["jurisdictions_top"] if j["name"] == "US-CA"), None)},
        {"jur": "US-TX", "records": next((j["count"] for j in s1["jurisdictions_top"] if j["name"] == "US-TX"), None)},
        {"jur": "US-NY", "records": next((j["count"] for j in s1["jurisdictions_top"] if j["name"] == "US-NY"), None)},
    ],
    "class_definition": "Silent-trigger queries: an actor attribute (jurisdiction, decision method, role) fires an unnamed obligation the user never mentions. Web search must first suspect the obligation exists to search for it, and fails at that step silently; a situation-queried obligation index returns it because it is tagged to the situation.",
}

section5["replay"] = {
    "snapshot_pinned": s1["snapshot_date"],
    "web_5run_note": "web search missed the Colorado obligation in all five runs - it searched generically ('adverse action', 'loan denial') and never reformulated toward a state AI statute; a consistent miss, not run-to-run noise. Live web retrieval is unversioned and cannot be pinned.",
    "drift_note": "PROJECTED workflow: regulatory drift detection = diff between dataset snapshots; not a measured capability",
}

out = {
    "snapshot_date": s1["snapshot_date"],
    "section1": {
        **{k: s1[k] for k in ["total_records", "distinct_entities", "entity_mentions",
                              "distinct_tags", "tag_mentions", "classified_records",
                              "sectors_by_taxonomy_top", "jurisdictions_top",
                              "distinct_jurisdictions", "intelligence_layer"]},
        "freshness": fresh,
        "recent_2y_count": recent_2y,
        "recent_2y_share_pct": recent_share,
    },
    "section2": {k: s2[k] for k in ["documents_analyzed", "tokens_per_doc_estimate",
                                    "estimated_source_read_tokens", "obligations_extracted",
                                    "reg_references_resolved", "records_with_critical_dates",
                                    "records_with_penalties", "penalty_records_with_parseable_amount",
                                    "penalty_money_mentions", "obligations_by_sector", "notes"]},
    "section3": section3,
    "section4": section4,
    "section5": section5,
}
json.dump(out, open(os.path.join(BASE, "whitepaper-data.json"), "w"), indent=2)
print("wrote whitepaper-data.json; recent 2y share =", recent_share, "%")
