"""YAML seed catalogs lint + minimal structural checks."""

from pathlib import Path

import pytest
import yaml

DATA = Path(__file__).parent.parent / "data"


def test_known_regulators_loads() -> None:
    items = yaml.safe_load((DATA / "known_regulators.yml").read_text())
    assert isinstance(items, list)
    assert len(items) >= 50, f"Need >= 50 regulators per 10-data-prep §2.1; got {len(items)}"
    for item in items:
        assert "canonical_name" in item
        assert isinstance(item.get("aliases", []), list)


@pytest.mark.parametrize("platform", ["kalshi", "polymarket"])
def test_entity_catalog_well_formed(platform: str) -> None:
    items = yaml.safe_load((DATA / "platforms" / platform / "entities.yml").read_text())
    assert isinstance(items, list)
    assert 10 <= len(items) <= 30, f"{platform} entities: {len(items)} (want 10-30)"
    self_entries = [e for e in items if e.get("role") == "self"]
    assert len(self_entries) >= 1, f"{platform} catalog needs at least one role=self entry"
    for item in items:
        if item.get("role") == "staff":
            assert item.get("source"), f"Staff entry {item['canonical_name']} missing source URL"


@pytest.mark.parametrize("platform", ["kalshi", "polymarket"])
def test_jurisdictions_well_formed(platform: str) -> None:
    items = yaml.safe_load((DATA / "platforms" / platform / "jurisdictions.yml").read_text())
    assert isinstance(items, list)
    valid_statuses = {"operating", "considering", "closed", "excluded"}
    for item in items:
        assert item.get("code"), "Each jurisdiction needs an ISO code"
        assert item.get("status") in valid_statuses


@pytest.mark.parametrize("platform", ["kalshi", "polymarket"])
def test_personas_well_formed(platform: str) -> None:
    obj = yaml.safe_load((DATA / "platforms" / platform / "personas.yml").read_text())
    assert isinstance(obj, dict)
    for key in ("gc", "listing_lead", "international_lead"):
        assert key in obj, f"{platform} personas missing {key}"
        assert obj[key].get("display_name")
