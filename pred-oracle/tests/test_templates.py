"""Tests that templates render to valid expected HTML."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).parent.parent / "build" / "templates"


@pytest.fixture
def env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)


def test_landing_renders_with_required_elements(env: Environment) -> None:
    ctx = {
        "events_count": 312,
        "jurisdictions_count": 38,
        "unique_regulators_count": 47,
        "earliest_pub_date": "2024-01-15",
        "latest_pub_date": "2026-05-18",
    }
    html = env.get_template("landing.html").render(**ctx)
    soup = BeautifulSoup(html, "html.parser")

    # Headline copy present
    assert soup.find("h1") is not None

    # Three scene tiles
    tiles = soup.find_all(class_="scene-tile")
    assert len(tiles) == 3, f"Expected 3 scene tiles; found {len(tiles)}"

    # Tailwind CDN script present
    scripts = [s.get("src", "") for s in soup.find_all("script")]
    assert any("cdn.tailwindcss.com" in s for s in scripts)

    # Counts surfaced
    assert "312" in html
    assert "38" in html


def test_base_template_has_required_chrome(env: Environment) -> None:
    # Base is extended via {% extends %} — render a minimal child to verify
    child = env.from_string("{% extends 'base.html' %}{% block content %}<p>x</p>{% endblock %}")
    html = child.render(
        events_count=0,
        jurisdictions_count=0,
        unique_regulators_count=0,
        earliest_pub_date=None,
        latest_pub_date=None,
    )
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("nav") is not None
    assert soup.find("footer") is not None
    # Demo disclaimer in footer
    assert "demo" in soup.find("footer").get_text().lower()


def test_landing_handles_zero_regulators_gracefully(env: Environment) -> None:
    """unique_regulators_count is 0 in production; landing must not say '0 regulatory bodies'."""
    ctx = {
        "events_count": 618,
        "jurisdictions_count": 63,
        "unique_regulators_count": 0,
        "earliest_pub_date": "2024-01-15",
        "latest_pub_date": "2026-05-15",
    }
    html = env.get_template("landing.html").render(**ctx)
    # The literal string "0 regulatory bodies" must NOT appear (case-insensitive)
    assert "0 regulatory bodies" not in html.lower()
    assert "0 regulators" not in html.lower()
    # Other counts ARE still present
    assert "618" in html
    assert "63" in html


@pytest.mark.parametrize("scene", ["gamma", "beta"])
def test_scene_intros_render(env: Environment, scene: str) -> None:
    """beta/gamma intro placeholders still render; alpha uses inbox.html instead."""
    html = env.get_template(f"{scene}/intro.html").render()
    assert "Coming soon" in html or "Placeholder" in html or "Pred-Oracle" in html
    soup = BeautifulSoup(html, "html.parser")
    # base_url defaults to "/" so the back-to-landing link in nav renders as href="/".
    assert soup.find("a", href="/") is not None


def test_close_renders(env: Environment) -> None:
    html = env.get_template("close.html").render()
    assert "thank" in html.lower() or "contact" in html.lower() or "next steps" in html.lower()


def test_alpha_components_render() -> None:
    """All alpha components are includable Jinja partials."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    REPO = Path(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    # demo_badge: no params, returns visible "demo data" text
    tpl = env.get_template("alpha/_components/demo_badge.html")
    assert "demo data" in tpl.render().lower()

    # urgency_pill: takes a tier; produces class containing the tier
    tpl = env.get_template("alpha/_components/urgency_pill.html")
    out = tpl.render(score=9, tier="critical", label="high")
    assert "critical" in out.lower()
    assert "9" in out

    # source_badge: takes url; produces an <a>
    tpl = env.get_template("alpha/_components/source_badge.html")
    out = tpl.render(url="https://cftc.gov/x", label="Primary source")
    assert 'href="https://cftc.gov/x"' in out
    assert "Primary source" in out

    # ticket_row: takes a row dict from inbox slice; produces a <tr>
    tpl = env.get_template("alpha/_components/ticket_row.html")
    row = {
        "id": "fx", "title": "T", "link": "https://x",
        "regulator": "CFTC", "jurisdictions": ["US"], "update_type": "enforcement",
        "pub_date": "2026-05-19", "age_days": 0,
        "urgency": {"score": 9, "tier": "critical", "label": "high"},
        "impact": {"score": 9, "label": "high"},
        "status": "new",
        "assignee": {"name": "Sara Chen", "initials": "SC"},
        "is_wow": True, "has_detail": True,
    }
    out = tpl.render(row=row, base_url="")
    assert "<tr" in out
    assert "T" in out  # title
    assert "fx" in out  # id used for link
    assert "SC" in out  # assignee initials


def test_base_html_includes_echarts_and_alpine() -> None:
    """base.html ships ECharts + Alpine via CDN."""
    from pathlib import Path

    base_tpl = Path(__file__).resolve().parent.parent / "build" / "templates" / "base.html"
    base = base_tpl.read_text()
    assert "echarts" in base.lower()
    assert "alpinejs" in base.lower()
    assert 'defer' in base.lower()


def test_alpha_inbox_renders_against_slice() -> None:
    """alpha/inbox.html renders against a slice JSON shape produced by alpha_inbox.py."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    REPO = Path(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("alpha/inbox.html")

    slice_data = {
        "scene": {
            "number": 1, "letter": "α",
            "headline": "Monday morning.",
            "subhead": "Three days of regulatory activity.",
            "next_label": "Drill in →", "next_href": "tickets/fx/",
        },
        "stats": {"active_items": 12, "above_threshold": 3, "threshold": 8},
        "rows": [
            {
                "id": "fx", "title": "Wow ticket", "link": "https://x",
                "regulator": "CFTC", "jurisdictions": ["US"], "update_type": "enforcement",
                "pub_date": "2026-05-19", "age_days": 0,
                "urgency": {"score": 9, "tier": "critical", "label": "high"},
                "impact": {"score": 9, "label": "high"},
                "status": "new",
                "assignee": {"name": "Sara Chen", "initials": "SC"},
                "is_wow": True, "has_detail": True,
            },
        ],
        "filter_chips": [{"label": "All", "active": True}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "Sara Chen" in out
    assert "Wow ticket" in out
    assert "Monday morning" in out
    assert "12" in out


def test_alpha_ticket_detail_renders() -> None:
    """alpha/ticket_detail.html renders a slice JSON produced by alpha_ticket.py."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    REPO = Path(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("alpha/ticket_detail.html")

    slice_data = {
        "scene": {"number": 1, "letter": "α", "back_label": "← Back to inbox", "back_href": "../"},
        "ticket": {
            "id": "fx", "title": "Title",
            "link": "https://www.cftc.gov/x",
            "regulator": {
                "name": "CFTC", "division": "Division of Enforcement", "primary_url": "cftc.gov",
            },
            "jurisdiction_tier": "us_federal",
            "jurisdictions": ["US"],
            "update_type": "enforcement",
            "update_subtype": "enforcement_agency",
            "pub_date": "2026-05-19",
            "effective_date": "2026-06-01",
            "compliance_date": None,
            "comment_deadline": None,
            "what_changed": "CFTC sued.",
            "why_it_matters": "Event contracts.",
            "key_requirements": ["Comply.", "Report."],
            "objective": "Block state action.",
            "risk_impact": "high",
            "penalties_consequences": ["Injunction"],
            "reg_references": {
                "statutes": ["CEA"], "rules": [], "past_release": [], "personnel": [],
            },
            "entities": ["Minnesota AG"],
            "tags": ["CFTC"],
            "scores": {
                "urgency": {"score": 9, "label": "high"},
                "impact": {"score": 9, "label": "high"},
                "relevance": {"score": 9, "label": "high"},
            },
            "wow_score": 9.0, "is_wow": True,
        },
        "workflow": {
            "status": "in_review", "priority": 9,
            "assignee": {"name": "Sara Chen", "initials": "SC", "role": "GC"},
            "due_date": "2026-05-21",
            "transitions": [
                {"timestamp": "2026-05-19T08:00:00+00:00", "from": None, "to": "new",
                 "by": "system", "note": "Ingested"},
            ],
            "comments": [
                {"timestamp": "2026-05-19T08:30:00+00:00", "author": "Sara Chen",
                 "role": "GC", "text": "Memo by EOD"},
            ],
        },
        "raw_annotation": {"x": "y"},
    }
    out = tpl.render(base_url="", **slice_data)
    assert "Division of Enforcement" in out
    assert "CFTC sued" in out
    assert "Comply." in out
    assert "Sara Chen" in out
    assert "demo data" in out.lower()   # synthetic block badges
    assert "https://www.cftc.gov/x" in out


def test_alpha_dashboard_renders() -> None:
    """alpha/dashboard.html renders a slice JSON and embeds chart data inline."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    REPO = Path(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("alpha/dashboard.html")
    slice_data = {
        "scene": {"number": 1, "letter": "α", "back_href": "../"},
        "window": {"days": 90, "label": "last 90 days"},
        "us_states": [{"code": "CA", "label": "California", "count": 519, "max_urgency": 9},
                      {"code": "NY", "label": "New York", "count": 273, "max_urgency": 8}],
        "top_10": [{"code": "US-CA", "label": "California", "count": 519,
                    "avg_urgency": 7.4, "max_urgency": 9}],
        "update_types": [{"label": "enforcement", "count": 100}],
        "international": [{"code": "GB", "label": "GB", "count": 87}],
        "totals": {"us_federal": 5000, "us_state_sum": 4500, "international": 26000},
    }
    out = tpl.render(base_url="", **slice_data)
    assert "California" in out
    assert "echarts.init" in out or "ECHARTS" in out.upper()
    assert "519" in out
    # Data array injected for the choropleth
    assert "US_STATES_DATA" in out or '"CA"' in out


def test_alpha_audit_export_renders() -> None:
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    REPO = Path(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("alpha/audit_export.html")
    slice_data = {
        "scene": {"number": 1, "letter": "α", "back_href": "../"},
        "period": {"label": "Q2 2026", "start": "2026-04-01", "end": "2026-06-30"},
        "rows": [
            {"timestamp": "2026-05-19T08:00:00+00:00",
             "ticket_title": "CFTC sues MN", "ticket_id": "fx",
             "transition": "(new) → new", "by": "system", "note": "Ingested"},
        ],
        "sample_pdf_path": "static/samples/audit-export-sample.pdf",
        "cta": {"label": "Next scene: Listing risk →", "href": "../../gamma/"},
    }
    out = tpl.render(base_url="", **slice_data)
    assert "Q2 2026" in out
    assert "CFTC sues MN" in out
    assert ".pdf" in out
    assert "gamma" in out.lower()
