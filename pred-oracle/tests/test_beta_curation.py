"""Validate data/beta-curation.yml shape."""
import datetime as _dt
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "beta-curation.yml"


def test_curation_file_exists() -> None:
    assert CURATION.exists()


def test_curation_schema() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    assert doc["schema_version"] == 1
    _dt.date.fromisoformat(doc["build_date"])
    assert doc["platform_footprint"] in {"polymarket", "kalshi"}
    assert isinstance(doc["retrospective_focus"], dict)
    assert {"country_code", "title", "narrative_window_months"} <= set(doc["retrospective_focus"])
    assert isinstance(doc["featured_cascade_ids"], list) and len(doc["featured_cascade_ids"]) >= 3
    assert isinstance(doc["watch_list_picks"], list) and len(doc["watch_list_picks"]) == 3
    for w in doc["watch_list_picks"]:
        assert {"country_code", "label", "rationale", "recommended_actions"} <= set(w)
        assert isinstance(w["recommended_actions"], list) and len(w["recommended_actions"]) >= 1
    assert isinstance(doc["report_window"], dict)
    assert {"start", "end", "label"} <= set(doc["report_window"])


def test_watch_list_country_codes_unique() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    codes = [w["country_code"] for w in doc["watch_list_picks"]]
    assert len(set(codes)) == len(codes)
