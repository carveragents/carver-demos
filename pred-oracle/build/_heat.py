"""γ scene heat-score, sparkline buckets, entity matching.

Formula per docs/specs/10-data-prep.md §4.2 (γ slices):
    heat = Σ severity * exp(-age_days / 14)
over records in the last 90 days whose `entities` intersect the contract's
`settlement_entities`.

severity = scores.urgency.score (1-10 from Carver annotations).
"""

from __future__ import annotations

import math
import re as _re
from collections.abc import Iterable
from datetime import date
from typing import Any

from build import _fields

HEAT_HALFLIFE_DAYS: float = 14.0
DEFAULT_MAX_AGE_DAYS: int = 90

# Hard filters shared by all γ generators. Match the Stage 1 alpha rules
# (docs/specs/STAGE_1_NOTES.md §5) to drop low-relevance + noise records.
_EXCLUDED_UPDATE_TYPES: frozenset[str] = frozenset({"website error", "other"})
_MIN_RELEVANCE: float = 5.0


def is_substantive(rec: dict[str, Any]) -> bool:
    """True if a corpus record passes the γ substantive-record filter.

    Drops 'website error' / 'other' update types and low-relevance records,
    which carry noisy LLM-extracted entity annotations.
    """
    if rec.get("update_type") in _EXCLUDED_UPDATE_TYPES:
        return False
    if _fields.relevance_score(rec) < _MIN_RELEVANCE:
        return False
    if not (rec.get("title") or "").strip():
        return False
    if not (rec.get("link") or "").strip():
        return False
    return True


def _normalize(s: str) -> str:
    return s.strip().lower()


def _whole_word_in(needle: str, haystack: str) -> bool:
    """Case-insensitive whole-word/phrase containment.

    "fcc" matches "federal communications commission (fcc)" but NOT "fcca".
    The needle is a whole-word phrase inside haystack.
    """
    pattern = r"\b" + _re.escape(needle) + r"\b"
    return _re.search(pattern, haystack) is not None


def entity_match(contract_entities: list[str], record_entities: list[str]) -> bool:
    """Bidirectional whole-word containment, case-insensitive.

    Tightened from a raw substring match — that produced false positives like
    "Department of Justice" matching "California Department of Justice" article
    bodies. With whole-word match, common acronyms (FCC, SEC, CFTC) still match
    inside expanded names, but tokens that happen to appear as suffix/prefix
    fragments do not.
    """
    if not contract_entities or not record_entities:
        return False
    contract_norm = [_normalize(e) for e in contract_entities if e]
    record_norm = [_normalize(e) for e in record_entities if e]
    for ce in contract_norm:
        for re_e in record_norm:
            if ce == re_e or _whole_word_in(ce, re_e) or _whole_word_in(re_e, ce):
                return True
    return False


def _matching_records(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date,
    max_age_days: int,
) -> list[tuple[dict[str, Any], int]]:
    """Yield (record, age_days) pairs for records that match by entity AND date."""
    out: list[tuple[dict[str, Any], int]] = []
    settle = contract.get("settlement_entities") or []
    for rec in records:
        age = _fields.pub_date_age_days(rec, today=today)
        if age is None or age < 0 or age > max_age_days:
            continue
        if not entity_match(settle, rec.get("entities") or []):
            continue
        out.append((rec, age))
    return out


def heat_score(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> float:
    """Compute heat for a contract against a corpus of records."""
    today = today or date.today()
    matches = _matching_records(contract, records, today=today, max_age_days=max_age_days)
    total = 0.0
    for rec, age in matches:
        sev = _fields.urgency_score(rec)
        total += sev * math.exp(-age / HEAT_HALFLIFE_DAYS)
    return round(total, 2)


def sparkline_buckets(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    days: int = 14,
) -> list[int]:
    """Return a list of length `days`: count of matching records per day.

    Index 0 is the oldest day; index `days-1` is today.
    """
    today = today or date.today()
    buckets = [0] * days
    matches = _matching_records(contract, records, today=today, max_age_days=days - 1)
    for _rec, age in matches:
        idx = days - 1 - age
        if 0 <= idx < days:
            buckets[idx] += 1
    return buckets


def matching_event_count(
    contract: dict[str, Any],
    records: Iterable[dict[str, Any]],
    today: date | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> int:
    """Count of records matching the contract's settlement entities in window."""
    today = today or date.today()
    return len(_matching_records(contract, records, today=today, max_age_days=max_age_days))
