"""Tests for build/beta_heatmap.py."""
import json
from datetime import date
from pathlib import Path

import yaml

from tests.conftest import make_row


def _write_corpus(p: Path, rows) -> None:
    p.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "build_date": "2026-05-19",
        "platform_footprint": "polymarket",
        "retrospective_focus": {
            "country_code": "FR",
            "title": "France — retrospective",
            "narrative_window_months": 18,
            "annotation_callouts": [
                {"date": "2025-12-10", "label": "Public restriction"},
            ],
        },
        "featured_cascade_ids": ["a", "b", "c"],
        "watch_list_picks": [],
        "report_window": {"start": "2026-04-01", "end": "2026-06-30", "label": "Q2"},
    }))


def _write_footprint(p: Path, platform: str) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "platform": platform,
        "operating": [{"code": "US"}],
        "considering": [{"code": "BR"}],
        "closed": [{"code": "FR", "closed_at": "2025-12-15", "reason": "..."}],
    }))


def test_heatmap_aggregates_world_records(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [
        make_row(topic_jurisdiction_code="FR", title="FR1"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", title="FR2"),
        make_row(feed_entry_id="r3", topic_jurisdiction_code="DE", title="DE1"),
    ])
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out,
             today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    codes = {row["code"]: row for row in doc["world_aggregates"]}
    assert codes["FR"]["count"] == 2
    assert codes["DE"]["count"] == 1


def test_heatmap_excludes_us_states_from_world(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [
        make_row(topic_jurisdiction_code="US-CA", title="CA1"),
        make_row(feed_entry_id="r2", topic_jurisdiction_code="FR", title="FR1"),
    ])
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    world_codes = {row["code"] for row in doc["world_aggregates"]}
    state_codes = {row["code"] for row in doc["us_state_aggregates"]}
    assert "FR" in world_codes
    assert "US-CA" not in world_codes
    assert "US-CA" in state_codes


def test_heatmap_carries_retrospective_payload(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="FR", title="FR")] * 5)
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    retro = doc["retrospective_focus"]
    assert retro["code"] == "FR"
    assert isinstance(retro["weekly_buckets"], list) and len(retro["weekly_buckets"]) == 78
    assert isinstance(retro["top_events"], list)
    assert isinstance(retro["annotation_callouts"], list)


def test_heatmap_includes_footprint(tmp_path: Path) -> None:
    from build.beta_heatmap import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "heatmap.json"

    _write_corpus(corpus, [make_row(topic_jurisdiction_code="FR", title="FR")])
    _write_curation(curation)
    _write_footprint(foot, "polymarket")

    generate(corpus_path=corpus, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    footprint = doc["platform_footprint"]
    assert footprint["active_platform"] == "polymarket"
    assert {p["code"] for p in footprint["closed"]} == {"FR"}
