"""Tests for build/alpha_dashboard.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _row(**ov) -> dict:
    """Dashboard-specific row defaulting to US-CA jurisdiction."""
    defaults = {
        "feed_entry_id": "f",
        "impacted_business": {"jurisdiction": ["US-CA"]},
        "scores": {"urgency": {"score": 7}, "impact": {"score": 7}, "relevance": {"score": 7}},
    }
    defaults.update(ov)
    return make_row(**defaults)


def _write_corpus(p, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p, window_days=90) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "wow_ticket_id": "f-wow",
        "supporting_ticket_ids": ["f-1", "f-2", "f-3", "f-4"],
        "dashboard_window_days": window_days,
        "inbox_top_n": 15,
        "persona_key": "gc",
        "synthetic_assignees": [],
        "synthetic_comment_templates": [],
    }))


def test_dashboard_aggregates_us_states(tmp_path: Path) -> None:
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    _write_corpus(corpus, [
        _row(impacted_business={"jurisdiction": ["US-CA"]}),
        _row(impacted_business={"jurisdiction": ["US-CA"]}),
        _row(impacted_business={"jurisdiction": ["US-NY"]}),
        _row(impacted_business={"jurisdiction": ["US-CA", "US-NY"]}),
        _row(impacted_business={"jurisdiction": ["GB"]}),
    ])
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    states = {s["code"]: s["count"] for s in doc["us_states"]}
    assert states["CA"] == 3
    assert states["NY"] == 2
    assert "GB" not in states


def test_dashboard_window_filters_old_records(tmp_path: Path) -> None:
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    _write_corpus(corpus, [
        _row(pub_date="2026-05-19", impacted_business={"jurisdiction": ["US-CA"]}),  # 0 days
        _row(pub_date="2026-02-18", impacted_business={"jurisdiction": ["US-NY"]}),  # 90 days
        _row(pub_date="2025-01-01", impacted_business={"jurisdiction": ["US-TX"]}),  # >90
    ])
    _write_curation(curation, window_days=90)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    states = {s["code"] for s in doc["us_states"]}
    assert "CA" in states
    assert "NY" in states
    assert "TX" not in states


def test_dashboard_top_10_sorted_by_count(tmp_path: Path) -> None:
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    rows = []
    rows += [_row(impacted_business={"jurisdiction": ["US-CA"]}) for _ in range(10)]
    rows += [_row(impacted_business={"jurisdiction": ["US-NY"]}) for _ in range(5)]
    rows += [_row(impacted_business={"jurisdiction": ["US-TX"]}) for _ in range(3)]
    _write_corpus(corpus, rows)
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    top = [r["code"] for r in doc["top_10"]]
    assert top[0] == "US-CA"
    assert top[1] == "US-NY"
    assert top[2] == "US-TX"


def test_dashboard_update_types_present(tmp_path: Path) -> None:
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    _write_corpus(corpus, [
        _row(update_type="enforcement"),
        _row(update_type="advisory"),
        _row(update_type="enforcement"),
    ])
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    types = {t["label"]: t["count"] for t in doc["update_types"]}
    assert types["enforcement"] == 2
    assert types["advisory"] == 1


def test_dashboard_bare_state_code_counts_as_state(tmp_path: Path) -> None:
    """Bare 'CA' must count as US-CA, not international."""
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    _write_corpus(corpus, [
        _row(impacted_business={"jurisdiction": ["US-CA"]}),
        _row(impacted_business={"jurisdiction": ["CA"]}),  # bare — also CA
        _row(impacted_business={"jurisdiction": ["GB"]}),  # real intl
    ])
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    states = {s["code"]: s["count"] for s in doc["us_states"]}
    intl = {i["code"] for i in doc["international"]}
    assert states["CA"] == 2, "Bare CA should be merged into US-CA count"
    assert "CA" not in intl, "California must NOT appear in international list"
    # GB appears only if it reaches the >= 5 threshold; with 1 record it shouldn't
    assert "GB" not in intl  # threshold is >= 5


def test_dashboard_excludes_website_error(tmp_path: Path) -> None:
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    _write_corpus(corpus, [
        _row(update_type="enforcement"),
        _row(update_type="website error", impacted_business={"jurisdiction": ["US-FL"]}),
    ])
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    types = {t["label"] for t in doc["update_types"]}
    assert "website error" not in types
    codes = {s["code"] for s in doc["us_states"]}
    assert "FL" not in codes


def test_dashboard_territories_resolve_to_full_names(tmp_path: Path) -> None:
    """US territories (PR, VI, GU, AS, MP) get full labels, not raw codes."""
    from build.alpha_dashboard import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "curation.yml"
    out = tmp_path / "dashboard.json"

    _write_corpus(corpus, [
        make_row(impacted_business={"jurisdiction": ["US-PR"]}),
        make_row(impacted_business={"jurisdiction": ["VI"]}),  # bare → US-VI
    ])
    _write_curation(curation)

    generate(corpus_path=corpus, curation_path=curation, out_path=out,
             today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    labels = {s["code"]: s["label"] for s in doc["us_states"]}
    assert labels["PR"] == "Puerto Rico"
    assert labels["VI"] == "U.S. Virgin Islands"
