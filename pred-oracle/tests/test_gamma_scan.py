"""Tests for build/gamma_scan.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path, scans) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "featured_kalshi": [],
        "featured_polymarket": [],
        "pre_listing_scans": scans,
        "contract_detail_picks": [],
        "synthetic_listing_risk_tickets": [],
    }))


def test_scan_generation_produces_one_file_per_scan(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [make_row(entities=["SEC"])])
    _write_curation(curation, [
        {"id": "s1", "title": "T1", "resolution_criteria": "RC", "platform_hint": "kalshi",
         "settlement_entities": ["SEC"], "severity_hint": 7},
        {"id": "s2", "title": "T2", "resolution_criteria": "RC", "platform_hint": "polymarket",
         "settlement_entities": ["FDA"], "severity_hint": 5},
    ])

    written = generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
                       today=date(2026, 5, 19))
    assert len(written) == 2
    assert (out_dir / "s1.json").exists()
    assert (out_dir / "s2.json").exists()


def test_scan_results_include_matching_recent_event(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [
        make_row(feed_entry_id="f1", entities=["U.S. Securities and Exchange Commission"],
                 title="SEC adopts thing", pub_date="2026-05-19"),
        make_row(feed_entry_id="f2", entities=["FDA"], title="Off-topic FDA"),
    ])
    _write_curation(curation, [{
        "id": "sec-scan", "title": "T", "resolution_criteria": "RC", "platform_hint": "polymarket",
        "settlement_entities": ["U.S. Securities and Exchange Commission"], "severity_hint": 6,
    }])

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))
    doc = json.loads((out_dir / "sec-scan.json").read_text())
    titles = [e["title"] for e in doc["recent_events"]]
    assert "SEC adopts thing" in titles
    assert "Off-topic FDA" not in titles


def test_scan_severity_breakdown_populated(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [
        make_row(
            entities=["SEC"],
            title="High urgency SEC",
            scores={"urgency": {"score": 9}, "impact": {"score": 7}, "relevance": {"score": 8}},
        ),
        make_row(
            feed_entry_id="r2",
            entities=["SEC"],
            title="Lower urgency SEC",
            scores={"urgency": {"score": 7}, "impact": {"score": 7}, "relevance": {"score": 7}},
        ),
    ])
    _write_curation(curation, [{
        "id": "sec-scan", "title": "T", "resolution_criteria": "RC", "platform_hint": "polymarket",
        "settlement_entities": ["SEC"], "severity_hint": 7,
    }])

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))
    doc = json.loads((out_dir / "sec-scan.json").read_text())
    assert doc["severity_breakdown"]["matching_events_count"] == 2
    assert doc["severity_breakdown"]["max_urgency"] == 9.0


def test_scan_warns_when_no_matches(tmp_path: Path) -> None:
    from build.gamma_scan import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "gamma-curation.yml"
    out_dir = tmp_path / "pre-listing-scans"

    _write_corpus(corpus, [make_row(entities=["FDA"])])
    _write_curation(curation, [{
        "id": "sec-scan", "title": "T", "resolution_criteria": "RC", "platform_hint": "polymarket",
        "settlement_entities": ["SEC"], "severity_hint": 7,
    }])

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))
    doc = json.loads((out_dir / "sec-scan.json").read_text())
    assert doc["recent_events"] == []
    assert any("no matching" in w.lower() for w in doc["warnings"])
