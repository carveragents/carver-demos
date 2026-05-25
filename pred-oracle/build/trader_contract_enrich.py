"""Trader contract slice enrichment orchestrator.

Mirrors gamma_contract_enrich.py but adds trader-specific fields to timeline
events: direction, magnitude, timeline_shift (from extended relevance schema)
and mechanism (from _mechanism.py).
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import (  # noqa: E402
    _fields,
    _heat,
    _heat_panel,
    _llm,
    _mechanism,
    _narrative,
    _relevance,
    _thesis,
)


def enrich_slice(
    *,
    slice_doc: dict[str, Any],
    corpus: list[dict[str, Any]],
    peer_heats: list[float],
    today: date,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    contract = slice_doc["contract"]
    cid = contract["id"]
    settle = [e["name"] for e in contract.get("settlement_entities") or []]

    # 1. Thesis decomposition (1 LLM call, cached by contract id).
    conditions = _thesis.decompose(
        contract_id=cid,
        title=contract.get("title", ""),
        resolution_criteria=contract.get("resolution_criteria", ""),
        settlement_entities=settle,
        cache_root=cache_root,
    )
    contract["conditions"] = conditions

    # 2. Per-record relevance — pass the already-windowed timeline as candidates.
    contract_for_llm: dict[str, Any] = {
        "id": cid,
        "title": contract.get("title", ""),
        "resolution_criteria": contract.get("resolution_criteria", ""),
        "settlement_entities": settle,
    }
    candidates = _hydrate_candidates(slice_doc.get("timeline") or [], corpus)
    judged = _relevance.judge_batch(
        contract=contract_for_llm, conditions=conditions, candidates=candidates,
        cache_root=cache_root,
    )
    slice_doc["timeline"] = _project_timeline_fields(judged)

    # 3. Heat panel (uses judged records for sparkline + explainer).
    heat_7d_ago = _heat.heat_score(
        {"settlement_entities": settle}, corpus, today=today - timedelta(days=7),
    )
    slice_doc["heat_panel"] = _heat_panel.build(
        contract_id=cid,
        heat_value=float(contract.get("heat", 0.0)),
        heat_value_7d_ago=heat_7d_ago,
        peers=peer_heats,
        records=judged,
        today=today,
        cache_root=cache_root,
    )

    # 4. Narrative (uses judged timeline so the LLM sees one_line_why context).
    contract["narrative"] = _narrative.summarize(
        contract=contract, timeline=slice_doc["timeline"], cache_root=cache_root,
    )

    return slice_doc


def _hydrate_candidates(
    timeline: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Look up each timeline entry's original corpus record by feed_entry_id."""
    by_id = {r.get("feed_entry_id"): r for r in corpus if r.get("feed_entry_id")}
    out: list[dict[str, Any]] = []
    for ev in timeline:
        rec = by_id.get(ev.get("carver_feed_entry_id"))
        if rec:
            out.append(rec)
    return out


def _project_timeline_fields(judged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map judged corpus records back to the timeline event shape.

    Extends the gamma shape with trader-specific fields:
    - direction / magnitude / timeline_shift from the extended relevance schema
    - mechanism from _mechanism.classify(update_type)
    """
    out: list[dict[str, Any]] = []
    for rec in judged:
        out.append({
            "pub_date": _fields.pub_date_iso(rec),
            "title": rec.get("title") or "",
            "regulator": _fields.regulator_display(rec),
            "url": rec.get("link") or "",
            "urgency": _fields.urgency_score(rec),
            "impact": _fields.impact_score(rec),
            "matched_entity": rec.get("matched_entity", ""),
            "carver_feed_entry_id": rec.get("feed_entry_id") or "",
            "one_line_why": rec.get("one_line_why", ""),
            "condition_tag": rec.get("condition_tag", "background"),
            "relevance_score": rec.get("relevance_score", 0),
            "high_impact": rec.get("high_impact", False),
            # Trader-specific extensions
            "direction": rec.get("direction", "neutral"),
            "magnitude": rec.get("magnitude", "low"),
            "timeline_shift": rec.get("timeline_shift", "none"),
            "mechanism": _mechanism.classify(rec.get("update_type", "")),
            "effective_date": (rec.get("critical_dates") or {}).get("effective_date", ""),
            "comment_deadline": (rec.get("critical_dates") or {}).get("comment_deadline", ""),
        })
    return out


def enrich_all(
    *,
    slice_dir: Path,
    corpus: list[dict[str, Any]],
    peer_heats: list[float],
    today: date,
    cache_root: Path | None = None,
    max_workers: int = 4,
) -> list[Path]:
    """Enrich every slice JSON under slice_dir in parallel."""
    slice_paths = sorted(slice_dir.glob("*.json"))

    def _process(p: Path) -> Path:
        doc = json.loads(p.read_text())
        enriched = enrich_slice(
            slice_doc=doc, corpus=corpus, peer_heats=peer_heats,
            today=today, cache_root=cache_root,
        )
        p.write_text(json.dumps(enriched, indent=2))
        return p

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(_process, slice_paths))


if __name__ == "__main__":
    print(f"is_available: {_llm.is_available()}")
