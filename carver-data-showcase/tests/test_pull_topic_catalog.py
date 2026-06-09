"""Tests for tools/pull_topic_catalog.py using httpx.MockTransport (no live network).

Tests verify:
- Row count equals the number of institutions returned by /feeds/topics
- `name` field is populated for all rows
- Most-specific category assignment: MD > DP > Finance
- Uncategorized fallback for topics outside the 3 categories
"""

import csv
import importlib.util
import json
import os
import sys
import tempfile
from unittest.mock import patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Load the module under test from its file path rather than via normal import
# so we can patch its module-level env-loading without side effects.
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS_DIR = os.path.join(ROOT, "tools")


def _load_module(name, path):
    """Load a Python file as a module without executing __main__ block."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Stub data
# ---------------------------------------------------------------------------

TOPICS_STUB = [
    {
        "id": "topic-md-1",
        "name": "FDA Medical Device Approvals",
        "acronym": "FDA-MD",
        "jurisdiction_code": "US",
        "jurisdiction_detail": "United States",
        "entity_type": "regulatory_agency",
        "govt_body": True,
        "scope": "national",
        "sectors": ["healthcare"],
        "industries": ["medical_devices"],
        "hq": "Washington DC",
        "base_domain": "fda.gov",
    },
    {
        "id": "topic-dp-1",
        "name": "ICO Data Protection",
        "acronym": "ICO",
        "jurisdiction_code": "GB",
        "jurisdiction_detail": "United Kingdom",
        "entity_type": "regulatory_agency",
        "govt_body": True,
        "scope": "national",
        "sectors": ["technology"],
        "industries": ["data_services"],
        "hq": "Wilmslow",
        "base_domain": "ico.org.uk",
    },
    {
        "id": "topic-fin-1",
        "name": "SEC Finance Oversight",
        "acronym": "SEC",
        "jurisdiction_code": "US",
        "jurisdiction_detail": "United States",
        "entity_type": "regulatory_agency",
        "govt_body": True,
        "scope": "national",
        "sectors": ["finance"],
        "industries": ["banking"],
        "hq": "Washington DC",
        "base_domain": "sec.gov",
    },
    {
        "id": "topic-fin-2",
        "name": "FCA Financial Conduct",
        "acronym": "FCA",
        "jurisdiction_code": "GB",
        "jurisdiction_detail": "United Kingdom",
        "entity_type": "regulatory_agency",
        "govt_body": True,
        "scope": "national",
        "sectors": ["finance"],
        "industries": ["banking", "insurance"],
        "hq": "London",
        "base_domain": "fca.org.uk",
    },
]

CATEGORIES_STUB = [
    {"id": "cat-finance", "name": "Finance", "topic_count": 4},
    {"id": "cat-dp", "name": "Data protection and cybersecurity", "topic_count": 1},
    {"id": "cat-md", "name": "Medical Devices", "topic_count": 1},
]

# topic membership: MD > DP > Finance (most specific wins via setdefault)
CATEGORY_TOPICS_STUB = {
    "cat-finance": ["topic-md-1", "topic-dp-1", "topic-fin-1", "topic-fin-2"],
    "cat-dp": ["topic-dp-1"],
    "cat-md": ["topic-md-1"],
}


def _make_transport():
    """Return an httpx.MockTransport that serves the stub API responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/api/v1/feeds/topics":
            return httpx.Response(200, json=TOPICS_STUB)

        if path == "/api/v1/feeds/categories":
            return httpx.Response(200, json=CATEGORIES_STUB)

        for cid, topic_ids in CATEGORY_TOPICS_STUB.items():
            if path == f"/api/v1/feeds/categories/{cid}/topics":
                # Return full topic dicts for the ids in this category
                members = [t for t in TOPICS_STUB if t["id"] in topic_ids]
                return httpx.Response(200, json=members)

        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Helpers to invoke the module functions directly via patched httpx.Client
# ---------------------------------------------------------------------------


@pytest.fixture()
def catalog_module():
    """Load pull_topic_catalog module with env patched so dotenv/os.environ are safe."""
    env_patch = {
        "CARVER_API_KEY": "test-key-stub",
        "CARVER_BASE_URL": "https://stub.carveragents.test",
    }
    with patch.dict(os.environ, env_patch):
        mod = _load_module(
            "pull_topic_catalog",
            os.path.join(TOOLS_DIR, "pull_topic_catalog.py"),
        )
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFetchCatalog:
    """Tests for the fetch_catalog function (category assignment)."""

    def test_row_count_equals_topic_count(self, catalog_module):
        """catalog rows == number of topics returned by /feeds/topics."""
        transport = _make_transport()
        with httpx.Client(transport=transport) as client:
            topic_cat, topic_meta = catalog_module.fetch_catalog(client)
        assert len(topic_cat) == len(TOPICS_STUB)

    def test_name_populated_for_all_rows(self, catalog_module):
        """Every entry in topic_meta must have a non-empty 'name' field."""
        transport = _make_transport()
        with httpx.Client(transport=transport) as client:
            topic_cat, topic_meta = catalog_module.fetch_catalog(client)
        for tid, meta in topic_meta.items():
            assert meta.get("name"), f"topic {tid} has empty/missing name"

    def test_most_specific_category_md_wins(self, catalog_module):
        """topic-md-1 is in all 3 categories; it should be assigned 'Medical Devices'."""
        transport = _make_transport()
        with httpx.Client(transport=transport) as client:
            topic_cat, _ = catalog_module.fetch_catalog(client)
        assert topic_cat["topic-md-1"] == "Medical Devices"

    def test_most_specific_category_dp_wins_over_finance(self, catalog_module):
        """topic-dp-1 is in Finance + DP; it should be assigned DP (more specific)."""
        transport = _make_transport()
        with httpx.Client(transport=transport) as client:
            topic_cat, _ = catalog_module.fetch_catalog(client)
        assert topic_cat["topic-dp-1"] == "Data protection and cybersecurity"

    def test_finance_only_topics_get_finance(self, catalog_module):
        """Topics only in Finance should be assigned 'Finance'."""
        transport = _make_transport()
        with httpx.Client(transport=transport) as client:
            topic_cat, _ = catalog_module.fetch_catalog(client)
        assert topic_cat["topic-fin-1"] == "Finance"
        assert topic_cat["topic-fin-2"] == "Finance"

    def test_uncategorized_topic_gets_empty(self, catalog_module):
        """A topic not in any category lists should map to '' / 'Uncategorized'."""
        # Build a transport that includes an extra topic absent from all categories
        extra_topic = {
            "id": "topic-orphan",
            "name": "Orphan Regulator",
            "acronym": "",
            "jurisdiction_code": "XX",
            "jurisdiction_detail": "",
            "entity_type": "",
            "govt_body": False,
            "scope": "",
            "sectors": [],
            "industries": [],
            "hq": "",
            "base_domain": "",
        }
        all_topics = TOPICS_STUB + [extra_topic]

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/feeds/topics":
                return httpx.Response(200, json=all_topics)
            if path == "/api/v1/feeds/categories":
                return httpx.Response(200, json=CATEGORIES_STUB)
            for cid, topic_ids in CATEGORY_TOPICS_STUB.items():
                if path == f"/api/v1/feeds/categories/{cid}/topics":
                    members = [t for t in all_topics if t["id"] in topic_ids]
                    return httpx.Response(200, json=members)
            return httpx.Response(404, json={})

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            topic_cat, topic_meta = catalog_module.fetch_catalog(client)

        # Orphan must exist in topic_meta (from /feeds/topics), with empty/Uncategorized category
        assert "topic-orphan" in topic_meta
        cat = topic_cat.get("topic-orphan", "")
        assert cat in ("", "Uncategorized"), f"Expected empty/Uncategorized, got {cat!r}"


class TestWriteCsv:
    """Integration test: fetch_catalog + write CSV → verify output file."""

    def test_csv_has_expected_rows_and_name_column(self, catalog_module, tmp_path):
        """Written CSV should have len(TOPICS_STUB) data rows, all with `name` populated."""
        out_csv = str(tmp_path / "topic_catalog.csv")

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/feeds/topics":
                return httpx.Response(200, json=TOPICS_STUB)
            if path == "/api/v1/feeds/categories":
                return httpx.Response(200, json=CATEGORIES_STUB)
            for cid, topic_ids in CATEGORY_TOPICS_STUB.items():
                if path == f"/api/v1/feeds/categories/{cid}/topics":
                    members = [t for t in TOPICS_STUB if t["id"] in topic_ids]
                    return httpx.Response(200, json=members)
            return httpx.Response(404, json={})

        transport = httpx.MockTransport(handler)

        with patch.dict(
            os.environ,
            {"CARVER_API_KEY": "test-key", "CARVER_BASE_URL": "https://stub.test"},
        ):
            with httpx.Client(transport=transport) as client:
                topic_cat, topic_meta = catalog_module.fetch_catalog(client)
            catalog_module.write_csv(topic_cat, topic_meta, out_csv)

        assert os.path.exists(out_csv), "CSV file was not written"

        with open(out_csv, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == len(TOPICS_STUB), (
            f"Expected {len(TOPICS_STUB)} data rows, got {len(rows)}"
        )
        assert "name" in reader.fieldnames, "CSV must have a 'name' column"
        for row in rows:
            assert row["name"], f"row {row['topic_id']} has empty name"
        # Verify most-specific category assignment in CSV output
        md_row = next(r for r in rows if r["topic_id"] == "topic-md-1")
        assert md_row["category"] == "Medical Devices"
        dp_row = next(r for r in rows if r["topic_id"] == "topic-dp-1")
        assert dp_row["category"] == "Data protection and cybersecurity"
