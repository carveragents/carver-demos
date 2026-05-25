"""Tests for generate.py: routing unit tests and integration build test."""

from pathlib import Path

import pytest

from build.generate import _route_for_template, build_site


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("landing.html", "index.html"),
        ("close.html", "close.html"),
        ("alpha/inbox.html", "alpha/index.html"),
        ("gamma/intro.html", "gamma/index.html"),
        ("beta/intro.html", "beta/index.html"),
        ("alpha/dashboard.html", "alpha/dashboard/index.html"),
    ],
)
def test_route_for_template(rel: str, expected: str) -> None:
    assert _route_for_template(Path(rel)) == Path(expected)


def test_build_site_respects_base_url_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When PRED_ORACLE_BASE_URL is set, internal URLs are prefixed."""
    monkeypatch.setenv("PRED_ORACLE_BASE_URL", "/pred-oracle/")
    repo_root = Path(__file__).parent.parent
    site_out = tmp_path / "site"
    build_site(repo_root=repo_root, out_dir=site_out)

    landing_html = (site_out / "index.html").read_text()
    assert 'href="/pred-oracle/alpha/"' in landing_html
    assert 'href="/pred-oracle/static/css/site.css"' in landing_html


def test_build_produces_all_pages(tmp_path: Path) -> None:
    repo_root = Path(__file__).parent.parent
    site_out = tmp_path / "site"

    build_site(repo_root=repo_root, out_dir=site_out)

    # Top-level pages exist
    assert (site_out / "index.html").exists()
    assert (site_out / "close.html").exists()

    # Scene placeholders exist
    for scene in ("alpha", "gamma", "beta"):
        assert (site_out / scene / "index.html").exists(), f"{scene}/index.html missing"

    # Static assets copied
    assert (site_out / "static" / "css" / "site.css").exists()
    assert (site_out / "static" / "js" / "site.js").exists()


def test_render_parametric_tickets(tmp_path: Path) -> None:
    """generate.py renders one HTML per ticket slice."""
    import json
    from pathlib import Path as _P

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    from build.generate import _render_parametric_tickets

    REPO = _P(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    pd_dir = tmp_path / "build" / "page_data" / "alpha" / "tickets"
    pd_dir.mkdir(parents=True)
    for i in range(3):
        (pd_dir / f"t{i}.json").write_text(json.dumps({
            "scene": {"number": 1, "letter": "α",
                      "back_label": "← Back", "back_href": "../"},
            "ticket": {
                "id": f"t{i}", "title": f"Title {i}",
                "link": "https://x",
                "regulator": {"name": "R", "division": "", "primary_url": ""},
                "jurisdiction_tier": "us_federal", "jurisdictions": ["US"],
                "update_type": "enforcement", "update_subtype": "",
                "pub_date": "2026-05-19",
                "effective_date": None, "compliance_date": None, "comment_deadline": None,
                "what_changed": "WC", "why_it_matters": "WIM",
                "key_requirements": [], "objective": "", "risk_impact": "",
                "penalties_consequences": [],
                "reg_references": {
                    "statutes": [], "rules": [], "past_release": [],
                    "precedents": [], "personnel": [],
                },
                "entities": [], "tags": [],
                "scores": {"urgency": {"score": 5, "label": ""},
                           "impact": {"score": 5, "label": ""},
                           "relevance": {"score": 5, "label": ""}},
                "wow_score": 5.0, "is_wow": False,
            },
            "workflow": {
                "status": "new", "priority": 5,
                "assignee": {"name": "X", "initials": "XX", "role": "Y"},
                "due_date": "2026-05-21",
                "transitions": [{"timestamp": "2026-05-19T08:00:00+00:00",
                                 "from": None, "to": "new", "by": "system", "note": ""}],
                "comments": [],
            },
            "raw_annotation": {},
        }))

    site_root = tmp_path / "site"
    n = _render_parametric_tickets(tmp_path, env, site_root, base_url="")
    assert n == 3
    for i in range(3):
        assert (site_root / "alpha" / "tickets" / f"t{i}" / "index.html").exists()


def test_gamma_scan_loads_all_three_slices(tmp_path) -> None:
    """generate.py's _load_gamma_scan_bundle returns all scans, not just one."""
    import json as _json

    from build.generate import _load_gamma_scan_bundle

    scan_dir = tmp_path / "build" / "page_data" / "gamma" / "pre-listing-scans"
    scan_dir.mkdir(parents=True)
    for i, name in enumerate(("a", "b", "c")):
        (scan_dir / f"{name}.json").write_text(_json.dumps({
            "id": name, "title": f"Scan {i}",
            "resolution_criteria": "",
            "platform_hint": "kalshi", "severity": 1,
            "severity_breakdown": {"matching_events_count": 0,
                                   "max_urgency": 0,
                                   "top_entity": ""},
            "extracted_entities": [],
            "recent_events": [],
            "warnings": [],
        }))

    bundle = _load_gamma_scan_bundle(tmp_path)
    assert len(bundle["scans"]) == 3
    assert {s["id"] for s in bundle["scans"]} == {"a", "b", "c"}


def test_render_parametric_generalized(tmp_path) -> None:
    """_render_parametric handles any slice-dir + template combo."""
    import json as _json
    from pathlib import Path as _P

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    from build.generate import _render_parametric

    REPO = _P(__file__).resolve().parent.parent
    env = Environment(
        loader=FileSystemLoader(REPO / "build" / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    pd = tmp_path / "build" / "page_data" / "gamma" / "contracts"
    pd.mkdir(parents=True)
    for i, name in enumerate(("a", "b")):
        (pd / f"{name}.json").write_text(_json.dumps({
            "scene": {"number": 2, "letter": "γ", "back_label": "← Back", "back_href": "../"},
            "contract": {
                "id": name, "platform": "kalshi", "kind": "active",
                "title": f"C{i}", "external_id": "X",
                "status": "active", "listed_at": "", "expires_at": "", "resolved_at": "",
                "resolution_criteria": "RC", "settlement_entities": [],
                "source_urls": [], "primary_source_url": "",
                "heat": 0, "heat_history": [0]*14,
                "conditions": [], "narrative": "",
            },
            "timeline": [], "open_tickets": [],
            "heat_panel": {
                "value": 0, "tier": "dormant", "delta_7d": 0,
                "peer_percentile": 0, "urgency_weighted_sparkline": [0]*14,
                "primary_drivers": [], "explainer": "",
            },
        }))

    site = tmp_path / "site"
    n = _render_parametric(tmp_path, env, site, "",
                           template_path="gamma/contract_detail.html",
                           slice_dir_relative="gamma/contracts",
                           site_subpath="gamma/contracts")
    assert n == 2
    assert (site / "gamma" / "contracts" / "a" / "index.html").exists()
    assert (site / "gamma" / "contracts" / "b" / "index.html").exists()
