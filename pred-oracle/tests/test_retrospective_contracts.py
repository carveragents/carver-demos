"""Validate hand-curated retrospective contract YAMLs."""
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
RETROS = [
    REPO / "data" / "platforms" / "kalshi" / "contracts" / "tiktokban-25apr30.yml",
    REPO / "data" / "platforms" / "kalshi" / "contracts" / "kxfeddecision-26mar.yml",
    REPO / "data" / "platforms" / "polymarket" / "contracts" / "solana-etf-2025.yml",
]


def test_all_retrospectives_exist() -> None:
    for p in RETROS:
        assert p.exists(), f"missing {p}"


def test_retrospective_schema() -> None:
    for p in RETROS:
        doc = yaml.safe_load(p.read_text())
        assert doc["schema_version"] == 1
        assert doc["kind"] == "retrospective"
        assert doc["platform"] in {"kalshi", "polymarket"}
        assert isinstance(doc["title"], str) and doc["title"]
        assert isinstance(doc["resolution_criteria"], str) and doc["resolution_criteria"]
        assert isinstance(doc["settlement_entities"], list) and len(doc["settlement_entities"]) >= 3
        assert doc.get("listed_at")
        assert doc.get("resolved_at")
        assert doc["status"] == "resolved"
        # Mandatory: source_url to Wayback or news article
        assert isinstance(doc["source_urls"], list) and len(doc["source_urls"]) >= 1
        for u in doc["source_urls"]:
            assert u.startswith("https://"), f"non-https source in {p}: {u}"
