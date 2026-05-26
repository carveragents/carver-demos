"""Tests for β template components."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent.parent


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )


def test_country_chip_renders_with_role() -> None:
    tpl = _env().get_template("beta/_components/country_chip.html")
    out = tpl.render(member={"code": "FR", "label": "France", "role": "closed"})
    assert "France" in out
    assert "FR" in out
    assert "closed" in out.lower()


def test_country_chip_role_other() -> None:
    tpl = _env().get_template("beta/_components/country_chip.html")
    out = tpl.render(member={"code": "JP", "label": "Japan", "role": "other"})
    assert "Japan" in out


def test_cascade_card_renders() -> None:
    tpl = _env().get_template("beta/_components/cascade_card.html")
    card = {
        "id": "x", "body": "FATF", "body_acronym": "FATF",
        "trigger_title": "Trigger T", "trigger_pub_date": "2025-11-20",
        "trigger_url": "https://x", "rationale": "Because.",
        "follow_window_days": 540,
        "expected_action_by": "2027-05-13",
        "historical_hit_rate": "31/39 (79%)",
        "hit_rate_adopted": 31, "hit_rate_total": 39, "hit_rate_pct": 79,
        "members": [{"code": "FR", "label": "France", "role": "closed"},
                     {"code": "BR", "label": "Brazil", "role": "operating"}],
        "footprint_overlap_count": 1,
    }
    out = tpl.render(card=card, base_url="")
    assert "FATF" in out
    assert "Trigger T" in out
    assert "France" in out
    assert "Brazil" in out
    assert "79%" in out
    assert "31 of 39" in out


def test_watchlist_card_renders() -> None:
    tpl = _env().get_template("beta/_components/watchlist_card.html")
    w = {"code": "BR", "label": "Brazil", "role": "operating",
         "rationale": "Pattern resembles France.",
         "recommended_actions": ["Engage counsel"],
         "alpha_dashboard_link": "../../alpha/dashboard/#BR",
         "evidence_events": [
             {"title": "Ev1", "regulator": "SECAP", "pub_date": "2026-05-01",
              "urgency": 8.0, "link": "https://x"},
         ]}
    out = tpl.render(item=w, base_url="")
    assert "Brazil" in out
    assert "Engage counsel" in out
    assert "Ev1" in out


def test_pressure_chart_renders_svg() -> None:
    tpl = _env().get_template("beta/_components/pressure_chart.html")
    out = tpl.render(buckets=[0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0] * 7,
                     callouts=[{"week_index": 3, "label": "X"}],
                     width=480, height=120)
    assert "<svg" in out
    assert "polyline" in out


def test_beta_intro_renders_with_scene_copy() -> None:
    tpl = _env().get_template("beta/intro.html")
    out = tpl.render(base_url="")
    assert "Q3" in out or "Q2" in out
    out_l = out.lower()
    assert "heat-map" in out_l or "heatmap" in out_l
    assert "cascade" in out_l
    assert "quarter" in out_l or "q2" in out_l
    assert 'href="' in out and "beta/heatmap/" in out


def test_beta_heatmap_template_renders() -> None:
    tpl = _env().get_template("beta/heatmap.html")
    slice_data = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "window_days": 90,
        "world_aggregates": [{"code": "FR", "label": "France", "count": 273,
                              "avg_urgency": 6.8, "max_urgency": 9.0,
                              "pressure": 87.5}],
        "us_state_aggregates": [{"code": "US-CA", "label": "CA", "count": 50,
                                  "avg_urgency": 7.0, "max_urgency": 9.0,
                                  "pressure": 70.0}],
        "platform_footprint": {
            "active_platform": "polymarket",
            "operating":   [{"code": "US", "label": "United States"}],
            "considering": [],
            "closed":      [{"code": "FR", "label": "France",
                              "closed_at": "2025-12-15", "reason": "AMF action"}],
        },
        "retrospective_focus": {
            "code": "FR", "label": "France",
            "title": "France — retrospective",
            "weekly_buckets": [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0] * 7,
            "annotation_callouts": [{"date": "2025-12-10",
                                       "label": "Public restriction",
                                       "week_index": 70}],
            "top_events": [{"title": "T", "regulator": "AMF",
                              "pub_date": "2025-12-10", "urgency": 9.0,
                              "link": "https://x", "matched_entity": "FR"}],
            "anj_disclosure": "Direct ANJ events are not in the Carver catalog.",
        },
        "anomaly_note": "France carries the highest pressure.",
    }
    out = tpl.render(base_url="", **slice_data)
    assert "France" in out
    assert "<svg" in out
    assert "world.geo.json" in out
    assert "AMF" in out
    assert "ANJ" in out


def test_beta_cascades_template_renders() -> None:
    tpl = _env().get_template("beta/cascades.html")
    slice_data = {
        "scene": {"number": 3, "letter": "β", "back_href": "../"},
        "active_platform": "polymarket",
        "cascades": [{
            "id": "fatf-1", "body": "Financial Action Task Force",
            "body_acronym": "FATF", "trigger_title": "VASP guidance update",
            "trigger_pub_date": "2025-11-20", "trigger_url": "https://x",
            "rationale": "Long history.", "follow_window_days": 540,
            "expected_action_by": "2027-05-13",
            "historical_hit_rate": "31/39 (79%)",
            "hit_rate_adopted": 31, "hit_rate_total": 39, "hit_rate_pct": 79,
            "members": [{"code": "FR", "label": "France", "role": "closed"}],
            "footprint_overlap_count": 1}],
    }
    out = tpl.render(base_url="", **slice_data)
    assert "FATF" in out
    assert "VASP guidance" in out
    assert "France" in out
    assert "79%" in out
    assert "31 of 39" in out


def test_beta_quarterly_report_template_renders() -> None:
    tpl = _env().get_template("beta/report.html")
    slice_data = {
        "scene": {"number": 3, "letter": "β", "back_label": "← Cascade signals",
                  "back_href": "../cascades/"},
        "report_window": {"start": "2026-04-01", "end": "2026-06-30",
                           "label": "Q2 2026"},
        "generated_at": "2026-05-20",
        "active_platform": "polymarket",
        "headline_stats": {"events_in_window": 12345,
                             "jurisdictions_with_activity": 67,
                             "high_urgency_events": 234,
                             "active_cascades": 3},
        "pressure_rising": [{"code": "BR", "label": "Brazil", "role": "operating",
                              "current_pressure": 78.5, "delta": 12.3,
                              "narrative": "Brazil pressure rising.",
                              "top_events": [{"title": "Ev1", "regulator": "SECAP",
                                                "pub_date": "2026-05-01",
                                                "urgency": 8.0, "link": "https://x"}]}],
        "pressure_easing": [{"code": "FI", "label": "Finland", "role": "other",
                              "current_pressure": 12.5, "delta": -8.0,
                              "narrative": "Finland pressure easing.",
                              "top_events": []}],
        "watch_list": [{"code": "BR", "label": "Brazil", "role": "operating",
                          "rationale": "Pattern resembles France.",
                          "recommended_actions": ["Engage counsel"],
                          "alpha_dashboard_link": "../../alpha/dashboard/#BR",
                          "evidence_events": [{"title": "Ev1",
                                                  "regulator": "SECAP",
                                                  "pub_date": "2026-05-01",
                                                  "urgency": 8.0,
                                                  "link": "https://x"}]}],
        "featured_cascades": [{"id": "fatf-1", "body_acronym": "FATF",
                                  "trigger_title": "T",
                                  "trigger_pub_date": "2025-11-20",
                                  "historical_hit_rate": "31/39 (79%)"}],
        "gamma_touchpoints": [{"contract_id": "kxbtc-maxprice-2026",
                                  "title": "Will Bitcoin be above $X?",
                                  "heat": 418.2,
                                  "detail_href": "../../gamma/contracts/kxbtc-maxprice-2026/"}],
        "method_notes": "Method.", "coverage_caveat": "Caveat.",
        "watch_list_disclaimer": "Pattern-based projection, not prediction. Confidence: medium.",
        "v1_footer": "V1 footer.",
        "pdf_href": "../static/samples/q2-2026-report.pdf",
    }
    out = tpl.render(base_url="", **slice_data)
    assert "Q2 2026" in out
    assert "Brazil" in out
    assert "Pattern-based projection" in out
    assert "Engage counsel" in out
    assert "Will Bitcoin" in out
    assert "q2-2026-report.pdf" in out
