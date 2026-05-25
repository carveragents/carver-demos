"""Portfolio-level aggregation for the trader dashboard."""
from __future__ import annotations
from datetime import date, timedelta
from typing import Any


def net_direction(
    events: list[dict[str, Any]], *, window_days: int = 30, today: str = "",
) -> str:
    if not today:
        today = date.today().isoformat()
    cutoff = (date.fromisoformat(today) - timedelta(days=window_days)).isoformat()
    recent = [e for e in events if e.get("pub_date", "") >= cutoff]
    bullish = sum(1 for e in recent if e.get("direction") == "bullish")
    bearish = sum(1 for e in recent if e.get("direction") == "bearish")
    if bullish == 0 and bearish == 0:
        return "Mixed"
    if bullish > bearish * 1.5:
        return "Bullish"
    if bearish > bullish * 1.5:
        return "Bearish"
    return "Mixed"


def _next_catalyst(timeline: list[dict[str, Any]], today: str) -> dict[str, Any] | None:
    candidates = []
    for ev in timeline:
        for field in ("effective_date", "comment_deadline"):
            dt = ev.get(field, "")
            if dt and dt > today:
                candidates.append({"date": dt, "field": field, "title": ev.get("title", "")})
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["date"])
    return candidates[0]


def portfolio_row(slice_doc: dict[str, Any], *, today: str = "") -> dict[str, Any]:
    if not today:
        today = date.today().isoformat()
    contract = slice_doc["contract"]
    timeline = slice_doc.get("timeline", [])
    heat_panel = slice_doc.get("heat_panel", {})
    position = slice_doc.get("position", {})

    latest = timeline[0] if timeline else None
    catalyst = _next_catalyst(timeline, today)
    event_count = len(timeline)

    return {
        "contract_id": contract["id"],
        "platform": contract.get("platform", ""),
        "title": contract.get("title", ""),
        "kind": contract.get("kind", "active"),
        "expires_at": contract.get("expires_at", ""),
        "heat_value": heat_panel.get("value", 0),
        "heat_tier": heat_panel.get("tier", "dormant"),
        "heat_delta_7d": heat_panel.get("delta_7d", 0),
        "peer_percentile": heat_panel.get("peer_percentile", 0),
        "net_direction": net_direction(timeline, today=today),
        "event_count_90d": event_count,
        "next_catalyst": catalyst,
        "latest_event": {
            "pub_date": latest.get("pub_date", ""),
            "title": latest.get("title", ""),
            "direction": latest.get("direction", "neutral"),
            "magnitude": latest.get("magnitude", "low"),
        } if latest else None,
        "position": position,
        "detail_href": f"contracts/{contract['id']}/",
    }


def build_portfolio(
    slice_docs: list[dict[str, Any]], *, today: str = "",
) -> list[dict[str, Any]]:
    active = [doc for doc in slice_docs if doc.get("contract", {}).get("kind") != "retrospective"]
    rows = [portfolio_row(doc, today=today) for doc in active]
    rows.sort(key=lambda r: r["heat_value"], reverse=True)
    return rows
