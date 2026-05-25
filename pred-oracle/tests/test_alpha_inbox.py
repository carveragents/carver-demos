"""Tests for build/alpha_inbox.py — inbox slice generator."""
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from tests.conftest import make_row


def _write_corpus(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows))


def _write_curation(path: Path, wow_id: str, supporting: list[str]) -> None:
    path.write_text(yaml.safe_dump({
        "schema_version": 1,
        "wow_ticket_id": wow_id,
        "supporting_ticket_ids": supporting,
        "dashboard_window_days": 90,
        "inbox_top_n": 5,
        "persona_key": "gc",
        "synthetic_assignees": [
            {"name": "Sara Chen", "role": "GC", "initials": "SC"},
            {"name": "Devin Liu", "role": "Associate", "initials": "DL"},
        ],
        "synthetic_comment_templates": [],
    }))


def test_inbox_generation_basic(tmp_path: Path) -> None:
    from build.alpha_inbox import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out = tmp_path / "inbox.json"

    _write_corpus(corpus, [
        make_row(feed_entry_id=f"f{i}", title=f"Row {i}") for i in range(10)
    ])
    _write_curation(curation, "f0", ["f1", "f2", "f3", "f4"])

    generate(corpus_path=corpus, curation_path=curation, out_path=out, today=date(2026, 5, 19))

    assert out.exists()
    doc = json.loads(out.read_text())
    assert doc["scene"]["number"] == 1
    assert len(doc["rows"]) == 5
    assert doc["stats"]["active_items"] >= 5


def test_inbox_wow_row_is_first(tmp_path: Path) -> None:
    from build.alpha_inbox import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out = tmp_path / "inbox.json"

    rows = [
        make_row(feed_entry_id="f0", title="Top by score",
                  scores={"urgency": {"score": 10}, "impact": {"score": 10},
                          "relevance": {"score": 10}}),
        make_row(feed_entry_id="f1", title="Wow pick",
                  scores={"urgency": {"score": 6}, "impact": {"score": 6},
                          "relevance": {"score": 6}}),
    ]
    _write_corpus(corpus, rows)
    _write_curation(curation, "f1", ["f0", "f0", "f0", "f0"])

    generate(corpus_path=corpus, curation_path=curation, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    assert doc["rows"][0]["id"] == "f1", "wow ticket must be first"
    assert doc["rows"][0]["is_wow"] is True


def test_inbox_excludes_ineligible(tmp_path: Path) -> None:
    from build.alpha_inbox import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out = tmp_path / "inbox.json"

    _write_corpus(corpus, [
        make_row(feed_entry_id="f-good", title="Good"),
        make_row(feed_entry_id="f-website-err", title="Bad", update_type="website error"),
        make_row(feed_entry_id="f-irrelevant", title="Off-topic",
                  scores={"urgency": {"score": 9}, "impact": {"score": 9},
                          "relevance": {"score": 3}}),  # relevance < 5
    ])
    _write_curation(curation, "f-good", ["f-good", "f-good", "f-good", "f-good"])

    generate(corpus_path=corpus, curation_path=curation, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    ids = [r["id"] for r in doc["rows"]]
    assert "f-good" in ids
    assert "f-website-err" not in ids
    assert "f-irrelevant" not in ids


def test_inbox_has_detail_flag(tmp_path: Path) -> None:
    from build.alpha_inbox import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out = tmp_path / "inbox.json"

    _write_corpus(corpus, [
        make_row(feed_entry_id="f-wow"),
        make_row(feed_entry_id="f-sup-1"),
        make_row(feed_entry_id="f-no-detail"),
    ])
    _write_curation(curation, "f-wow", ["f-sup-1", "f-sup-1", "f-sup-1", "f-sup-1"])

    generate(corpus_path=corpus, curation_path=curation, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    by_id = {r["id"]: r for r in doc["rows"]}
    assert by_id["f-wow"]["has_detail"] is True
    assert by_id["f-sup-1"]["has_detail"] is True
    assert by_id["f-no-detail"]["has_detail"] is False


def test_inbox_assignee_round_robin(tmp_path: Path) -> None:
    from build.alpha_inbox import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out = tmp_path / "inbox.json"

    _write_corpus(corpus, [make_row(feed_entry_id=f"f{i}", title=f"R{i}") for i in range(4)])
    _write_curation(curation, "f0", ["f1", "f2", "f3", "f0"])

    generate(corpus_path=corpus, curation_path=curation, out_path=out, today=date(2026, 5, 19))

    doc = json.loads(out.read_text())
    assignees = [r["assignee"]["initials"] for r in doc["rows"]]
    assert set(assignees) == {"SC", "DL"}


def test_inbox_raises_when_wow_ticket_missing(tmp_path: Path) -> None:
    """If wow_ticket_id is not in the eligible corpus, raise ValueError."""
    from build.alpha_inbox import generate

    corpus = tmp_path / "artifacts.jsonl"
    curation = tmp_path / "alpha-curation.yml"
    out = tmp_path / "inbox.json"

    # Corpus has eligible records but NONE matches wow_id "f-missing"
    _write_corpus(corpus, [
        make_row(feed_entry_id="f0"),
        make_row(feed_entry_id="f1"),
    ])
    _write_curation(curation, "f-missing", ["f0", "f0", "f0", "f0"])

    with pytest.raises(ValueError, match="f-missing"):
        generate(corpus_path=corpus, curation_path=curation, out_path=out, today=date(2026, 5, 19))
