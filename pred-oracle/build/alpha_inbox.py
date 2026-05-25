"""Generate the α-inbox slice (build/page_data/alpha/inbox.json).

Reads data/_scratch/artifacts.jsonl + data/alpha-curation.yml.
Filters via build._scoring.is_inbox_eligible, ranks via build._scoring.wow_score,
takes top N (curation.inbox_top_n), promotes the curated wow ticket to row 0.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# Allow running as `python build/alpha_inbox.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _scoring  # noqa: E402

_STATUS_CYCLE: tuple[str, ...] = ("new", "in_review", "acknowledged", "new", "drafted")


def _record_id(rec: dict[str, Any]) -> str:
    """Extract the primary record ID from a corpus record.

    Mirrors the logic in _build_row for consistent ID lookup.
    Returns feed_entry_id if present, otherwise artifact_id, otherwise empty string.
    """
    return rec.get("feed_entry_id") or rec.get("artifact_id") or ""


def _stream_eligible(corpus_path: Path, today: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if _scoring.is_inbox_eligible(rec, today=today):
                out.append(rec)
    return out


def _build_row(
    rec: dict[str, Any],
    today: date,
    idx: int,
    assignees: list[dict[str, str]],
    detail_ids: set[str],
    wow_id: str,
) -> dict[str, Any]:
    urg = _fields.urgency_score(rec)
    imp = _fields.impact_score(rec)
    rid = _record_id(rec)
    return {
        "id": rid,
        "title": rec.get("title") or "",
        "link": rec.get("link") or "",
        "regulator": _fields.regulator_display(rec),
        "jurisdictions": _fields.jurisdictions(rec),
        "update_type": rec.get("update_type") or "",
        "pub_date": _fields.pub_date_iso(rec),
        "age_days": _fields.pub_date_age_days(rec, today=today),
        "urgency": {
            "score": urg,
            "label": (rec.get("scores") or {}).get("urgency", {}).get("label", ""),
            "tier": _fields.urgency_tier(urg),
        },
        "impact": {
            "score": imp,
            "label": (rec.get("scores") or {}).get("impact", {}).get("label", ""),
        },
        "wow_score": _scoring.wow_score(rec, today=today),
        "status": _STATUS_CYCLE[idx % len(_STATUS_CYCLE)],
        "assignee": {
            "name": assignees[idx % len(assignees)]["name"],
            "initials": assignees[idx % len(assignees)]["initials"],
        },
        "is_wow": rid == wow_id,
        "has_detail": rid in detail_ids,
    }


def generate(
    corpus_path: Path,
    curation_path: Path,
    out_path: Path,
    today: date | None = None,
) -> dict[str, Any]:
    """Write the α inbox slice. Returns the dict for inspection."""
    today = today or date.today()
    curation = yaml.safe_load(curation_path.read_text())
    wow_id = curation["wow_ticket_id"]
    supporting = curation["supporting_ticket_ids"]
    detail_ids = {wow_id, *supporting}
    top_n = int(curation["inbox_top_n"])
    assignees = curation["synthetic_assignees"]

    eligible = _stream_eligible(corpus_path, today)
    eligible.sort(
        key=lambda r: (_scoring.wow_score(r, today=today), _fields.pub_date_iso(r)),
        reverse=True,
    )

    # Promote wow ticket to position 0 if present
    chosen: list[dict[str, Any]] = []
    wow_rec = next((r for r in eligible if _record_id(r) == wow_id), None)
    if wow_rec is None:
        raise ValueError(
            f"wow_ticket_id {wow_id!r} not found in eligible corpus. "
            f"Update data/alpha-curation.yml or re-run the corpus pull."
        )
    chosen.append(wow_rec)
    for r in eligible:
        if len(chosen) >= top_n:
            break
        if _record_id(r) == wow_id:
            continue
        chosen.append(r)

    rows = [
        _build_row(r, today=today, idx=i, assignees=assignees, detail_ids=detail_ids, wow_id=wow_id)
        for i, r in enumerate(chosen)
    ]

    above_threshold = sum(1 for r in rows if r["urgency"]["score"] >= 8)

    slice_doc = {
        "scene": {
            "number": 1,
            "letter": "α",
            "headline": "Monday, 9:00 AM. You are the General Counsel.",
            "subhead": "Three days of regulatory activity hit while you were offline.",
            "next_label": "Drill into top ticket →",
            "next_href": f"tickets/{wow_id}/",
        },
        "stats": {
            "active_items": len(eligible),
            "above_threshold": above_threshold,
            "threshold": 8,
        },
        "rows": rows,
        "filter_chips": [
            {"label": "All", "active": True},
            {"label": "New", "active": False},
            {"label": "In Review", "active": False},
            {"label": "Above threshold", "active": False},
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(slice_doc, indent=2))
    return slice_doc


if __name__ == "__main__":
    generate(
        corpus_path=_REPO_ROOT / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=_REPO_ROOT / "data" / "alpha-curation.yml",
        out_path=_REPO_ROOT / "build" / "page_data" / "alpha" / "inbox.json",
    )
