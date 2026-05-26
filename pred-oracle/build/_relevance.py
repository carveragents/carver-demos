"""Per-record relevance judgment via LLM.

For each candidate record (already entity-matched), ask the model whether
the record is relevant to the contract resolving YES/NO. Drop irrelevant,
tag each survivor with a condition_tag and a one_line_why. Sort by
relevance_score × urgency, keep top 20.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from build import _fields, _llm

SYSTEM_PROMPT = (
    "You are a regulatory analyst. Given a prediction-market contract and a "
    "single regulatory news record, decide if this record is relevant to "
    "whether the contract resolves YES or NO. Score relevance 0-10 (0 = "
    "off-topic, 10 = directly determinative). Return JSON matching the "
    "schema. one_line_why should be ≤160 chars and explain how this record "
    "moves resolution probability."
    " Also judge directionality: does this event make YES resolution more likely (bullish), less likely (bearish), or neither (neutral)? Judge magnitude: high = materially changes probability, medium = notable but not decisive, low = incremental signal. Judge timeline shift: does this event suggest resolution will come sooner or later than expected, or no change (none)?"
)


def build_user_prompt(
    contract: dict[str, Any],
    conditions: list[dict[str, str]],
    rec: dict[str, Any],
) -> str:
    return (
        f"Contract title: {contract.get('title', '')}\n"
        f"Resolution criteria: {contract.get('resolution_criteria', '')}\n"
        f"Conditions:\n"
        + "".join(f"  {c['id']}: {c['label']} — {c['summary']}\n" for c in conditions)
        + f"Settlement entities: {contract.get('settlement_entities', [])}\n\n"
        f"Record title: {rec.get('title', '')}\n"
        f"Record date: {_fields.pub_date_iso(rec)}\n"
        f"Record regulator: {_fields.regulator_display(rec)}\n"
        f"Record topic: {rec.get('topic_name', '')}\n"
        f"Record entities: {rec.get('entities', [])}"
    )


def build_schema(conditions: list[dict[str, str]]) -> dict[str, Any]:
    condition_ids = [c["id"] for c in conditions]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "relevant": {"type": "boolean"},
            "relevance_score": {"type": "integer", "minimum": 0, "maximum": 10},
            "one_line_why": {"type": "string"},
            "condition_tag": {"type": "string", "enum": condition_ids + ["background"]},
            "high_impact": {"type": "boolean"},
            "direction": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
            },
            "magnitude": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "timeline_shift": {
                "type": "string",
                "enum": ["sooner", "later", "none"],
            },
        },
        "required": ["relevant", "relevance_score", "one_line_why",
                     "condition_tag", "high_impact",
                     "direction", "magnitude", "timeline_shift"],
    }


def _heuristic_judgment(rec: dict[str, Any]) -> dict[str, Any]:
    topic = (rec.get("topic_name") or "").strip()
    entities = rec.get("entities") or []
    matched = entities[0] if entities else ""
    parts = [p for p in (matched, topic) if p]
    why = " — ".join(parts) if parts else "Entity match"
    return {
        "relevant": True,
        "relevance_score": int(_fields.urgency_score(rec)),
        "one_line_why": why,
        "condition_tag": "background",
        "high_impact": _fields.urgency_score(rec) >= 7,
        "direction": "neutral",
        "magnitude": "low",
        "timeline_shift": "none",
    }


def judge_batch(
    *,
    contract: dict[str, Any],
    conditions: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    cache_root: Path | None = None,
    top_n: int = 20,
    min_results: int = 5,
) -> list[dict[str, Any]]:
    """Score each candidate; drop irrelevant; sort by score × urgency; trim to top_n.

    Soft fallback: if fewer than `min_results` records survive the LLM's
    `relevant: True` filter, top up from the dropped pool — sorted by the
    LLM's `relevance_score` desc — and tag them `background`. This handles
    contracts whose corpus coverage is sparse so the demo timeline is never
    empty when entity matches exist.
    """
    schema = build_schema(conditions)
    relevant: list[dict[str, Any]] = []
    background_pool: list[dict[str, Any]] = []
    for rec in candidates:
        user = build_user_prompt(contract, conditions, rec)
        key = _llm.cache_key_for(
            model=_llm.MODEL_FAST, system=SYSTEM_PROMPT, user=user, schema=schema,
        )
        verdict = _llm.complete_json(
            purpose="relevance", cache_key=key, model=_llm.MODEL_FAST,
            system=SYSTEM_PROMPT, user=user, schema=schema, cache_root=cache_root,
        )
        if verdict is None:
            verdict = _heuristic_judgment(rec)
        enriched = {
            **rec,
            "one_line_why": verdict.get("one_line_why") or "",
            "condition_tag": verdict.get("condition_tag", "background"),
            "relevance_score": int(verdict.get("relevance_score", 0)),
            "high_impact": bool(verdict.get("high_impact", False)),
            "direction": verdict.get("direction", "neutral"),
            "magnitude": verdict.get("magnitude", "low"),
            "timeline_shift": verdict.get("timeline_shift", "none"),
        }
        if verdict.get("relevant"):
            relevant.append(enriched)
        else:
            # Force background tag + heuristic one_line_why for fallback path.
            enriched["condition_tag"] = "background"
            if not enriched["one_line_why"]:
                enriched["one_line_why"] = _heuristic_judgment(rec)["one_line_why"]
            background_pool.append(enriched)

    def _rank(r: dict[str, Any]) -> float:
        return float(r["relevance_score"]) * float(_fields.urgency_score(r))

    relevant.sort(key=_rank, reverse=True)
    relevant = relevant[:top_n]

    if len(relevant) < min_results and background_pool:
        background_pool.sort(key=_rank, reverse=True)
        need = min_results - len(relevant)
        relevant = relevant + background_pool[:need]

    relevant.sort(key=lambda r: _fields.pub_date_iso(r), reverse=True)
    return relevant
