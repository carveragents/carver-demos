"""Field extractors for the Stage 1 artifact schema.

Each artifact in data/_scratch/artifacts.jsonl is normalized by
build/pull_artifacts.py into a flat record. These helpers read the
canonical fields with safe defaults, hiding the nested score / dict shapes
from the slice generators that depend on them.

See docs/specs/STAGE_1_NOTES.md §4 for the canonical schema.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

_URGENCY_BUCKETS = (
    (8.0, "critical"),
    (6.5, "high"),
    (4.0, "medium"),
)


def _score(rec: dict[str, Any], dimension: str) -> float:
    """Return the numeric score for urgency/impact/relevance, default 0.0."""
    scores = rec.get("scores") or {}
    bucket = scores.get(dimension) or {}
    val = bucket.get("score")
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def urgency_score(rec: dict[str, Any]) -> float:
    return _score(rec, "urgency")


def impact_score(rec: dict[str, Any]) -> float:
    return _score(rec, "impact")


def relevance_score(rec: dict[str, Any]) -> float:
    return _score(rec, "relevance")


def pub_date_iso(rec: dict[str, Any]) -> str:
    """Return ISO date string (YYYY-MM-DD) or empty string."""
    if not rec.get("pub_date_valid"):
        return ""
    raw = rec.get("pub_date") or ""
    return str(raw)[:10] if raw else ""


def pub_date_age_days(rec: dict[str, Any], today: date | None = None) -> int | None:
    """Return age in days from `today`, or None if pub_date is invalid/empty.

    `today` defaults to the current date; pass an explicit value for testing.
    """
    iso = pub_date_iso(rec)
    if not iso:
        return None
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    if today is None:
        today = date.today()
    return (today - d).days


def jurisdictions(rec: dict[str, Any]) -> list[str]:
    """Return the impacted-business jurisdiction list, or []."""
    ib = rec.get("impacted_business") or {}
    j = ib.get("jurisdiction") or []
    return [str(x) for x in j if x]


def us_states(rec: dict[str, Any]) -> list[str]:
    """Return only US-state codes (US-XX) from the jurisdictions list."""
    return [j for j in jurisdictions(rec) if j.startswith("US-") and len(j) == 5]


def regulator_display(rec: dict[str, Any]) -> str:
    """Return the regulator name suitable for display.

    Composition rule: `<regulator_name> — <division>` if both set;
    otherwise just `<regulator_name>`; otherwise `<topic_name>` fallback.
    """
    name = (rec.get("regulator_name") or "").strip()
    division = (rec.get("regulator_division") or "").strip()
    if name and division:
        return f"{name} — {division}"
    if name:
        return name
    return (rec.get("topic_name") or "").strip()


def urgency_tier(score: float) -> str:
    """Bucket a 0-10 urgency score into low/medium/high/critical."""
    for threshold, label in _URGENCY_BUCKETS:
        if score >= threshold:
            return label
    return "low"
