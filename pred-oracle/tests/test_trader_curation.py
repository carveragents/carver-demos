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


def test_portfolio_has_six_contracts():
    doc = yaml.safe_load(CURATION.read_text())
    assert len(doc["portfolio"]) == 6


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


def test_new_contract_yamls_exist():
    for path in [
        REPO / "data" / "platforms" / "kalshi" / "contracts" / "kxuschina-tariffs-2026.yml",
        REPO / "data" / "platforms" / "polymarket" / "contracts" / "sec-eth-security-2026.yml",
        REPO / "data" / "platforms" / "polymarket" / "contracts" / "fatf-travel-rule-2027.yml",
    ]:
        assert path.exists(), f"Missing: {path}"
        doc = yaml.safe_load(path.read_text())
        assert doc["schema_version"] == 1
        assert isinstance(doc["settlement_entities"], list)
        assert len(doc["settlement_entities"]) >= 3
