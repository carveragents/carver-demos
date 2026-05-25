"""Generate α ticket-detail slices (build/page_data/alpha/tickets/{id}.json).

One JSON per curated ticket (1 wow + 4 supporting = 5 total).

NOTE (spec reviewer): A curated ID that is absent from the corpus is logged
as a warning and silently skipped rather than raising, so partial builds succeed
when the corpus is fresher than the curation file. The wow ID is not treated
specially here — unlike alpha_inbox.py which raises on a missing wow ticket,
this module produces whatever subset of detail pages the corpus supports.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

# Allow running as `python build/alpha_ticket.py` from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from build import _fields, _scoring  # noqa: E402

_STATUS_CYCLE: tuple[str, ...] = ("new", "acknowledged", "in_review", "drafted")


def _record_id(rec: dict[str, Any]) -> str:
    return rec.get("feed_entry_id") or rec.get("artifact_id") or ""


def _date_or_none(s: str | None) -> str | None:
    if not s:
        return None
    s = str(s).strip()
    return s[:10] if len(s) >= 10 else None


def _build_ticket_dto(rec: dict[str, Any], today: date, wow_id: str) -> dict[str, Any]:
    cd = rec.get("critical_dates") or {}
    isum = rec.get("impact_summary") or {}
    refs = rec.get("reg_references") or {}

    return {
        "id": _record_id(rec),
        "title": rec.get("title") or "",
        "link": rec.get("link") or "",
        "regulator": {
            "name": rec.get("regulator_name") or "",
            "division": rec.get("regulator_division") or "",
            "primary_url": rec.get("classification_base_url") or "",
        },
        "jurisdiction_tier": (rec.get("jurisdiction_tier") or {}).get("label") or "",
        "jurisdictions": _fields.jurisdictions(rec),
        "update_type": rec.get("update_type") or "",
        "update_subtype": rec.get("update_subtype") or "",
        "pub_date": _fields.pub_date_iso(rec),
        "effective_date": _date_or_none(cd.get("effective_date")),
        "compliance_date": _date_or_none(cd.get("compliance_date")),
        "comment_deadline": _date_or_none(cd.get("comment_deadline")),
        "what_changed": isum.get("what_changed") or "",
        "why_it_matters": isum.get("why_it_matters") or "",
        "key_requirements": isum.get("key_requirements") or [],
        "objective": isum.get("objective") or "",
        "risk_impact": isum.get("risk_impact") or "",
        "penalties_consequences": rec.get("penalties_consequences") or [],
        "reg_references": {
            "statutes": refs.get("statutes") or [],
            "rules": refs.get("rules") or [],
            "past_release": refs.get("past_release") or [],
            "precedents": refs.get("precedents") or [],
            "personnel": refs.get("personnel") or [],
        },
        "entities": rec.get("entities") or [],
        "tags": rec.get("tags") or [],
        "scores": rec.get("scores") or {},
        "wow_score": _scoring.wow_score(rec, today=today),
        "is_wow": (_record_id(rec) == wow_id),
    }


def _build_workflow(
    rec: dict[str, Any],
    idx: int,
    assignees: list[dict[str, str]],
    comment_templates: list[dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    """Synthetic workflow block. Marked demo data in templates."""
    urg = _fields.urgency_score(rec)
    priority = min(10, max(1, int(round(0.6 * urg + 0.4 * _fields.impact_score(rec)))))
    assignee = assignees[idx % len(assignees)]
    status = _STATUS_CYCLE[idx % len(_STATUS_CYCLE)]
    now = datetime(today.year, today.month, today.day, 9, 0, tzinfo=timezone.utc)
    due = (now + timedelta(days=2)).date().isoformat()

    regulator = rec.get("regulator_name") or "the regulator"

    comments = []
    for t in comment_templates:
        ts = (now + timedelta(hours=int(t.get("timestamp_offset_hours", 0)))).isoformat()
        comments.append({
            "timestamp": ts,
            "author": t["author"],
            "role": t["role"],
            "text": t["text"].replace("{regulator}", regulator),
        })

    transitions = [
        {
            "timestamp": (now - timedelta(hours=6)).isoformat(),
            "from": None,
            "to": "new",
            "by": "system",
            "note": "Ingested from Carver annotation pipeline.",
        },
        {
            "timestamp": (now - timedelta(hours=4)).isoformat(),
            "from": "new",
            "to": "acknowledged",
            "by": assignee["name"],
            "note": "Acknowledged in morning triage.",
        },
    ]

    return {
        "status": status,
        "priority": priority,
        "assignee": {
            "name": assignee["name"],
            "initials": assignee["initials"],
            "role": assignee.get("role", ""),
        },
        "due_date": due,
        "transitions": transitions,
        "comments": comments,
    }


def generate(
    corpus_path: Path,
    curation_path: Path,
    out_dir: Path,
    today: date | None = None,
) -> list[Path]:
    """Write one ticket-detail slice per curated ID. Returns list of written paths."""
    today = today or date.today()
    curation = yaml.safe_load(curation_path.read_text())
    wow_id = curation["wow_ticket_id"]
    wanted_ids = [wow_id, *curation["supporting_ticket_ids"]]
    seen_ids = set(wanted_ids)

    found: dict[str, dict[str, Any]] = {}
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rid = _record_id(rec)
            if rid in seen_ids and rid not in found:
                found[rid] = rec
                if len(found) == len(seen_ids):
                    break

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for idx, rid in enumerate(wanted_ids):
        rec = found.get(rid)
        if rec is None:
            print(f"WARN: curated id {rid} not found in corpus; skipping", file=sys.stderr)
            continue
        slice_doc = {
            "scene": {
                "number": 1,
                "letter": "α",
                "back_label": "← Back to inbox",
                "back_href": "../",
            },
            "ticket": _build_ticket_dto(rec, today=today, wow_id=wow_id),
            "workflow": _build_workflow(
                rec,
                idx=idx,
                assignees=curation["synthetic_assignees"],
                comment_templates=curation["synthetic_comment_templates"],
                today=today,
            ),
            "raw_annotation": rec,
        }
        out_path = out_dir / f"{rid}.json"
        out_path.write_text(json.dumps(slice_doc, indent=2))
        written.append(out_path)

    return written


if __name__ == "__main__":
    REPO = _REPO_ROOT
    paths = generate(
        corpus_path=REPO / "data" / "_scratch" / "artifacts.jsonl",
        curation_path=REPO / "data" / "alpha-curation.yml",
        out_dir=REPO / "build" / "page_data" / "alpha" / "tickets",
    )
    print(f"Wrote {len(paths)} ticket slices")
