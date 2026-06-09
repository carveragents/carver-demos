"""Shared pytest fixtures for ingest and normalize tests.

`raw_envelope` is derived from the actual API payload structure (probe-confirmed).
It includes:
  - populated fields for the happy-path tests
  - empty strings / whitespace / placeholder strings for the empties→NA tests
  - an anomalous impacted_business entry to exercise has_impacted_business logic
"""

import io
import json
import pathlib

import pandas as pd
import pytest


@pytest.fixture()
def raw_envelope() -> dict:
    """One realistic annotation envelope with a mix of populated, empty, and anomalous fields."""
    return {
        # --- Envelope ---
        "id": "aaaabbbb-0000-0000-0000-000000000001",
        "artifact_id": "aaaabbbb-0000-0000-0000-000000000001",
        "dag_id": "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad",
        "artifact_type_id": "annotations-v1",
        "source_kind": "record",
        "source_table": "crawl_outcomes",
        "source_id": "src-0001",
        "topic_id": "topic-finance-001",
        "source_metadata": {},
        "state": "completed",
        "created_at": "2025-11-01T10:00:00.000Z",
        "completed_at": "2025-11-01T10:05:00.000Z",
        # --- input_data ---
        "input_data": {
            "id": "src-0001",
            "source_id": "src-0001",
            "extracted_metadata": {
                "url": "https://www.fca.org.uk/news/press-releases/fca-update",
                "title": "Input Title (should not be used)",
                "status": "done",
                "feed_id": "feed-0001",
                "source_type": "rss",
                "timestamp": "2025-11-01T09:55:00+00:00",
                # language and summary are intentionally absent here (they live
                # in output_data.classification.metadata in the real payload)
            },
            "current_published_date": "2025-10-15T00:00:00+00:00",
            "feed_entry_id": "src-0001",
        },
        # --- output_data ---
        "output_data": {
            "entry_id": "src-0001",
            "scores": {
                "impact": {"label": "high", "score": 8.5, "confidence": 0.9},
                "urgency": {
                    "label": "medium",
                    "score": 5.0,
                    "confidence": 0.75,
                    "basis": "future_deadline",
                },
                "relevance": {"label": "high", "score": 7.5, "confidence": 0.8},
            },
            "metadata": {
                "tags": ["Basel III", "Capital Requirements", "Banking"],
                "entities": ["FCA", "Bank of England", "HM Treasury"],
                "actionables": {
                    "policy_change": "Firms must update their capital adequacy policies.",
                    "status_change": "",  # empty → not counted
                    "process_change": "   ",  # whitespace-only → not counted
                    "training_change": "N/A",  # placeholder → not counted
                    "reporting_change": "Firms must submit updated regulatory reports.",
                    "tech_data_change": "Update data feeds to new schema.",
                    "other_change": "None",  # placeholder → not counted
                },
                "critical_dates": {
                    "effective_date": "2026-01-01",
                    "effective_date_calendar": "gregorian",
                    "compliance_date": "",  # empty → NA
                    "compliance_date_calendar": "",
                    "comment_deadline": "2025-12-01",
                    "comment_deadline_calendar": "gregorian",
                    "early_adoption_date": "",
                    "early_adoption_date_calendar": "",
                    "updated_date": "",
                    "updated_date_calendar": "",
                    "pub_date_content": "2025-10-15",
                    "pub_date_calendar": "gregorian",
                    "other_dates": [
                        {
                            "date": "2025-09-30",
                            "calendar": "gregorian",
                            "description": "Consultation period closed",
                        },
                        {
                            "date": "2026-06-30",
                            "calendar": "gregorian",
                            "description": "Phase 2 implementation deadline",
                        },
                    ],
                },
                "impact_summary": {
                    "objective": "To strengthen capital adequacy requirements for UK banks post-Brexit.",
                    "what_changed": "New minimum CET1 ratios introduced for systemically important institutions.",
                    "why_it_matters": "Undercapitalized banks pose systemic risk to the UK financial system.",
                    "risk_impact": "Firms failing to comply face enforcement action and potential license revocation.",
                    "key_requirements": [
                        "Maintain CET1 ratio of at least 8%.",
                        "Submit updated ICAAP by 2026-03-31.",
                        "Notify FCA of any capital buffer breaches within 24 hours.",
                    ],
                },
                "reg_references": {
                    "rules": [
                        "FCA PRIN 2.1 — Integrity",
                        "PRA Rulebook: Capital Requirements",
                    ],
                    "statutes": ["Financial Services and Markets Act 2000", "Bank Recovery and Resolution Directive"],
                    "other_ref": ["Basel III framework (BIS 2017)"],
                    "personnel": [],  # empty list → 0
                    "precedents": [],
                    "past_release": ["FCA PS24/12"],
                },
                "impacted_business": {
                    "industry": ["Banking", "Financial Services"],
                    "type": ["Large Institutions", "Systemically Important Firms"],
                    "jurisdiction": ["GB"],
                    "other_notes": ["Focus on PRA-regulated entities"],
                },
                "impacted_functions": [
                    "Risk Management",
                    "Finance",
                    "Compliance",
                    "Technology",
                ],
                "penalties_consequences": [
                    "Fines up to 10% of annual turnover.",
                    "License suspension or revocation.",
                ],
            },
            "classification": {
                "metadata": {
                    "title": "FCA Capital Requirements Update 2025",
                    "feed_url": "https://www.fca.org.uk/news/press-releases/fca-capital-update-2025",
                    "base_url": "fca.org.uk",
                    "language": ["en"],
                    "summary": "FCA updates capital adequacy requirements for UK banks.",
                    "extraction_note": [],
                },
                "update_type": "Regulatory Update",
                "update_subtype": "Capital Requirements",
                "jurisdiction": {
                    "scope": "national",
                    "country": "GB",
                    "bloc": "N/A",  # placeholder → NA
                    "locality": None,
                    "region_code": None,
                    "region_name": None,
                    "locality_type": None,
                    "reasoning": (
                        "FCA is the UK national financial regulator; "
                        "the regulation applies to UK-incorporated firms."
                    ),
                },
                "regulatory_source": {
                    "name": "Financial Conduct Authority",
                    "division_office": "Prudential Policy Division",
                    "other_agency": ["Prudential Regulation Authority"],
                },
            },
            "reconciled_published_date": {
                "date": "2025-10-15",
                "source": "content",
                "converted": False,
                "original_calendar": "gregorian",
                "valid": True,
            },
        },
    }


@pytest.fixture()
def raw_envelope_with_legacy_tier(raw_envelope) -> dict:
    """Envelope with the deprecated jurisdiction_tier field present."""
    import copy
    env = copy.deepcopy(raw_envelope)
    env["output_data"]["classification"]["jurisdiction_tier"] = "national"
    return env


@pytest.fixture()
def tiny_jsonl(tmp_path: pathlib.Path) -> pathlib.Path:
    """Write 3 minimal JSONL lines and return the path."""
    records = [
        {"id": f"rec-{i:04d}", "topic_id": f"topic-{i}", "state": "completed"}
        for i in range(3)
    ]
    p = tmp_path / "tiny.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return p


@pytest.fixture()
def categories_df() -> pd.DataFrame:
    """Small topic-to-category mapping frame (mirrors topic_categories.csv schema)."""
    return pd.DataFrame(
        {
            "topic_id": [
                "topic-finance-001",  # matches raw_envelope
                "topic-meddev-002",
                "topic-dataprotect-003",
            ],
            "category": [
                "Finance",
                "Medical Devices",
                "Data protection and cybersecurity",
            ],
        }
    )
