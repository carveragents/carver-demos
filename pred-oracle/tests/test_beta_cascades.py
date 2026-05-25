"""Tests for build/beta_cascades.py."""
import json
from datetime import date
from pathlib import Path

import yaml


def _write_cascades(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1,
        "cascades": [{
            "id": "rule-1", "body": "FATF", "body_acronym": "FATF",
            "trigger_title": "Trigger", "trigger_pub_date": "2025-11-20",
            "trigger_url": "https://x", "rationale": "R",
            "follow_window_days": 540,
            "historical_hit_rate": "31/39 (79%)",
            "member_jurisdictions": ["FR", "AU", "BR", "IN", "ZA"],
        }],
    }))


def _write_curation(p: Path, featured_ids) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "build_date": "2026-05-19",
        "platform_footprint": "polymarket",
        "retrospective_focus": {"country_code": "FR", "title": "T",
                                 "narrative_window_months": 18,
                                 "annotation_callouts": []},
        "featured_cascade_ids": featured_ids,
        "watch_list_picks": [],
        "report_window": {"start": "2026-04-01", "end": "2026-06-30", "label": "Q2"},
    }))


def _write_footprint(p: Path) -> None:
    p.write_text(yaml.safe_dump({
        "schema_version": 1, "platform": "polymarket",
        "operating":   [{"code": "AU"}, {"code": "BR"}, {"code": "IN"}],
        "considering": [{"code": "ZA"}],
        "closed":      [{"code": "FR", "closed_at": "2025-12-15"}],
    }))


def test_cascades_emit_one_card_per_featured(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    assert len(doc["cascades"]) == 1
    card = doc["cascades"][0]
    assert card["id"] == "rule-1"
    assert card["body_acronym"] == "FATF"
    # Hit-rate string parsed into structured fields for template rendering.
    assert card["hit_rate_adopted"] == 31
    assert card["hit_rate_total"] == 39
    assert card["hit_rate_pct"] == 79


def test_cascade_members_tagged_by_role(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    members = doc["cascades"][0]["members"]
    by_code = {m["code"]: m["role"] for m in members}
    assert by_code["AU"] == "operating"
    assert by_code["BR"] == "operating"
    assert by_code["ZA"] == "considering"
    assert by_code["FR"] == "closed"
    assert by_code["IN"] == "operating"


def test_cascade_expected_action_date(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    # 2025-11-20 + 540 days = 2027-05-14
    assert doc["cascades"][0]["expected_action_by"] == "2027-05-14"


def test_cascade_footprint_overlap_count(tmp_path: Path) -> None:
    from build.beta_cascades import generate

    cascades_yml = tmp_path / "cascades.yml"
    curation = tmp_path / "beta-curation.yml"
    foot = tmp_path / "footprint.yml"
    out = tmp_path / "cascades.json"

    _write_cascades(cascades_yml)
    _write_curation(curation, ["rule-1"])
    _write_footprint(foot)

    generate(cascades_path=cascades_yml, curation_path=curation,
             footprint_path=foot, out_path=out, today=date(2026, 5, 19))
    doc = json.loads(out.read_text())
    # Operating: AU, BR, IN (3) + Considering: ZA (1) = 4
    assert doc["cascades"][0]["footprint_overlap_count"] == 4
