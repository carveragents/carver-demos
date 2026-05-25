"""α scene wow-score + inbox-eligibility predicates.

Scoring formula and exclusion rules are documented in:
- docs/specs/STAGE_1_NOTES.md §5 (filter rules)
- data/a8-prime-wow-summary.md (ranking heuristic)

Centralized here so changes touch one place.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from build._fields import (
    impact_score,
    pub_date_age_days,
    relevance_score,
    urgency_score,
)

EXCLUDED_UPDATE_TYPES: frozenset[str] = frozenset({"website error", "other"})
MIN_RELEVANCE: float = 5.0

_PM_NAMES: tuple[str, ...] = (
    "kalshi", "polymarket", "forecastex", "predictit", "electronx", "railbird",
    "fanduel", "draftkings", "event contract", "prediction market", "sportsbook",
    "sweepstakes casino", "binary option",
)

_UPDATE_TYPE_WEIGHTS: dict[str, float] = {
    "enforcement": 10.0,
    "final rule": 10.0,
    "advisory": 8.0,
    "proposed rule": 8.0,
    "comment request": 6.0,
    "guidance": 6.0,
    "bulletin": 4.0,
    "event announcement": 4.0,
    "press release": 2.0,
    "speech": 2.0,
    "trend report": 2.0,
    "newsletter": 2.0,
    "insights": 2.0,
}


def is_inbox_eligible(
    rec: dict[str, Any],
    today: date | None = None,
    max_age_days: int = 90,
) -> bool:
    """Return True if a record passes the α-inbox hard filter."""
    if rec.get("update_type") in EXCLUDED_UPDATE_TYPES:
        return False
    if relevance_score(rec) < MIN_RELEVANCE:
        return False
    if not (rec.get("title") or "").strip():
        return False
    if not (rec.get("link") or "").strip():
        return False
    if not rec.get("pub_date_valid"):
        return False
    age = pub_date_age_days(rec, today=today)
    if age is None or age > max_age_days or age < 0:
        return False
    return True


def _recency_score(age_days: int | None) -> float:
    if age_days is None:
        return 0.0
    if age_days <= 7:
        return 10.0
    if age_days <= 30:
        return 8.0
    if age_days <= 60:
        return 5.0
    if age_days <= 90:
        return 2.0
    return 0.0


def _update_type_score(update_type: str) -> float:
    return _UPDATE_TYPE_WEIGHTS.get(update_type, 0.0)


def _jurisdiction_score(rec: dict[str, Any]) -> float:
    code = (rec.get("topic_jurisdiction_code") or "").strip()
    if code.startswith("US-"):
        return 10.0
    if code == "US":
        return 8.0
    tier = (rec.get("jurisdiction_tier") or {}).get("label") or ""
    if tier == "international":
        return 4.0
    return 0.0


def _recognition_score(rec: dict[str, Any]) -> float:
    haystack = " ".join([
        rec.get("title") or "",
        rec.get("regulator_name") or "",
        *(rec.get("entities") or []),
        *(rec.get("tags") or []),
    ]).lower()
    for name in _PM_NAMES:
        if name in haystack:
            return 10.0
    return 0.0


def wow_score(rec: dict[str, Any], today: date | None = None) -> float:
    """Compute a 0-10ish ranking score per docs/specs/STAGE_1_NOTES §7.

    Weighted blend of urgency, impact, recency, update-type, jurisdiction,
    recognition. Higher = better wow candidate.
    """
    age = pub_date_age_days(rec, today=today)
    return round(
        0.30 * urgency_score(rec)
        + 0.20 * impact_score(rec)
        + 0.15 * _recency_score(age)
        + 0.15 * _update_type_score(rec.get("update_type") or "")
        + 0.10 * _jurisdiction_score(rec)
        + 0.10 * _recognition_score(rec),
        4,
    )
