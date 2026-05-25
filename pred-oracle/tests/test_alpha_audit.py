"""Tests for build/alpha_audit.py."""
import json
from datetime import date
from pathlib import Path


def _write_ticket(out_dir: Path, tid: str, title: str, status: str, assignee: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{tid}.json").write_text(json.dumps({
        "ticket": {"id": tid, "title": title},
        "workflow": {
            "status": status,
            "assignee": {"name": assignee, "initials": "XX"},
            "transitions": [
                {"timestamp": "2026-05-19T08:00:00+00:00", "from": None, "to": "new",
                 "by": "system", "note": "Ingested"},
                {"timestamp": "2026-05-19T09:00:00+00:00", "from": "new", "to": status,
                 "by": assignee, "note": "Acknowledged"},
            ],
        },
    }))


def test_audit_export_includes_all_ticket_transitions(tmp_path: Path) -> None:
    from build.alpha_audit import generate

    tickets_dir = tmp_path / "tickets"
    out = tmp_path / "audit_export.json"

    _write_ticket(tickets_dir, "t1", "Title One", "in_review", "Sara Chen")
    _write_ticket(tickets_dir, "t2", "Title Two", "drafted", "Devin Liu")

    generate(tickets_dir=tickets_dir, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    assert len(doc["rows"]) >= 4  # 2 tickets × 2 transitions
    titles = [r["ticket_title"] for r in doc["rows"]]
    assert "Title One" in titles
    assert "Title Two" in titles


def test_audit_export_rows_sorted_by_timestamp(tmp_path: Path) -> None:
    from build.alpha_audit import generate

    tickets_dir = tmp_path / "tickets"
    out = tmp_path / "audit_export.json"
    _write_ticket(tickets_dir, "t1", "Title One", "in_review", "Sara Chen")

    generate(tickets_dir=tickets_dir, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    ts = [r["timestamp"] for r in doc["rows"]]
    assert ts == sorted(ts), "rows must be sorted ascending by timestamp"


def test_audit_export_includes_cta_and_pdf_link(tmp_path: Path) -> None:
    from build.alpha_audit import generate

    tickets_dir = tmp_path / "tickets"
    out = tmp_path / "audit_export.json"
    _write_ticket(tickets_dir, "t1", "Title One", "new", "Sara Chen")

    generate(tickets_dir=tickets_dir, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    assert doc["cta"]["href"].endswith("gamma/")
    assert doc["sample_pdf_path"].endswith(".pdf")
    assert "Q" in doc["period"]["label"]


def test_audit_cta_href_is_absolute_from_root(tmp_path: Path) -> None:
    """CTA href must be 'gamma/' (joins with base_url cleanly), not '../../gamma/'."""
    from build.alpha_audit import generate

    tickets_dir = tmp_path / "tickets"
    out = tmp_path / "audit_export.json"
    _write_ticket(tickets_dir, "t1", "Title", "new", "Sara")

    generate(tickets_dir=tickets_dir, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert doc["cta"]["href"] == "gamma/", \
        "Use absolute-from-root href; base_url prefix joins cleanly."


def test_period_end_dates_are_real_quarter_ends(tmp_path: Path) -> None:
    """Q1 ends 03-31; Q4 ends 12-31. Not 03-30 / 12-30."""
    from datetime import date

    from build.alpha_audit import generate

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()

    # Q1
    out = tmp_path / "q1.json"
    generate(tickets_dir=tickets_dir, out_path=out, today=date(2026, 2, 15))
    doc = json.loads(out.read_text())
    assert doc["period"]["end"] == "2026-03-31"

    # Q4
    out2 = tmp_path / "q4.json"
    generate(tickets_dir=tickets_dir, out_path=out2, today=date(2026, 11, 15))
    doc2 = json.loads(out2.read_text())
    assert doc2["period"]["end"] == "2026-12-31"


def test_audit_export_renders_with_demo_badge(tmp_path: Path) -> None:
    """Audit-export template must carry the demo_badge mark per spec §1."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    from build.alpha_audit import generate

    REPO = Path(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    tickets_dir = tmp_path / "tickets"
    out_json = tmp_path / "audit_export.json"
    _write_ticket(tickets_dir, "t1", "Title One", "new", "Sara Chen")

    generate(tickets_dir=tickets_dir, out_path=out_json, today=date(2026, 5, 19))
    ctx = json.loads(out_json.read_text())
    ctx["base_url"] = ""
    rendered = env.get_template("alpha/audit_export.html").render(**ctx)
    assert "demo data" in rendered.lower()
