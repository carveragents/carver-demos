"""Tests for γ template components."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent.parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )


def test_sparkline_renders_inline_svg() -> None:
    tpl = _env().get_template("gamma/_components/sparkline.html")
    out = tpl.render(values=[0, 1, 0, 2, 1, 3, 2, 1, 4, 2, 3, 5, 2, 1])
    assert "<svg" in out
    assert "</svg>" in out


def test_sparkline_handles_all_zeros() -> None:
    tpl = _env().get_template("gamma/_components/sparkline.html")
    out = tpl.render(values=[0] * 14)
    assert "<svg" in out
    # No error; no division by zero


def test_entity_chip_shows_role() -> None:
    tpl = _env().get_template("gamma/_components/entity_chip.html")
    out = tpl.render(entity={"name": "CFTC", "role": "regulator"})
    assert "CFTC" in out
    assert "regulator" in out.lower()


def test_contract_row_renders() -> None:
    tpl = _env().get_template("gamma/_components/contract_row.html")
    row = {
        "id": "k1", "platform": "kalshi", "title": "K1", "external_id": "KX1",
        "status": "active", "settlement_entities": ["FCC", "ByteDance"],
        "heat": 73.5, "heat_delta_7d": 4.2, "tier": "active", "sparkline": [0] * 14,
        "heat_window_label": "current",
        "matching_event_count": 12, "last_event_pub_date": "2026-05-19",
        "open_tickets_count": 1, "is_stale": False,
        "detail_href": "contracts/k1/",
    }
    out = tpl.render(row=row, base_url="")
    assert "<tr" in out
    assert "K1" in out
    assert "73" in out  # heat number


def test_signal_callout_with_days_ahead() -> None:
    tpl = _env().get_template("gamma/_components/signal_callout.html")
    out = tpl.render(callout={"days_ahead": 4, "news_url": "https://x",
                              "news_date": "2025-04-25",
                              "label": "Pred-Oracle signal preceded news by 4 days"})
    assert "4 days" in out
    assert "https://x" in out


def test_signal_callout_empty_when_no_data() -> None:
    tpl = _env().get_template("gamma/_components/signal_callout.html")
    out = tpl.render(callout={"days_ahead": None, "news_url": None,
                              "news_date": None, "label": None})
    # Renders nothing visible (template returns empty / whitespace)
    assert "<span" not in out and "<div" not in out


def test_gamma_scan_renders_with_three_tabs() -> None:
    tpl = _env().get_template("gamma/scan.html")
    bundle = {
        "scans": [
            {"id": "tiktokban", "title": "Will TikTok be banned…", "resolution_criteria": "RC",
             "platform_hint": "kalshi", "severity": 8,
             "severity_breakdown": {"matching_events_count": 12, "max_urgency": 9.0, "top_entity": "FCC"},
             "extracted_entities": [{"name": "FCC", "source": "settlement_entities"}],
             "recent_events": [{"title": "FCC filing", "regulator": "FCC", "pub_date": "2026-05-10",
                                "urgency": 8.0, "link": "https://fcc.gov/x", "matched_entity": "FCC"}],
             "warnings": []},
            {"id": "solana_etf_2027", "title": "Solana ETF…", "resolution_criteria": "RC",
             "platform_hint": "polymarket", "severity": 7,
             "severity_breakdown": {"matching_events_count": 4, "max_urgency": 7.0, "top_entity": "SEC"},
             "extracted_entities": [{"name": "SEC", "source": "settlement_entities"}],
             "recent_events": [], "warnings": []},
            {"id": "state_kalshi_action", "title": "State action…", "resolution_criteria": "RC",
             "platform_hint": "kalshi", "severity": 9,
             "severity_breakdown": {"matching_events_count": 2, "max_urgency": 8.0, "top_entity": "NJ"},
             "extracted_entities": [], "recent_events": [], "warnings": []},
        ],
    }
    out = tpl.render(base_url="", **bundle)
    assert "Will TikTok be banned" in out
    assert "Solana ETF" in out
    assert "State action" in out
    # Tabs use Alpine: look for x-data
    assert "x-data" in out


def test_gamma_dashboard_renders_against_slice() -> None:
    tpl = _env().get_template("gamma/dashboard.html")
    slice_data = {
        "scene": {"number": 2, "letter": "γ", "back_href": "../"},
        "window_days": 90,
        "contracts": [
            {"id": "k1", "platform": "kalshi", "title": "K1", "external_id": "KX1",
             "kind": "active", "status": "active", "settlement_entities": ["FCC"],
             "heat": 73.5, "heat_delta_7d": 4.2, "tier": "active", "sparkline": [0]*14,
             "heat_window_label": "current",
             "matching_event_count": 12, "last_event_pub_date": "2026-05-19",
             "open_tickets_count": 1, "is_stale": False, "detail_href": "contracts/k1/"},
        ],
        "rising_narrative": "Heat rising: \"K1\". Watch closely.",
        "filter_chips": [{"label": "All", "min_heat": 0, "active": True}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "K1" in out
    assert "<svg" in out
    assert "Heat rising" in out


def test_gamma_contract_detail_renders() -> None:
    tpl = _env().get_template("gamma/contract_detail.html")
    slice_data = {
        "scene": {"number": 2, "letter": "γ", "back_label": "← Dashboard", "back_href": "../"},
        "contract": {
            "id": "ttb", "platform": "kalshi", "kind": "retrospective",
            "title": "TikTok Ban", "external_id": "TIKTOKBAN-25APR30",
            "status": "resolved",
            "listed_at": "2025-01-15", "expires_at": "",
            "resolved_at": "2025-04-30",
            "resolution_criteria": "Resolves YES if …",
            "settlement_entities": [
                {"name": "FCC", "role": "regulator"},
                {"name": "ByteDance", "role": "company"},
            ],
            "source_urls": ["https://web.archive.org/web/2025"],
            "primary_source_url": "https://web.archive.org/web/2025",
            "heat": 12.4,
            "heat_history": [0, 0, 1, 0, 2, 1, 0, 1, 1, 3, 2, 4, 1, 0],
            "conditions": [
                {"id": "A", "label": "Test cond A", "summary": "..."},
                {"id": "B", "label": "Test cond B", "summary": "..."},
            ],
            "narrative": "Test narrative.",
        },
        "timeline": [
            {"pub_date": "2025-03-04", "title": "CFIUS filing on ByteDance",
             "regulator": "CFIUS", "url": "https://cfius.gov/x", "urgency": 9.0,
             "impact": 9.0, "matched_entity": "ByteDance",
             "carver_feed_entry_id": "f1",
             "condition_tag": "background",
             "one_line_why": "Pred-Oracle signal preceded news by 4 days",
             "precedence_callout": {"days_ahead": 4, "news_date": "2025-03-08",
                                    "news_url": "https://reuters.com/x",
                                    "label": "Pred-Oracle signal preceded news by 4 days"}},
        ],
        "open_tickets": [{"summary": "Escalating", "severity": "high",
                          "assignee_initials": "MV", "is_demo": True}],
        "heat_panel": {
            "value": 56.0, "tier": "active", "delta_7d": 18.3,
            "peer_percentile": 88,
            "urgency_weighted_sparkline": [0] * 14,
            "primary_drivers": [], "explainer": "Heat explainer text.",
        },
    }
    out = tpl.render(base_url="", **slice_data)
    assert "TikTok Ban" in out
    assert "CFIUS filing on ByteDance" in out
    assert "FCC" in out
    assert "ByteDance" in out
    assert "Pred-Oracle signal preceded news by 4 days" in out
    assert "Escalating" in out
    assert "demo data" in out.lower()


def test_contract_detail_renders_conditions_and_legend(tmp_path) -> None:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader("build/templates"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("gamma/contract_detail.html")
    contract = {
        "id": "ttb", "kind": "retrospective", "platform": "kalshi", "status": "resolved",
        "title": "TikTok ban?", "resolution_criteria": "r",
        "listed_at": "2024-04-24", "resolved_at": "2025-04-30",
        "settlement_entities": [{"name": "TikTok", "role": "company"}],
        "source_urls": ["https://example.com"],
        "primary_source_url": "https://example.com",
        "conditions": [
            {"id": "A", "label": "App-store unavailability", "summary": "..."},
            {"id": "B", "label": "Federal divestiture order", "summary": "..."},
        ],
        "narrative": "Between July 2024 and April 2025, the contract was driven by PAFACA enforcement.",
        "heat": 56.0, "heat_history": [0] * 14,
    }
    timeline = [
        {"pub_date": "2025-04-04", "title": "EO delay 2", "regulator": "WH",
         "url": "u", "urgency": 8, "impact": 7,
         "matched_entity": "TikTok", "carver_feed_entry_id": "f1",
         "one_line_why": "Second extension defers enforcement.",
         "condition_tag": "B"},
    ]
    heat_panel = {
        "value": 56.0, "tier": "active", "delta_7d": 18.3, "peer_percentile": 88,
        "urgency_weighted_sparkline": [0, 1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1],
        "primary_drivers": [], "explainer": "Heat driven by Commerce activity.",
    }
    html = template.render(
        scene={"back_label": "← back"},
        contract=contract, timeline=timeline,
        heat_panel=heat_panel, open_tickets=[], base_url="",
    )
    assert "Conditions for YES" in html
    assert "App-store unavailability" in html
    assert "Federal divestiture order" in html
    assert "Between July 2024" in html
    assert "Regulatory timeline" in html
    assert "Condition:" in html
    assert "Urgency:" in html
    assert "ACTIVE" in html.upper()  # tier label may be 'active' but rendered uppercase
    assert "Heat driven by Commerce" in html
    assert "Second extension defers enforcement" in html


def test_gamma_intro_renders_with_scene_copy() -> None:
    tpl = _env().get_template("gamma/intro.html")
    out = tpl.render(base_url="")
    assert "pre-listing" in out.lower() or "pre listing" in out.lower()
    assert "active contracts" in out.lower()
    out_l = out.lower()
    assert "scan" in out_l
    # Primary CTA → /gamma/scan/
    assert 'href="' in out and "gamma/scan/" in out


def test_dashboard_renders_active_resolved_sections() -> None:
    tpl = _env().get_template("gamma/dashboard.html")
    slice_data = {
        "scene": {"number": 2, "letter": "γ", "back_href": "../"},
        "window_days": 14,
        "contracts": [
            {"id": "a", "platform": "kalshi", "title": "Active C", "external_id": "AC",
             "kind": "active", "status": "active",
             "heat": 45.0, "heat_delta_7d": 2.0, "tier": "active",
             "heat_window_label": "current", "sparkline": [0]*14,
             "settlement_entities": ["FOMC"], "open_tickets_count": 0,
             "is_stale": False, "last_event_pub_date": "2026-05-15",
             "detail_href": "contracts/a/", "matching_event_count": 3},
            {"id": "r", "platform": "kalshi", "title": "Retro C", "external_id": "RC",
             "kind": "retrospective", "status": "resolved",
             "heat": 60.0, "heat_delta_7d": 0.0, "tier": "active",
             "heat_window_label": "at resolution", "sparkline": [0]*14,
             "settlement_entities": ["TikTok"], "open_tickets_count": 0,
             "is_stale": False, "last_event_pub_date": "",
             "detail_href": "contracts/r/", "matching_event_count": 8},
        ],
        "rising_narrative": "Heat rising: test.",
        "filter_chips": [{"label": "All", "min_heat": 0, "active": True}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "Resolved (retrospective)" in out
    assert "at resolution" in out
    assert "current" in out
    assert "Active C" in out and "Retro C" in out
