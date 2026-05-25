"""Generate α audit-export slice (build/page_data/alpha/audit_export.json).

Reads the 5 ticket slices and composes a synthetic transition log table.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def _format_transition(t: dict[str, Any]) -> str:
    frm = t.get("from") or "(new)"
    to = t.get("to") or "?"
    return f"{frm} → {to}"


def generate(tickets_dir: Path, out_path: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rows: list[dict[str, Any]] = []
    for path in sorted(tickets_dir.glob("*.json")):
        doc = json.loads(path.read_text())
        ticket = doc.get("ticket") or {}
        wf = doc.get("workflow") or {}
        for t in wf.get("transitions") or []:
            rows.append({
                "timestamp": t.get("timestamp") or "",
                "ticket_title": ticket.get("title") or "",
                "ticket_id": ticket.get("id") or "",
                "transition": _format_transition(t),
                "by": t.get("by") or "",
                "note": t.get("note") or "",
            })

    rows.sort(key=lambda r: r["timestamp"])

    quarter = (today.month - 1) // 3 + 1
    quarter_end_months = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    end_month, end_day = quarter_end_months[quarter]
    slice_doc = {
        "scene": {"number": 1, "letter": "α", "back_href": "../"},
        "period": {
            "label": f"Q{quarter} {today.year}",
            "start": f"{today.year}-{3*(quarter-1)+1:02d}-01",
            "end": f"{today.year}-{end_month:02d}-{end_day:02d}",
        },
        "rows": rows,
        "sample_pdf_path": "static/samples/audit-export-sample.pdf",
        "cta": {"label": "Next scene: Listing risk →", "href": "gamma/"},
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(slice_doc, indent=2))
    return slice_doc


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parent.parent
    generate(
        tickets_dir=REPO / "build" / "page_data" / "alpha" / "tickets",
        out_path=REPO / "build" / "page_data" / "alpha" / "audit_export.json",
    )
