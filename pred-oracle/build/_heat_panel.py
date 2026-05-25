"""Heat tier vocabulary, peer percentile, urgency-weighted sparkline.

Pure computation; LLM-backed explainer will be added in Task 8.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from build import _fields, _llm

Tier = Literal["dormant", "watch", "active", "critical"]

_TIER_THRESHOLDS: list[tuple[float, Tier]] = [
    (70.0, "critical"),
    (30.0, "active"),
    (10.0, "watch"),
    (0.0, "dormant"),
]


def tier_for(value: float) -> Tier:
    """Map a heat score to one of dormant/watch/active/critical."""
    for threshold, tier in _TIER_THRESHOLDS:
        if value >= threshold:
            return tier
    return "dormant"


def peer_percentile(value: float, peers: list[float]) -> int:
    """Percentile rank (0-100) of `value` against `peers` (inclusive count).

    Returns 0 when peers is empty.
    """
    if not peers:
        return 0
    leq = sum(1 for p in peers if p <= value)
    return round(100 * leq / len(peers))


def urgency_weighted_sparkline(
    records: list[dict[str, Any]], *, today: date, days: int = 14,
) -> list[int]:
    """Sum of urgency per day for the past `days` (oldest first).

    Each record contributes its urgency score to the bucket of its pub_date.
    """
    buckets = [0] * days
    for rec in records:
        age = _fields.pub_date_age_days(rec, today=today)
        if age is None or age < 0 or age >= days:
            continue
        urgency = _fields.urgency_score(rec)
        buckets[days - 1 - age] += int(urgency)
    return buckets


# --- LLM explainer + orchestrator ---


_EXPLAINER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "primary_drivers": {
            "type": "array",
            "minItems": 1, "maxItems": 3,
            "items": {"type": "string"},
        },
        "explainer": {"type": "string"},
    },
    "required": ["primary_drivers", "explainer"],
}

_EXPLAINER_SYSTEM = (
    "You are a regulatory analyst. Given a contract's heat tier and its top "
    "recent matching records, write a one-sentence (≤220 char) explanation "
    "of what is driving heat at this level this week. Also list 1-3 short "
    "primary drivers (≤120 chars each). Return JSON matching the schema."
)


def _week_key(today: date) -> str:
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}W{iso_week:02d}"


def build(
    *,
    contract_id: str,
    heat_value: float,
    heat_value_7d_ago: float,
    peers: list[float],
    records: list[dict[str, Any]],
    today: date,
    cache_root: Path | None = None,
) -> dict[str, Any]:
    """Assemble a heat_panel dict for the contract page + dashboard tier."""
    tier_label = tier_for(heat_value)
    delta_7d = round(heat_value - heat_value_7d_ago, 2)
    percentile = peer_percentile(heat_value, peers)
    sparkline = urgency_weighted_sparkline(records, today=today, days=14)

    top_for_explainer = sorted(
        records, key=lambda r: _fields.pub_date_iso(r), reverse=True,
    )[:10]
    user = (
        f"Tier: {tier_label}\n"
        f"Heat: {heat_value}\n"
        f"Delta_7d: {delta_7d}\n"
        f"Top records:\n"
        + "".join(
            f"- {_fields.pub_date_iso(r)} {r.get('title', '')[:80]}\n"
            for r in top_for_explainer
        )
    )
    week_key = _week_key(today)
    response = _llm.complete_json(
        purpose="heat_explainer",
        cache_key=f"{contract_id}__{week_key}",
        model=_llm.MODEL_FAST,
        system=_EXPLAINER_SYSTEM,
        user=user,
        schema=_EXPLAINER_SCHEMA,
        cache_root=cache_root,
    )
    if response is None:
        response = {
            "primary_drivers": [f"{len(records)} matching events in window"],
            "explainer": (
                f"Heat reflects {len(records)} matching events in the last "
                f"{14 if records else 90} days."
            ),
        }

    return {
        "value": heat_value,
        "tier": tier_label,
        "delta_7d": delta_7d,
        "peer_percentile": percentile,
        "urgency_weighted_sparkline": sparkline,
        "primary_drivers": response["primary_drivers"],
        "explainer": response["explainer"],
    }
