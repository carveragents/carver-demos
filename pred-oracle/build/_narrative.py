"""2-3 sentence storyline summary of a contract's enriched timeline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from build import _llm

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}

_SYSTEM = (
    "You are a regulatory analyst. Write a 2-3 sentence storyline summary "
    "(≤500 chars total) of the regulatory pressure history for this "
    "prediction-market contract. For 'retrospective' kind, write past tense "
    "and reference the actual resolution. For 'active' kind, write present "
    "tense and note what's still pending. Return JSON {text: ...}."
)


def _timeline_hash(timeline: list[dict[str, Any]]) -> str:
    payload = json.dumps([
        {"d": ev.get("pub_date", ""), "t": ev.get("title", ""),
         "c": ev.get("condition_tag", "")}
        for ev in timeline
    ], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def summarize(
    *,
    contract: dict[str, Any],
    timeline: list[dict[str, Any]],
    cache_root: Path | None = None,
) -> str:
    """Return narrative text. Empty string if LLM unavailable + cache miss."""
    if not timeline:
        return ""
    h = _timeline_hash(timeline)
    resolution = contract.get("resolution_outcome", "")
    resolution_line = f"Resolution: {resolution}\n" if resolution else ""
    user = (
        f"Contract: {contract.get('title', '')}\n"
        f"Kind: {contract.get('kind', '')}\n"
        f"{resolution_line}"
        f"Timeline ({len(timeline)} events):\n"
        + "".join(
            f"- {ev.get('pub_date', '')} [{ev.get('condition_tag', '?')}] "
            f"{ev.get('title', '')} — {ev.get('one_line_why', '')}\n"
            for ev in timeline
        )
    )
    response = _llm.complete_json(
        purpose="narrative",
        cache_key=f"{contract['id']}__{h}",
        model=_llm.MODEL_DEEP,
        system=_SYSTEM,
        user=user,
        schema=_SCHEMA,
        cache_root=cache_root,
    )
    if response is None:
        return ""
    return str(response.get("text", ""))
