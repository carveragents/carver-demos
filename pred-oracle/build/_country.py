"""Per-country aggregation for β heat-map, cascades, and quarterly report.

Aggregation key:
  - Prefer record.topic_jurisdiction_code (Carver-catalog code) when present.
  - Fall back to first record.impacted_business.jurisdiction entry otherwise.
  - For world_only callers (the world map), drop US-XX subdivisions; they
    belong to the US-states inset.

Pressure score:
  pressure = min(100, count * avg_urgency / 5)
  (normalised so a country with 100 records at avg_urgency 5 sits at 100;
   the divisor is tunable.)
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields  # noqa: E402

PRESSURE_DIVISOR: float = 5.0

# Accept ISO-2 country codes ("US", "FR"), the EU bloc, or subdivision codes
# ("US-CA", "CA-ON"). Anything else (free-form strings, dashes, descriptive
# labels the corpus sometimes carries) is rejected.
_ISO2_RE = re.compile(r"^[A-Z]{2}$")
_SUBDIVISION_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")


def country_code(rec: dict[str, Any], world_only: bool = False) -> str | None:
    """Return the country/jurisdiction code for a record."""
    code = (rec.get("topic_jurisdiction_code") or "").strip()
    if not code:
        jur = (rec.get("impacted_business") or {}).get("jurisdiction") or []
        if jur:
            code = str(jur[0]).strip()
    if not code:
        return None
    is_iso2 = _ISO2_RE.match(code) is not None or code == "EU"
    is_subdivision = _SUBDIVISION_RE.match(code) is not None
    if not (is_iso2 or is_subdivision):
        return None
    if world_only and is_subdivision:
        return None
    return code


def aggregate(
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    window_days: int = 90,
    world_only: bool = False,
) -> dict[str, dict[str, float]]:
    """Return per-country aggregates in the given window.

    For each country code:
      count        — number of records.
      sum_urgency  — sum of urgency scores.
      avg_urgency  — sum_urgency / count.
      max_urgency  — max urgency.
    """
    today = today or date.today()
    out: dict[str, dict[str, float]] = {}
    for r in records:
        code = country_code(r, world_only=world_only)
        if code is None:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age > window_days:
            continue
        u = _fields.urgency_score(r)
        slot = out.setdefault(code, {"count": 0.0, "sum_urgency": 0.0, "max_urgency": 0.0})
        slot["count"] += 1
        slot["sum_urgency"] += u
        if u > slot["max_urgency"]:
            slot["max_urgency"] = u
    for slot in out.values():
        if slot["count"]:
            slot["avg_urgency"] = round(slot["sum_urgency"] / slot["count"], 2)
        else:
            slot["avg_urgency"] = 0.0
    return out


def pressure_score(agg_row: dict[str, float]) -> float:
    """Composite pressure score normalised to ~0-100."""
    raw = agg_row["count"] * agg_row.get("avg_urgency", 0.0) / PRESSURE_DIVISOR
    return round(min(100.0, raw), 2)


def weekly_buckets(
    records: Iterable[dict[str, Any]],
    code: str,
    today: date | None = None,
    weeks: int = 78,
) -> list[int]:
    """Per-week count of records for one country, oldest first.

    Used for the 18-month pressure-over-time chart in the drilldown panel.
    """
    today = today or date.today()
    buckets = [0] * weeks
    horizon_days = weeks * 7
    for r in records:
        if country_code(r, world_only=False) != code:
            continue
        age = _fields.pub_date_age_days(r, today=today)
        if age is None or age < 0 or age >= horizon_days:
            continue
        week_idx = (weeks - 1) - (age // 7)
        if 0 <= week_idx < weeks:
            buckets[week_idx] += 1
    return buckets


def delta_pressure(
    records: list[dict[str, Any]],
    today: date,
    current_window_days: int = 90,
    prior_window_days: int = 90,
    world_only: bool = True,
) -> dict[str, dict[str, float]]:
    """Return per-country pressure for current vs prior windows and a delta."""
    cur = aggregate(records, today=today, window_days=current_window_days,
                    world_only=world_only)
    prior_today = today - timedelta(days=current_window_days)
    prior = aggregate(records, today=prior_today, window_days=prior_window_days,
                      world_only=world_only)
    codes = set(cur) | set(prior)
    out: dict[str, dict[str, float]] = {}
    for code in codes:
        cur_row = cur.get(code) or {"count": 0.0, "avg_urgency": 0.0, "max_urgency": 0.0,
                                     "sum_urgency": 0.0}
        prior_row = prior.get(code) or {"count": 0.0, "avg_urgency": 0.0, "max_urgency": 0.0,
                                         "sum_urgency": 0.0}
        out[code] = {
            "current_pressure": pressure_score(cur_row),
            "prior_pressure":   pressure_score(prior_row),
            "delta":            round(pressure_score(cur_row) - pressure_score(prior_row), 2),
            "current_count":    cur_row["count"],
            "current_avg_urgency": cur_row.get("avg_urgency", 0.0),
            "current_max_urgency": cur_row.get("max_urgency", 0.0),
        }
    return out
