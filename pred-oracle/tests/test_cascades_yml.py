"""Validate data/cascades.yml shape."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CASCADES = REPO / "data" / "cascades.yml"


def test_cascades_file_exists() -> None:
    assert CASCADES.exists()


def test_cascades_schema() -> None:
    doc = yaml.safe_load(CASCADES.read_text())
    assert doc["schema_version"] == 1
    assert isinstance(doc["cascades"], list) and len(doc["cascades"]) >= 3
    for c in doc["cascades"]:
        assert {"id", "body", "trigger_title", "trigger_pub_date",
                "trigger_url", "rationale", "member_jurisdictions",
                "follow_window_days", "historical_hit_rate"} <= set(c)
        assert isinstance(c["member_jurisdictions"], list) and len(c["member_jurisdictions"]) >= 5
        assert 30 <= c["follow_window_days"] <= 730
        # Hit rate is "<hits>/<total> (<pct>%)"
        assert "/" in c["historical_hit_rate"]
        # Source-of-truth: every cascade has a primary-source URL on the trigger
        assert c["trigger_url"].startswith("https://")


def test_cascade_ids_unique() -> None:
    doc = yaml.safe_load(CASCADES.read_text())
    ids = [c["id"] for c in doc["cascades"]]
    assert len(set(ids)) == len(ids)
