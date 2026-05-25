"""Smoke tests for the trader dashboard Jinja2 templates."""
from __future__ import annotations
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "build" / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


# ---------------------------------------------------------------------------
# _base.html
# ---------------------------------------------------------------------------

def test_trader_base_renders() -> None:
    env = _env()
    tmpl = env.get_template("trader/_base.html")
    html = tmpl.render(base_url="/", active_nav="list")
    assert "Alex&#39;s Portfolio" in html or "Alex's Portfolio" in html
    assert "Portfolio" in html
    assert "Case Studies" in html


def test_trader_base_active_nav_portfolio() -> None:
    env = _env()
    tmpl = env.get_template("trader/_base.html")
    html = tmpl.render(base_url="/", active_nav="list")
    # DEMO badge present
    assert "DEMO" in html


def test_trader_base_active_nav_retrospectives() -> None:
    env = _env()
    tmpl = env.get_template("trader/_base.html")
    html = tmpl.render(base_url="/", active_nav="retrospectives")
    assert "Case Studies" in html


# ---------------------------------------------------------------------------
# list.html
# ---------------------------------------------------------------------------

def _make_row(**overrides) -> dict:
    row = {
        "contract_id": "test-001",
        "platform": "kalshi",
        "title": "Test contract",
        "heat_tier": "active",
        "heat_value": 42.5,
        "heat_delta_7d": 5.3,
        "net_direction": "Bullish",
        "event_count_90d": 12,
        "next_catalyst": None,
        "latest_event": {
            "pub_date": "2026-05-10",
            "title": "Test event",
            "direction": "bullish",
            "magnitude": "high",
        },
        "position": {"side": "YES", "size": 100, "entry_price": 0.50},
        "detail_href": "contracts/test-001/",
        "yes_price": 62,
        "no_price": 38,
    }
    row.update(overrides)
    return row


def test_trader_list_renders() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row()])
    assert "Test contract" in html
    assert "Bullish" in html


def test_trader_list_shows_prices() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row()])
    assert "62" in html  # yes_price
    assert "38" in html  # no_price


def test_trader_list_heat_value_rendered() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row(heat_value=77.0)])
    assert "77" in html


def test_trader_list_shows_platform_badge() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row(platform="kalshi")])
    assert "kalshi" in html.lower()


def test_trader_list_shows_polymarket_badge() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row(platform="polymarket")])
    assert "polymarket" in html.lower()


def test_trader_list_shows_next_catalyst() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    row = _make_row(next_catalyst={"title": "FOMC meeting", "date": "2026-06-10"})
    html = tmpl.render(base_url="/", rows=[row])
    assert "FOMC meeting" in html


def test_trader_list_shows_demo_badge_on_position() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row()])
    assert "DEMO" in html


def test_trader_list_renders_empty() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[])
    assert "Portfolio" in html


def test_trader_list_alpine_sort_controls() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    html = tmpl.render(base_url="/", rows=[_make_row()])
    assert "x-data" in html
    assert "sort" in html
    assert "platform" in html
    assert "tier" in html


def test_trader_list_tier_badges_all_present() -> None:
    env = _env()
    tmpl = env.get_template("trader/list.html")
    rows = [
        _make_row(heat_tier="critical", title="Critical contract"),
        _make_row(heat_tier="active", title="Active contract"),
        _make_row(heat_tier="watch", title="Watch contract"),
        _make_row(heat_tier="dormant", title="Dormant contract"),
    ]
    html = tmpl.render(base_url="/", rows=rows)
    assert "critical" in html.lower()
    assert "active" in html.lower()
    assert "watch" in html.lower()
    assert "dormant" in html.lower()


# ---------------------------------------------------------------------------
# briefing.html
# ---------------------------------------------------------------------------

def _make_contract(**overrides) -> dict:
    c = {
        "id": "test-001",
        "platform": "kalshi",
        "kind": "active",
        "title": "Test contract",
        "expires_at": "2026-12-31",
        "resolution_criteria": "Resolves YES if the test condition is met.",
        "settlement_entities": [{"name": "SEC", "role": "regulator"}],
        "conditions": [
            {"id": "A", "label": "Test condition", "summary": "Test summary"},
        ],
        "narrative": "Test narrative.",
    }
    c.update(overrides)
    return c


def _make_timeline_event(**overrides) -> dict:
    ev = {
        "pub_date": "2026-05-10",
        "title": "Test event",
        "regulator": "SEC",
        "url": "https://example.com",
        "direction": "bullish",
        "magnitude": "high",
        "mechanism": "Binding Action",
        "timeline_shift": "none",
        "condition_tag": "A",
        "one_line_why": "Direct impact on resolution.",
        "relevance_score": 8,
        "high_impact": True,
    }
    ev.update(overrides)
    return ev


def _make_heat_panel(**overrides) -> dict:
    hp = {
        "value": 42.5,
        "tier": "active",
        "delta_7d": 5.3,
        "peer_percentile": 72,
        "urgency_weighted_sparkline": [0] * 14,
        "primary_drivers": ["Test driver"],
        "explainer": "Test explainer.",
    }
    hp.update(overrides)
    return hp


def test_trader_briefing_renders() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[_make_timeline_event()],
        heat_panel=_make_heat_panel(),
        position={"side": "YES", "size": 100, "entry_price": 0.50},
        prices={"series": []},
    )
    assert "Test contract" in html
    assert "Binding Action" in html


def test_trader_briefing_shows_back_link() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "Portfolio" in html
    # back link present
    assert "trader/" in html


def test_trader_briefing_shows_platform_badge() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(platform="polymarket"),
        timeline=[],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "polymarket" in html.lower()


def test_trader_briefing_direction_badges() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[
            _make_timeline_event(direction="bullish"),
            _make_timeline_event(direction="bearish", title="Bearish event"),
            _make_timeline_event(direction="neutral", title="Neutral event"),
        ],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "bullish" in html.lower()
    assert "bearish" in html.lower()


def test_trader_briefing_shows_position_with_demo_badge() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[],
        heat_panel=_make_heat_panel(),
        position={"side": "YES", "size": 250, "entry_price": 0.45},
        prices={"series": []},
    )
    assert "DEMO" in html
    assert "YES" in html
    assert "250" in html


def test_trader_briefing_heat_panel_rendered() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[],
        heat_panel=_make_heat_panel(value=88.0, tier="critical", explainer="High urgency."),
        position=None,
        prices={"series": []},
    )
    assert "88" in html
    assert "High urgency" in html


def test_trader_briefing_narrative_shown() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(narrative="The regulatory environment is shifting rapidly."),
        timeline=[],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "regulatory environment is shifting" in html


def test_trader_briefing_timeline_filter_alpine() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[_make_timeline_event()],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "x-data" in html
    assert "filter" in html


def test_trader_briefing_timeline_shift_indicator() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[_make_timeline_event(timeline_shift="sooner")],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "Sooner" in html


def test_trader_briefing_price_chart_script_injected() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(),
        timeline=[],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": [[("2026-01-01", 55), ("2026-02-01", 60)]]},
    )
    assert "price-chart" in html
    assert "echarts" in html or "price-chart" in html


def test_trader_briefing_settlement_entities_shown() -> None:
    env = _env()
    tmpl = env.get_template("trader/briefing.html")
    html = tmpl.render(
        base_url="/",
        contract=_make_contract(settlement_entities=[
            {"name": "CFTC", "role": "regulator"},
            {"name": "Kalshi", "role": "exchange"},
        ]),
        timeline=[],
        heat_panel=_make_heat_panel(),
        position=None,
        prices={"series": []},
    )
    assert "CFTC" in html
    assert "Kalshi" in html


# ---------------------------------------------------------------------------
# calendar.html
# ---------------------------------------------------------------------------

def _make_calendar_context() -> dict:
    day_with_events = {
        "date": "2026-05-15",
        "day_num": 15,
        "events": [
            {"title": "CFTC ruling", "direction": "bullish", "color": "emerald",
             "regulator": "CFTC", "contract_title": "Test contract"},
        ],
    }
    day_empty = {"date": "2026-05-16", "day_num": 16, "events": []}

    week = [None, None, day_with_events, day_empty, None, None, None]
    month = {
        "label": "May 2026",
        "weeks": [week],
        "days": [day_with_events, day_empty],
    }

    all_events = [
        {"date": "2026-05-15", "title": "CFTC ruling", "direction": "bullish",
         "regulator": "CFTC", "contract_title": "Test contract"},
    ]
    return {
        "months": [month],
        "today": "2026-05-15",
        "all_events": all_events,
    }


def test_trader_calendar_renders() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "May 2026" in html


def test_trader_calendar_shows_event_dots() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "CFTC ruling" in html


def test_trader_calendar_alpine_month_nav() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "x-data" in html
    assert "currentMonth" in html


def test_trader_calendar_has_day_headers() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "Sun" in html
    assert "Mon" in html
    assert "Sat" in html


def test_trader_calendar_selected_date_panel() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "selectedDate" in html


def test_trader_calendar_list_view_toggle_link() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "List view" in html
    assert "trader/" in html


def test_trader_calendar_legend_present() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "Bullish" in html
    assert "Bearish" in html
    assert "Neutral" in html


def test_trader_calendar_ticker_strip() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", **_make_calendar_context())
    assert "Recent" in html


def test_trader_calendar_empty_months() -> None:
    env = _env()
    tmpl = env.get_template("trader/calendar.html")
    html = tmpl.render(base_url="/", months=[], today="2026-05-15", all_events=[])
    assert "Calendar" in html


# ---------------------------------------------------------------------------
# retrospectives.html
# ---------------------------------------------------------------------------

def _make_retrospective(contract_id: str = "retro-001", platform: str = "kalshi") -> dict:
    return {
        "contract": {
            "id": contract_id,
            "platform": platform,
            "kind": "retrospective",
            "title": "Will Kalshi be banned?",
            "expires_at": "2025-11-30",
            "resolved_at": "2025-11-15",
            "resolved_outcome": "YES",
            "narrative": "The contract resolved YES after the court ruling.",
        },
        "narrative_snippet": "The court ruling triggered resolution.",
    }


def test_trader_retrospectives_renders() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[_make_retrospective()])
    assert "Will Kalshi be banned" in html
    assert "Case Studies" in html


def test_trader_retrospectives_shows_resolution_badge() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[_make_retrospective()])
    assert "Resolved YES" in html


def test_trader_retrospectives_shows_platform_badge() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[_make_retrospective(platform="polymarket")])
    assert "polymarket" in html.lower()


def test_trader_retrospectives_links_to_detail() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[_make_retrospective(contract_id="abc-123")])
    assert "abc-123" in html


def test_trader_retrospectives_shows_narrative_snippet() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[_make_retrospective()])
    assert "court ruling triggered resolution" in html


def test_trader_retrospectives_multiple_cards() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    retros = [
        _make_retrospective("r1", "kalshi"),
        _make_retrospective("r2", "polymarket"),
    ]
    # Override titles so they're distinguishable
    retros[0]["contract"]["title"] = "Kalshi state ban?"
    retros[1]["contract"]["title"] = "Polymarket CFTC action?"
    html = tmpl.render(base_url="/", retrospectives=retros)
    assert "Kalshi state ban" in html
    assert "Polymarket CFTC action" in html


def test_trader_retrospectives_empty_list() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[])
    assert "Case Studies" in html
    assert "No case studies" in html


def test_trader_retrospectives_intro_paragraph() -> None:
    env = _env()
    tmpl = env.get_template("trader/retrospectives.html")
    html = tmpl.render(base_url="/", retrospectives=[])
    # Intro text is present
    assert "retrospective" in html.lower()
