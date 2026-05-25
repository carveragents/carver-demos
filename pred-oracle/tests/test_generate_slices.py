"""Tests for the slice generator."""

import json
import subprocess
from pathlib import Path

from build.generate_slices import generate_landing_slice


def test_generate_landing_slice_from_artifacts_jsonl(tmp_path: Path) -> None:
    """generate_landing_slice reads artifacts.jsonl, not carver-events.json."""
    corpus = tmp_path / "artifacts.jsonl"

    rows = [
        {
            "artifact_id": "a1", "title": "T1", "link": "https://x",
            "regulator_name": "CFTC",
            "topic_name": "Commodity Futures Trading Commission",
            "pub_date": "2026-05-10", "pub_date_valid": True,
            "topic_jurisdiction_code": "US",
            "impacted_business": {"jurisdiction": ["US"]},
            "update_type": "enforcement",
            "scores": {"urgency": {"score": 8}, "impact": {"score": 7}, "relevance": {"score": 8}},
        },
        {
            "artifact_id": "a2", "title": "T2", "link": "https://y",
            "regulator_name": "SEC",
            "topic_name": "U.S. Securities and Exchange Commission",
            "pub_date": "2026-04-01", "pub_date_valid": True,
            "topic_jurisdiction_code": "US-CA",
            "impacted_business": {"jurisdiction": ["US-CA"]},
            "update_type": "advisory",
            "scores": {"urgency": {"score": 5}, "impact": {"score": 6}, "relevance": {"score": 7}},
        },
    ]
    corpus.write_text("\n".join(json.dumps(r) for r in rows))

    out = generate_landing_slice(corpus_path=corpus)

    assert out["events_count"] == 2
    # 'US' (ISO-2) + 'US-CA' (subdivision) both pass the validation regex
    assert out["jurisdictions_count"] == 2
    # topic_name de-duplicated (one CFTC topic, one SEC topic).
    assert out["unique_regulators_count"] == 2
    assert out["earliest_pub_date"] == "2026-04-01"
    assert out["latest_pub_date"] == "2026-05-10"


def test_generate_landing_slice_corpus_not_found(tmp_path: Path) -> None:
    """Returns zeroed dict when corpus does not exist (pre-pull state)."""
    corpus = tmp_path / "artifacts.jsonl"   # do NOT create it
    out = generate_landing_slice(corpus_path=corpus)
    assert out["events_count"] == 0
    assert out["jurisdictions_count"] == 0
    assert out["unique_regulators_count"] == 0
    assert out["earliest_pub_date"] is None
    assert out["latest_pub_date"] is None


def test_main_is_deterministic_across_runs() -> None:
    """make build run twice should produce byte-identical slices when build_date is set."""
    REPO = Path(__file__).resolve().parent.parent
    inbox_path = REPO / "build" / "page_data" / "alpha" / "inbox.json"

    # First build
    subprocess.run(["uv", "run", "python", "build/generate_slices.py"], cwd=REPO, check=True)
    first_snap = inbox_path.read_text()

    # Second build
    subprocess.run(["uv", "run", "python", "build/generate_slices.py"], cwd=REPO, check=True)
    second_snap = inbox_path.read_text()

    assert first_snap == second_snap, "build_date anchor must make output deterministic"
