from __future__ import annotations
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "trader-curation.yml"


def test_trader_curation_loads():
    doc = yaml.safe_load(CURATION.read_text())
    assert doc["schema_version"] == 1
    assert "portfolio" in doc
    assert "retrospectives" in doc


def test_portfolio_has_three_contracts():
    doc = yaml.safe_load(CURATION.read_text())
    assert len(doc["portfolio"]) == 3


def test_portfolio_entries_have_required_keys():
    doc = yaml.safe_load(CURATION.read_text())
    for entry in doc["portfolio"]:
        assert "id" in entry
        assert "platform" in entry
        assert entry["platform"] in ("kalshi", "polymarket")
        assert "kind" in entry
        assert "position" in entry
        pos = entry["position"]
        assert pos["side"] in ("YES", "NO")
        assert isinstance(pos["size"], int)
        assert isinstance(pos["entry_price"], (int, float))


def test_retrospectives_has_two_entries():
    doc = yaml.safe_load(CURATION.read_text())
    assert len(doc["retrospectives"]) == 2


def test_all_portfolio_contracts_exist_in_contracts_yml():
    """Every active portfolio entry must exist in a contracts.yml picks list."""
    doc = yaml.safe_load(CURATION.read_text())
    kalshi = yaml.safe_load(
        (REPO / "data" / "platforms" / "kalshi" / "contracts.yml").read_text()
    )
    poly = yaml.safe_load(
        (REPO / "data" / "platforms" / "polymarket" / "contracts.yml").read_text()
    )
    pick_ids = set()
    for p in kalshi.get("picks", []):
        pick_ids.add(p["id"])
    for p in poly.get("picks", []):
        pick_ids.add(p["id"])
    for entry in doc["portfolio"]:
        assert entry["id"] in pick_ids, (
            f"{entry['id']} not found in any contracts.yml — must be API-pulled"
        )


def test_retrospective_yamls_exist():
    doc = yaml.safe_load(CURATION.read_text())
    for entry in doc["retrospectives"]:
        platform = entry["platform"]
        path = REPO / "data" / "platforms" / platform / "contracts" / f"{entry['id']}.yml"
        assert path.exists(), f"Missing retrospective YAML: {path}"
