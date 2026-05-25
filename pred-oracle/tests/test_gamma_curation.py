"""Validate data/gamma-curation.yml shape."""
import datetime as _dt
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "gamma-curation.yml"


def test_curation_file_exists() -> None:
    assert CURATION.exists()


def test_curation_schema() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    assert doc["schema_version"] == 1
    _dt.date.fromisoformat(doc["build_date"])  # raises if not ISO
    assert isinstance(doc["featured_kalshi"], list) and len(doc["featured_kalshi"]) >= 3
    assert isinstance(doc["featured_polymarket"], list) and len(doc["featured_polymarket"]) >= 1
    assert isinstance(doc["pre_listing_scans"], list) and len(doc["pre_listing_scans"]) == 3
    for scan in doc["pre_listing_scans"]:
        assert {"id", "title", "resolution_criteria", "platform_hint"} <= set(scan.keys())
    # At least 5 contract-detail picks; ≥1 page per dashboard contract +
    # the 3 hand-curated retrospectives.
    assert isinstance(doc["contract_detail_picks"], list) and len(doc["contract_detail_picks"]) >= 5
    for pick in doc["contract_detail_picks"]:
        assert {"id", "platform", "kind"} <= set(pick.keys())
        assert pick["kind"] in {"active", "retrospective"}
    # Exactly 3 retrospectives expected per Stage 2 plan §4
    # (tiktokban-25apr30, kxfeddecision-26mar, solana-etf-2025)
    retros = [p for p in doc["contract_detail_picks"] if p["kind"] == "retrospective"]
    assert len(retros) == 3


def test_pre_listing_scan_ids_unique() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    ids = [s["id"] for s in doc["pre_listing_scans"]]
    assert len(set(ids)) == len(ids)
