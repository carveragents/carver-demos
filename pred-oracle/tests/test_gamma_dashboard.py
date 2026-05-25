"""Tests for build/gamma_dashboard.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_gamma_curation(p, contract_detail_picks=None, picks=None) -> None:
    # `picks` is an alias for `contract_detail_picks` for convenience
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "featured_kalshi": [],
        "featured_polymarket": [],
        "pre_listing_scans": [],
        "contract_detail_picks": picks if picks is not None else (contract_detail_picks or []),
        "synthetic_listing_risk_tickets": [],
    }))


def _write_retro(p, **kwargs) -> None:
    base = {"schema_version": 1, "kind": "retrospective", "platform": "kalshi",
            "title": "T", "resolution_criteria": "r", "status": "resolved",
            "listed_at": "2025-01-01", "resolved_at": "2025-12-31",
            "settlement_entities": [], "source_urls": []}
    base.update(kwargs)
    p.write_text(yaml.safe_dump(base))


def _write_kalshi_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def _write_polymarket_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def test_dashboard_emits_contracts_from_pick_lists(tmp_path: Path) -> None:
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k1", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "K1", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [
        {"id": "p1", "source_lookup": {"slug": "p1"},
         "cached": {"title": "P1", "status": "active", "settlement_entities": ["SEC"]}},
    ])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    ids = [c["id"] for c in doc["contracts"]]
    assert set(ids) == {"k1", "p1"}


def test_dashboard_includes_heat_and_sparkline(tmp_path: Path) -> None:
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    _write_corpus(corpus, [
        make_row(
            entities=["SEC"],
            pub_date="2026-05-19",
            scores={"urgency": {"score": 9}, "impact": {"score": 8}, "relevance": {"score": 8}},
        ),
        make_row(
            feed_entry_id="r2",
            entities=["SEC"],
            pub_date="2026-05-15",
            scores={"urgency": {"score": 7}, "impact": {"score": 7}, "relevance": {"score": 7}},
        ),
    ])
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k1", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "K1", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    c = doc["contracts"][0]
    assert c["heat"] > 0
    assert isinstance(c["sparkline"], list) and len(c["sparkline"]) == 14
    assert c["matching_event_count"] >= 2


def test_dashboard_excludes_stale_picks_from_active_listing(tmp_path: Path) -> None:
    """Stale contracts (upstream 404) — show only if cached is still good; flag visually."""
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k1", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "K1", "status": "active", "settlement_entities": ["SEC"]},
         "stale": True, "stale_reason": "upstream 404"},
        {"id": "k2", "source_lookup": {"event_ticker": "KX2"},
         "cached": {"title": "K2", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    by_id = {c["id"]: c for c in doc["contracts"]}
    assert by_id["k1"]["is_stale"] is True
    assert by_id["k2"]["is_stale"] is False


def test_dashboard_sorted_by_heat_desc(tmp_path: Path) -> None:
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out = tmp_path / "contracts.json"

    rows = [
        make_row(feed_entry_id=f"f{i}", entities=["SEC"], pub_date="2026-05-19")
        for i in range(5)
    ]
    _write_corpus(corpus, rows)
    _write_gamma_curation(gamma_cur)
    _write_kalshi_contracts(kalshi_yml, [
        {"id": "k-cold", "source_lookup": {"event_ticker": "KX1"},
         "cached": {"title": "Cold", "status": "active", "settlement_entities": ["FDA"]}},
        {"id": "k-hot", "source_lookup": {"event_ticker": "KX2"},
         "cached": {"title": "Hot", "status": "active", "settlement_entities": ["SEC"]}},
    ])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert doc["contracts"][0]["id"] == "k-hot"
    assert doc["contracts"][1]["id"] == "k-cold"


def test_dashboard_includes_retrospective_rows_with_resolution_window_heat(
    tmp_path: Path,
) -> None:
    """Retrospective contracts appear as rows with heat scored against their life window."""
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_path = tmp_path / "dashboard.json"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)
    _write_retro(retros_root / "kalshi" / "contracts" / "ttb.yml",
                 id="ttb", title="TikTok ban",
                 settlement_entities=["TikTok"],
                 listed_at="2024-04-24", resolved_at="2025-04-30",
                 status="resolved")
    _write_corpus(corpus, [
        make_row(entities=["TikTok"], title="In life window",
                 pub_date="2025-04-20",
                 scores={"urgency": {"score": 8, "label": "high"},
                         "impact": {"score": 7, "label": "medium"},
                         "relevance": {"score": 7, "label": "medium"}}),
        make_row(entities=["FOMC"], title="Active hit",
                 pub_date="2026-05-15"),
    ])
    _write_gamma_curation(gamma_cur,
        picks=[
            {"id": "k1", "platform": "kalshi", "kind": "active"},
            {"id": "ttb", "platform": "kalshi", "kind": "retrospective"},
        ])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1",
        "cached": {"title": "Active", "ticker": "K1", "status": "active",
                   "listed_at": "2026-01-01", "expires_at": "2026-12-31",
                   "resolution_criteria": "r", "settlement_entities": ["FOMC"]},
    }])
    poly_yml.write_text("schema_version: 1\npicks: []\n")

    result = generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
                      kalshi_contracts_path=kalshi_yml,
                      polymarket_contracts_path=poly_yml,
                      out_path=out_path, today=date(2026, 5, 20),
                      retros_root=retros_root)
    rows = result["rows"]
    actives = [r for r in rows if r["kind"] == "active"]
    retros = [r for r in rows if r["kind"] == "retrospective"]
    assert len(actives) == 1
    assert len(retros) == 1
    assert retros[0]["status"] == "resolved"
    assert retros[0]["heat_window_label"] == "at resolution"
    assert actives[0]["heat_window_label"] == "current"
    assert retros[0]["heat"] > 0  # in-life-window record drives heat
    for row in rows:
        assert row["tier"] in ("dormant", "watch", "active", "critical")


def test_dashboard_tier_consistent_with_heat_panel(tmp_path: Path) -> None:
    """Same tier_for function used for dashboard and contract detail panel."""
    from build._heat_panel import tier_for
    from build.gamma_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_path = tmp_path / "dashboard.json"
    retros_root = tmp_path / "retros"
    retros_root.mkdir()
    _write_corpus(corpus, [make_row(entities=["FOMC"], pub_date="2026-05-19")])
    _write_gamma_curation(gamma_cur,
        picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1",
        "cached": {"title": "T", "ticker": "K1", "status": "active",
                   "listed_at": "2026-01-01", "expires_at": "2026-12-31",
                   "resolution_criteria": "r", "settlement_entities": ["FOMC"]},
    }])
    poly_yml.write_text("schema_version: 1\npicks: []\n")
    result = generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
                      kalshi_contracts_path=kalshi_yml,
                      polymarket_contracts_path=poly_yml,
                      out_path=out_path, today=date(2026, 5, 20),
                      retros_root=retros_root)
    for row in result["rows"]:
        assert row["tier"] == tier_for(row["heat"])
