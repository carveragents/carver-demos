"""Validate data/alpha-curation.yml shape and that referenced IDs exist."""
import datetime as _dt
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CURATION = REPO / "data" / "alpha-curation.yml"
CANDIDATES = REPO / "data" / "wow-candidates.json"


def test_curation_file_exists() -> None:
    assert CURATION.exists(), f"{CURATION} missing — see plan task 2"


def test_curation_schema() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    assert doc.get("schema_version") == 1
    assert "build_date" in doc, "build_date must be set per Stage 1 carryover I1"
    _dt.date.fromisoformat(doc["build_date"])  # raises ValueError if not a valid ISO date
    assert isinstance(doc.get("wow_ticket_id"), str) and not doc["wow_ticket_id"].startswith("<"), \
        "wow_ticket_id must be a real UUID, not the placeholder"
    assert isinstance(doc.get("supporting_ticket_ids"), list)
    assert len(doc["supporting_ticket_ids"]) == 4
    for sid in doc["supporting_ticket_ids"]:
        assert isinstance(sid, str) and not sid.startswith("<"), \
            f"supporting_ticket_id {sid} is a placeholder; replace with real UUID"
    assert isinstance(doc["dashboard_window_days"], int) and doc["dashboard_window_days"] > 0
    assert isinstance(doc["inbox_top_n"], int) and doc["inbox_top_n"] > 0
    assert doc.get("persona_key")
    assert isinstance(doc["synthetic_assignees"], list)
    assert isinstance(doc["synthetic_comment_templates"], list)


def test_curated_ids_are_in_candidates() -> None:
    """Curated IDs must be in the wow-candidates shortlist (catch typos)."""
    doc = yaml.safe_load(CURATION.read_text())
    candidate_ids = {r["feed_entry_id"] for r in json.loads(CANDIDATES.read_text())}
    assert doc["wow_ticket_id"] in candidate_ids, \
        "wow_ticket_id not in data/wow-candidates.json — re-pick from the top-25 shortlist"
    for sid in doc["supporting_ticket_ids"]:
        assert sid in candidate_ids, \
            f"supporting_ticket_id {sid} not in data/wow-candidates.json"


def test_no_duplicate_ticket_ids() -> None:
    doc = yaml.safe_load(CURATION.read_text())
    all_ids = [doc["wow_ticket_id"], *doc["supporting_ticket_ids"]]
    assert len(set(all_ids)) == len(all_ids), "ticket ids must be unique"
