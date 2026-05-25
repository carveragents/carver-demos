# tests/test_diff.py
from pathlib import Path

from pipeline.extractors.base import Section
from pipeline.diff import diff_sections, SectionDelta


def test_diff_sections_only_returns_changed():
    v1 = [
        Section("1", "Intro", "unchanged content"),
        Section("2", "BRAM", "old text 180 days"),
    ]
    v2 = [
        Section("1", "Intro", "unchanged content"),
        Section("2", "BRAM", "new text 120 days"),
        Section("3", "New Section", "added"),
    ]

    deltas = diff_sections(v1, v2)

    ids = {d.section_id for d in deltas}
    assert ids == {"2", "3"}
    bram = next(d for d in deltas if d.section_id == "2")
    assert bram.kind == "modified"
    assert "180 days" in bram.before
    assert "120 days" in bram.after
    new = next(d for d in deltas if d.section_id == "3")
    assert new.kind == "added"


def test_diff_sections_detects_removed_section():
    v1 = [Section("1", "A", "x"), Section("2", "B", "y")]
    v2 = [Section("1", "A", "x")]

    deltas = diff_sections(v1, v2)

    assert len(deltas) == 1
    assert deltas[0].section_id == "2"
    assert deltas[0].kind == "removed"
