"""Tests for build/beta_report.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "build_date": "2026-05-19",
        "platform_footprint": "polymarket",
        "retrospective_focus": {"country_code": "FR", "title": "T",
                                 "narrative_window_months": 18,
                                 "annotation_callouts": []},
        "featured_cascade_ids": ["rule-1"],
        "watch_list_picks": [
            {"country_code": "BR", "label": "Brazil",
             "rationale": "R", "recommended_actions": ["A1"]},
            {"country_code": "SG", "label": "Singapore",
             "rationale": "R", "recommended_actions": ["A1"]},
            {"country_code": "AU", "label": "Australia",
             "rationale": "R", "recommended_actions": ["A1"]},
        ],
        "report_window": {"start": "2026-04-01", "end": "2026-06-30",
                           "label": "Q2 2026"},
    }))


def _write_footprint(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "platform": "polymarket",
        "operating": [{"code": "BR"}, {"code": "AU"}],
        "considering": [{"code": "SG"}],
        "closed": [{"code": "FR", "closed_at": "2025-12-15"}],
    }))


def _write_cascades(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "cascades": [{
            "id": "rule-1", "body": "FATF", "body_acronym": "FATF",
            "trigger_title": "T", "trigger_pub_date": "2025-11-20",
            "trigger_url": "https://x", "rationale": "R",
            "follow_window_days": 540,
            "historical_hit_rate": "31/39 (79%)",
            "member_jurisdictions": ["BR", "AU", "SG", "FR"],
        }],
    }))


def test_report_emits_full_schema(tmp_path: Path) -> None:
    from build.beta_report import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    cascades = tmp_path / "cascades.yml"
    out = tmp_path / "report.json"

    _write_corpus(corpus, [
        make_row(topic_jurisdiction_code="BR", title="BR1"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="BR", title="BR2"),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="AU", title="AU1"),
    ])
    _write_curation(curation)
    _write_footprint(foot)
    _write_cascades(cascades)

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, cascades_path=cascades,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    for key in ("headline_stats", "pressure_rising", "pressure_easing",
                "watch_list", "featured_cascades", "method_notes",
                "watch_list_disclaimer", "v1_footer", "pdf_href"):
        assert key in doc, f"missing {key}"


def test_report_watch_list_size_three(tmp_path: Path) -> None:
    from build.beta_report import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    cascades = tmp_path / "cascades.yml"
    out = tmp_path / "report.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="BR")])
    _write_curation(curation)
    _write_footprint(foot)
    _write_cascades(cascades)

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, cascades_path=cascades,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert len(doc["watch_list"]) == 3
    assert all("recommended_actions" in w for w in doc["watch_list"])


def test_report_pdf_href_points_to_sample(tmp_path: Path) -> None:
    from build.beta_report import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    cascades = tmp_path / "cascades.yml"
    out = tmp_path / "report.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="BR")])
    _write_curation(curation)
    _write_footprint(foot)
    _write_cascades(cascades)

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, cascades_path=cascades,
             out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert "q2-2026-report.pdf" in doc["pdf_href"]
