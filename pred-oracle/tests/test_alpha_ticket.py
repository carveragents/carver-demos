"""Tests for build/alpha_ticket.py — parametric ticket-detail generator."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _row(**ov) -> dict:
    """Ticket-specific row with fields needed for the wow-ticket scenario."""
    defaults = {
        "feed_entry_id": "f-wow",
        "title": "CFTC Sues Minnesota",
        "link": "https://www.cftc.gov/x",
        "regulator_name": "CFTC",
        "regulator_division": "Division of Enforcement",
        "classification_base_url": "cftc.gov",
        "topic_name": "CFTC",
        "topic_jurisdiction_code": "US",
        "update_type": "enforcement",
        "update_subtype": "enforcement_agency",
        "pub_date": "2026-05-19",
        "pub_date_valid": True,
        "critical_dates": {
            "effective_date": "2026-06-01",
            "compliance_date": "",
            "comment_deadline": "",
        },
        "impacted_business": {"jurisdiction": ["US", "US-MN"], "industry": ["Derivatives"]},
        "scores": {
            "urgency": {"score": 9, "label": "high"},
            "impact": {"score": 9, "label": "high"},
            "relevance": {"score": 9, "label": "high"},
        },
        "impact_summary": {
            "what_changed": "CFTC sued.",
            "why_it_matters": "Event contracts.",
            "key_requirements": ["Comply.", "Report."],
            "objective": "Block state action.",
            "risk_impact": "high",
        },
        "penalties_consequences": ["Injunction"],
        "reg_references": {
            "statutes": ["CEA"], "rules": [], "past_release": [], "precedents": [], "personnel": [],
        },
        "entities": ["Minnesota AG"],
        "tags": ["CFTC", "Minnesota"],
        "jurisdiction_tier": {"label": "us_federal", "tier": 1},
    }
    defaults.update(ov)
    return make_row(**defaults)


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "wow_ticket_id": "f-wow",
        "supporting_ticket_ids": ["f-sup-1", "f-sup-2", "f-sup-3", "f-sup-4"],
        "dashboard_window_days": 90,
        "inbox_top_n": 15,
        "persona_key": "gc",
        "synthetic_assignees": [
            {"name": "Sara Chen", "role": "GC", "initials": "SC"},
            {"name": "Devin Liu", "role": "Associate", "initials": "DL"},
        ],
        "synthetic_comment_templates": [
            {"author": "Sara Chen", "role": "GC",
             "text": "Memo by EOD please — {regulator} matters.",
             "timestamp_offset_hours": -4},
            {"author": "Devin Liu", "role": "Associate",
             "text": "Pulling precedents.", "timestamp_offset_hours": -2},
        ],
    }))


def test_generates_5_slices(tmp_path: Path) -> None:
    from build.alpha_ticket import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out_dir = tmp_path / "tickets"
    out_dir.mkdir()

    _write_corpus(corpus, [
        _row(feed_entry_id="f-wow"),
        _row(feed_entry_id="f-sup-1", title="Sup 1"),
        _row(feed_entry_id="f-sup-2", title="Sup 2"),
        _row(feed_entry_id="f-sup-3", title="Sup 3"),
        _row(feed_entry_id="f-sup-4", title="Sup 4"),
    ])
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))

    files = sorted(out_dir.glob("*.json"))
    assert len(files) == 5
    assert (out_dir / "f-wow.json").exists()


def test_ticket_schema_contains_required_fields(tmp_path: Path) -> None:
    from build.alpha_ticket import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out_dir = tmp_path / "tickets"
    out_dir.mkdir()

    _write_corpus(corpus, [_row(feed_entry_id="f-wow")] + [
        _row(feed_entry_id=f"f-sup-{i}", title=f"S{i}") for i in range(1, 5)
    ])
    _write_curation(curation)
    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))

    doc = json.loads((out_dir / "f-wow.json").read_text())
    assert doc["ticket"]["id"] == "f-wow"
    assert doc["ticket"]["title"] == "CFTC Sues Minnesota"
    assert doc["ticket"]["link"] == "https://www.cftc.gov/x"
    assert doc["ticket"]["regulator"]["name"] == "CFTC"
    assert doc["ticket"]["regulator"]["division"] == "Division of Enforcement"
    assert doc["ticket"]["update_type"] == "enforcement"
    assert doc["ticket"]["effective_date"] == "2026-06-01"
    assert doc["ticket"]["compliance_date"] is None
    assert doc["ticket"]["what_changed"] == "CFTC sued."
    assert doc["ticket"]["is_wow"] is True
    assert "Comply." in doc["ticket"]["key_requirements"]
    assert "precedents" in doc["ticket"]["reg_references"]


def test_synthetic_workflow_block(tmp_path: Path) -> None:
    from build.alpha_ticket import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out_dir = tmp_path / "tickets"
    out_dir.mkdir()

    _write_corpus(corpus, [_row(feed_entry_id="f-wow")] + [
        _row(feed_entry_id=f"f-sup-{i}") for i in range(1, 5)
    ])
    _write_curation(curation)
    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))

    doc = json.loads((out_dir / "f-wow.json").read_text())
    assert doc["workflow"]["status"] in {"new", "acknowledged", "in_review", "drafted"}
    assert isinstance(doc["workflow"]["priority"], int)
    assert 1 <= doc["workflow"]["priority"] <= 10
    assert doc["workflow"]["assignee"]["initials"] in {"SC", "DL"}
    assert len(doc["workflow"]["transitions"]) >= 1
    assert len(doc["workflow"]["comments"]) >= 1
    # Comment text interpolation
    assert "CFTC matters" in doc["workflow"]["comments"][0]["text"]


def test_skips_missing_corpus_records(tmp_path: Path) -> None:
    """If a curated id is not in the corpus, log + skip; don't crash."""
    from build.alpha_ticket import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out_dir = tmp_path / "tickets"
    out_dir.mkdir()

    _write_corpus(corpus, [_row(feed_entry_id="f-wow")])  # only wow exists
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_dir=out_dir,
             today=date(2026, 5, 19))

    files = sorted(out_dir.glob("*.json"))
    assert len(files) == 1
    assert files[0].name == "f-wow.json"
