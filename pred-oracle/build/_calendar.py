"""Calendar data extraction for the trader dashboard."""
from __future__ import annotations
import calendar as _cal
from datetime import date
from typing import Any


def extract_calendar_events(
    slice_docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for doc in slice_docs:
        cid = doc["contract"]["id"]
        ctitle = doc["contract"].get("title", "")
        platform = doc["contract"].get("platform", "")

        expires = doc["contract"].get("expires_at", "")
        if expires:
            events.append({
                "calendar_date": expires[:10],
                "type": "settlement",
                "title": f"Settlement: {ctitle}",
                "contract_id": cid,
                "platform": platform,
                "color": "blue",
            })

        for ev in doc.get("timeline", []):
            for field, etype, color in [
                ("effective_date", "effective_date", "purple"),
                ("comment_deadline", "comment_deadline", "green"),
            ]:
                dt = ev.get(field, "")
                if dt:
                    events.append({
                        "calendar_date": dt[:10],
                        "type": etype,
                        "title": ev.get("title", ""),
                        "contract_id": cid,
                        "platform": platform,
                        "color": color,
                        "direction": ev.get("direction", "neutral"),
                        "magnitude": ev.get("magnitude", "low"),
                    })

            pub = ev.get("pub_date", "")
            if pub:
                is_high = ev.get("high_impact", False)
                events.append({
                    "calendar_date": pub[:10],
                    "type": "regulatory_event",
                    "title": ev.get("title", ""),
                    "contract_id": cid,
                    "platform": platform,
                    "color": "red" if is_high else "amber",
                    "direction": ev.get("direction", "neutral"),
                    "magnitude": ev.get("magnitude", "low"),
                    "high_impact": is_high,
                    "relevance_score": ev.get("relevance_score", 0),
                })
    return events


def calendar_month(
    year: int, month: int, events: list[dict[str, Any]],
) -> dict[str, Any]:
    weeks: list[list[dict[str, Any] | None]] = []
    cal = _cal.Calendar(firstweekday=6)
    for week in cal.monthdayscalendar(year, month):
        week_data: list[dict[str, Any] | None] = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                iso = f"{year:04d}-{month:02d}-{day:02d}"
                day_events = [e for e in events if e["calendar_date"] == iso]
                week_data.append({
                    "day": day,
                    "date": iso,
                    "events": day_events,
                    "busy": len(day_events) >= 3,
                })
        weeks.append(week_data)
    return {"year": year, "month": month, "weeks": weeks}
