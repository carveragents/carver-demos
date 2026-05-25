"""Validate data/platforms/*/footprint.yml shape."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PLATFORMS = ["kalshi", "polymarket"]


def test_each_platform_has_footprint() -> None:
    for p in PLATFORMS:
        path = REPO / "data" / "platforms" / p / "footprint.yml"
        assert path.exists(), f"missing {path}"


def test_footprint_shape() -> None:
    for p in PLATFORMS:
        doc = yaml.safe_load((REPO / "data" / "platforms" / p / "footprint.yml").read_text())
        assert doc["schema_version"] == 1
        assert doc["platform"] == p
        for k in ("operating", "considering", "closed"):
            assert isinstance(doc[k], list)
            for item in doc[k]:
                assert isinstance(item, dict)
                assert "code" in item
                # closed entries should record a date for the heat-map annotation
                if k == "closed":
                    assert "closed_at" in item


def test_polymarket_includes_france_closed() -> None:
    doc = yaml.safe_load((REPO / "data" / "platforms" / "polymarket" / "footprint.yml").read_text())
    closed_codes = {e["code"] for e in doc["closed"]}
    assert "FR" in closed_codes, "France must be on Polymarket closed list per spec §2.2"
