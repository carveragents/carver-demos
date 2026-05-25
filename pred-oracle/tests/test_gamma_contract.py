"""Tests for build/gamma_contract.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_gamma_curation(p, picks=None, tickets=None) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "featured_kalshi": [],
        "featured_polymarket": [],
        "pre_listing_scans": [],
        "contract_detail_picks": picks or [],
        "synthetic_listing_risk_tickets": tickets or [],
    }))


def _write_kalshi_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def _write_polymarket_contracts(p, picks) -> None:
    p.write_text(yaml.safe_dump({"schema_version": 1, "picks": picks}))


def _write_retro(path: Path, **fields) -> None:
    """Write a hand-curated retrospective YAML."""
    base = {
        "schema_version": 1,
        "kind": "retrospective",
        "platform": "kalshi",
        "id": "x",
        "title": "Retro T",
        "resolution_criteria": "RC",
        "listed_at": "2025-01-01",
        "resolved_at": "2025-04-30",
        "status": "resolved",
        "resolution_outcome": "NO",
        "settlement_entities": ["FCC", "ByteDance"],
        "source_urls": ["https://web.archive.org/web/2025"],
        "source_retrieved_at": "2026-05-20",
    }
    base.update(fields)
    path.write_text(yaml.safe_dump(base))


def test_contract_detail_active_writes_slice(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur, picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1", "source_lookup": {"event_ticker": "KX1"},
        "cached": {"title": "K1", "status": "active",
                   "settlement_entities": ["SEC"], "external_id": "KX1"},
    }])
    _write_polymarket_contracts(polymarket_yml, [])

    paths = generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=tmp_path / "retros",
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    assert len(paths) == 1
    doc = json.loads((out_dir / "k1.json").read_text())
    assert doc["contract"]["id"] == "k1"
    assert doc["contract"]["kind"] == "active"


def test_contract_detail_retrospective_reads_yaml(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)
    _write_retro(retros_root / "kalshi" / "contracts" / "ttb.yml", id="ttb",
                 title="TikTok Ban", settlement_entities=["FCC", "ByteDance"],
                 listed_at="2025-01-01", resolved_at="2026-05-30")

    _write_corpus(corpus, [
        make_row(entities=["ByteDance"], title="ByteDance disclosure",
                 pub_date="2026-05-19")
    ])
    _write_gamma_curation(
        gamma_cur, picks=[{"id": "ttb", "platform": "kalshi", "kind": "retrospective"}],
    )
    _write_kalshi_contracts(kalshi_yml, [])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=retros_root,
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    doc = json.loads((out_dir / "ttb.json").read_text())
    assert doc["contract"]["kind"] == "retrospective"
    assert doc["contract"]["title"] == "TikTok Ban"
    titles = [e["title"] for e in doc["timeline"]]
    assert "ByteDance disclosure" in titles


def test_contract_detail_timeline_includes_only_matching(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"

    _write_corpus(corpus, [
        make_row(entities=["SEC"], title="In scope SEC"),
        make_row(feed_entry_id="r2", entities=["FDA"], title="Out of scope FDA"),
    ])
    _write_gamma_curation(gamma_cur, picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1", "source_lookup": {"event_ticker": "KX1"},
        "cached": {"title": "K1", "status": "active",
                   "settlement_entities": ["SEC"], "external_id": "KX1"},
    }])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=tmp_path / "retros",
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    doc = json.loads((out_dir / "k1.json").read_text())
    titles = [e["title"] for e in doc["timeline"]]
    assert "In scope SEC" in titles
    assert "Out of scope FDA" not in titles


def test_contract_detail_open_tickets_marked_demo(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    polymarket_yml = tmp_path / "polymarket.yml"
    out_dir = tmp_path / "contracts"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_gamma_curation(gamma_cur,
                          picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}],
                          tickets=[{"contract_id": "k1", "summary": "Watch",
                                    "severity": "high", "assignee_initials": "MV"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1", "source_lookup": {"event_ticker": "KX1"},
        "cached": {"title": "K1", "status": "active",
                   "settlement_entities": ["SEC"], "external_id": "KX1"},
    }])
    _write_polymarket_contracts(polymarket_yml, [])

    generate(
        corpus_path=corpus, gamma_curation_path=gamma_cur,
        kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=polymarket_yml,
        retrospectives_root=tmp_path / "retros",
        out_dir=out_dir, today=date(2026, 5, 19),
    )
    doc = json.loads((out_dir / "k1.json").read_text())
    assert len(doc["open_tickets"]) == 1
    assert doc["open_tickets"][0]["is_demo"] is True
    assert doc["open_tickets"][0]["assignee_initials"] == "MV"


def test_retrospective_excludes_events_past_resolved_at(tmp_path: Path) -> None:
    """Retrospective contracts must not show timeline events after resolved_at."""
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_dir = tmp_path / "contracts"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)
    _write_retro(retros_root / "kalshi" / "contracts" / "ttb.yml",
                 id="ttb", title="TikTok Ban",
                 settlement_entities=["TikTok"],
                 listed_at="2024-04-24",
                 resolved_at="2025-04-30")

    _write_corpus(corpus, [
        make_row(entities=["TikTok"], title="In window", pub_date="2025-03-01"),
        make_row(entities=["TikTok"], title="Too early", pub_date="2023-01-01"),
        make_row(entities=["TikTok"], title="After resolution", pub_date="2025-12-01"),
    ])
    _write_gamma_curation(gamma_cur,
        picks=[{"id": "ttb", "platform": "kalshi", "kind": "retrospective"}])
    _write_kalshi_contracts(kalshi_yml, [])
    poly_yml.write_text("schema_version: 1\npicks: []\n")

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=poly_yml,
             retrospectives_root=retros_root, out_dir=out_dir,
             today=date(2026, 5, 20))

    doc = json.loads((out_dir / "ttb.json").read_text())
    titles = [ev["title"] for ev in doc["timeline"]]
    assert "In window" in titles
    assert "Too early" not in titles
    assert "After resolution" not in titles


def test_active_excludes_events_before_lead_in(tmp_path: Path) -> None:
    from build.gamma_contract import generate

    corpus = tmp_path / "artifacts.jsonl"
    gamma_cur = tmp_path / "gamma-curation.yml"
    kalshi_yml = tmp_path / "kalshi.yml"
    poly_yml = tmp_path / "poly.yml"
    out_dir = tmp_path / "contracts"
    retros_root = tmp_path / "retros"
    (retros_root / "kalshi" / "contracts").mkdir(parents=True)

    _write_corpus(corpus, [
        make_row(entities=["FOMC"], title="In window", pub_date="2026-04-01"),
        make_row(entities=["FOMC"], title="Too early", pub_date="2025-01-01"),
    ])
    _write_gamma_curation(gamma_cur,
        picks=[{"id": "k1", "platform": "kalshi", "kind": "active"}])
    _write_kalshi_contracts(kalshi_yml, [{
        "id": "k1",
        "cached": {"title": "T", "ticker": "K1", "status": "active",
                   "listed_at": "2026-02-01", "expires_at": "2026-12-31",
                   "resolution_criteria": "r",
                   "settlement_entities": ["FOMC"]},
    }])
    poly_yml.write_text("schema_version: 1\npicks: []\n")

    generate(corpus_path=corpus, gamma_curation_path=gamma_cur,
             kalshi_contracts_path=kalshi_yml, polymarket_contracts_path=poly_yml,
             retrospectives_root=retros_root, out_dir=out_dir,
             today=date(2026, 5, 20))

    doc = json.loads((out_dir / "k1.json").read_text())
    titles = [ev["title"] for ev in doc["timeline"]]
    assert "In window" in titles
    assert "Too early" not in titles
