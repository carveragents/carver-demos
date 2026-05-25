"""Thesis decomposition for a γ contract.

One LLM call per contract: breaks resolution criteria into 1-3 atomic
conditions. Cached by contract id (stable across runs).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from build import _llm

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "conditions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "enum": ["A", "B", "C"]},
                    "label": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["id", "label", "summary"],
            },
        },
    },
    "required": ["conditions"],
}

_SYSTEM = (
    "You are a regulatory analyst. Decompose a prediction-market contract's "
    "resolution criteria into 1-3 atomic conditions. Each condition should "
    "describe one independent path by which the contract can resolve YES. "
    "Return JSON matching the provided schema; labels ≤ 40 chars; summaries "
    "≤ 200 chars."
)


def decompose(
    *,
    contract_id: str,
    title: str,
    resolution_criteria: str,
    settlement_entities: list[str],
    cache_root: Path | None = None,
) -> list[dict[str, str]]:
    """Return list of condition dicts {id, label, summary}.

    Falls back to a single 'A: Resolution criteria' condition when LLM is
    unavailable AND cache misses.
    """
    user = (
        f"Title: {title}\n"
        f"Resolution criteria: {resolution_criteria}\n"
        f"Settlement entities: {settlement_entities}"
    )
    response = _llm.complete_json(
        purpose="thesis",
        cache_key=contract_id,
        model=_llm.MODEL_DEEP,
        system=_SYSTEM,
        user=user,
        schema=_SCHEMA,
        cache_root=cache_root,
    )
    if response is None:
        return [{
            "id": "A",
            "label": "Resolution criteria",
            "summary": resolution_criteria[:200],
        }]
    return cast(list[dict[str, str]], response["conditions"])
