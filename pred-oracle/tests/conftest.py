"""Shared pytest fixtures + factories for the test suite."""
from __future__ import annotations

from typing import Any


def make_row(**overrides: Any) -> dict[str, Any]:
    """Build a baseline artifact-corpus record, override per-test as needed.

    Used by alpha slice generator tests. Matches the schema produced by
    build/pull_artifacts.py.
    """
    base: dict[str, Any] = {
        "feed_entry_id": "f-default",
        "artifact_id": "a-default",
        "title": "T",
        "link": "https://x",
        "regulator_name": "CFTC",
        "regulator_division": "",
        "classification_base_url": "cftc.gov",
        "topic_name": "Commodity Futures Trading Commission",
        "topic_jurisdiction_code": "US",
        "update_type": "enforcement",
        "update_subtype": "",
        "pub_date": "2026-05-19",
        "pub_date_valid": True,
        "critical_dates": {
            "effective_date": "",
            "compliance_date": "",
            "comment_deadline": "",
        },
        "impacted_business": {"jurisdiction": ["US"], "industry": []},
        "scores": {
            "urgency": {"score": 8, "label": "high"},
            "impact": {"score": 7, "label": "medium"},
            "relevance": {"score": 8, "label": "medium"},
        },
        "impact_summary": {
            "what_changed": "",
            "why_it_matters": "",
            "key_requirements": [],
            "objective": "",
            "risk_impact": "",
        },
        "penalties_consequences": [],
        "reg_references": {
            "statutes": [], "rules": [], "past_release": [],
            "precedents": [], "personnel": [],
        },
        "entities": [],
        "tags": [],
        "jurisdiction_tier": {"label": "us_federal", "tier": 1},
    }
    base.update(overrides)
    return base


def make_contract(**overrides: Any) -> dict[str, Any]:
    """Build a baseline curated-contract record for γ slice tests.

    Shape matches what gamma slice generators consume:
    fields drawn from the post-refresh contracts.yml `cached` block plus
    pick-level metadata (id, kind, platform).
    """
    base: dict[str, Any] = {
        "id": "kx-default",
        "platform": "kalshi",
        "kind": "active",
        "title": "Default contract title",
        "subtitle": "",
        "resolution_criteria": "Resolves YES if the default thing happens by year-end.",
        "external_id": "KX-DEFAULT",
        "status": "active",
        "listed_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-12-31T00:00:00Z",
        "settlement_entities": ["Federal Reserve System"],
        "source_urls": [],
    }
    base.update(overrides)
    return base
