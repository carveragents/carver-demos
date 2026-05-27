"""One-shot enrichment script for the 5 new trader demo contracts.

Pre-filters candidates to top 60 by urgency to cap LLM calls per contract.
Run from pred-oracle/ directory:
    python3 build/_enrich_new_contracts.py
"""
from __future__ import annotations
import json, sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build import _relevance, _thesis, _heat, _heat_panel, _narrative, _fields
from build.trader_contract_enrich import (
    _hydrate_candidates, _project_timeline_fields, _annotate_conditions,
)

REPO = Path(__file__).resolve().parent.parent
CORPUS_PATH = REPO / "data/_scratch/artifacts.jsonl"
OUT_DIR = REPO / "build/page_data/trader/contracts"
CACHE_ROOT = REPO / "build/_cache"
TODAY = date(2026, 5, 26)
MAX_CANDIDATES = 60

NEW_IDS = [
    "clarity-act-2026",
    "cannabis-dea-rescheduling-2026",
    "nrc-nuclear-reactor-2026",
    "fda-retatrutide-2026",
    "scotus-ftc-independence-2026",
]


def main() -> None:
    print(f"Loading corpus from {CORPUS_PATH}...")
    corpus: list[dict] = []
    with CORPUS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                corpus.append(json.loads(line))
    print(f"Corpus: {len(corpus)} records")

    peer_heats = [
        json.loads(p.read_text()).get("contract", {}).get("heat", 0)
        for p in OUT_DIR.glob("*.json")
    ]

    for cid in NEW_IDS:
        p = OUT_DIR / f"{cid}.json"
        slice_doc = json.loads(p.read_text())
        contract = slice_doc["contract"]
        settle = [e["name"] for e in contract.get("settlement_entities") or []]

        print(f"\n=== {cid} ===")

        # Thesis decomposition
        conditions = _thesis.decompose(
            contract_id=cid,
            title=contract.get("title", ""),
            resolution_criteria=contract.get("resolution_criteria", ""),
            settlement_entities=settle,
            cache_root=CACHE_ROOT,
        )
        contract["conditions"] = conditions
        print(f"  Conditions: {len(conditions)}")

        # Hydrate candidates and pre-filter
        contract_for_llm = {
            "id": cid, "title": contract.get("title", ""),
            "resolution_criteria": contract.get("resolution_criteria", ""),
            "settlement_entities": settle,
        }
        candidates = _hydrate_candidates(slice_doc.get("timeline") or [], corpus)
        print(f"  Candidates: {len(candidates)} -> capping at {MAX_CANDIDATES}")
        candidates.sort(key=lambda r: float(_fields.urgency_score(r)), reverse=True)
        candidates = candidates[:MAX_CANDIDATES]

        # LLM relevance scoring
        judged = _relevance.judge_batch(
            contract=contract_for_llm, conditions=conditions, candidates=candidates,
            cache_root=CACHE_ROOT,
        )
        slice_doc["timeline"] = _project_timeline_fields(judged)
        contract["conditions"] = _annotate_conditions(conditions, slice_doc["timeline"])
        print(f"  Timeline: {len(slice_doc['timeline'])} events")

        # Heat panel
        heat_7d_ago = _heat.heat_score(
            {"settlement_entities": settle}, corpus, today=TODAY - timedelta(days=7),
        )
        slice_doc["heat_panel"] = _heat_panel.build(
            contract_id=cid,
            heat_value=float(contract.get("heat", 0.0)),
            heat_value_7d_ago=heat_7d_ago,
            peers=peer_heats,
            records=judged,
            today=TODAY,
            cache_root=CACHE_ROOT,
        )

        # Narrative
        contract["narrative"] = _narrative.summarize(
            contract=contract, timeline=slice_doc["timeline"], cache_root=CACHE_ROOT,
        )
        print(f"  Narrative: {'yes' if contract.get('narrative') else 'no'}")

        p.write_text(json.dumps(slice_doc, indent=2))
        print(f"  Written: {p}")

    print("\nAll done.")


if __name__ == "__main__":
    main()
