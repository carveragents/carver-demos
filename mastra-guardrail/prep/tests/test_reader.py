"""Tests for mastra_prep.reader — the streaming JSONL reader (spec §2).

LEAF module: imports nothing else from `mastra_prep`. The real target file is
~1.8GB (`../carver-showcase/data/annotations.jsonl`, goal — read-only, never
loaded into memory); these tests exercise the same code path against small,
disposable fixture files under `tmp_path`.
"""
from __future__ import annotations

import inspect
import json
import logging

import pytest

from mastra_prep.reader import stream_annotations


def _write_jsonl(path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_returns_a_generator_not_a_loaded_list(tmp_path):
    """`stream_annotations` must be lazy — the whole point of streaming is that
    calling it does no I/O and holds no more than one record at a time."""
    path = tmp_path / "sample.jsonl"
    _write_jsonl(path, [json.dumps({"artifact_id": "a1"})])

    result = stream_annotations(path)
    assert inspect.isgenerator(result)


def test_streams_three_line_fixture_one_record_at_a_time(tmp_path):
    path = tmp_path / "sample.jsonl"
    _write_jsonl(
        path,
        [
            json.dumps({"artifact_id": "a1", "value": 1}),
            json.dumps({"artifact_id": "a2", "value": 2}),
            json.dumps({"artifact_id": "a3", "value": 3}),
        ],
    )

    gen = stream_annotations(path)

    # Exhaustion, one `next()` at a time — proves the generator yields exactly
    # the 3 records present and nothing is buffered/pre-loaded as a whole list.
    assert next(gen) == {"artifact_id": "a1", "value": 1}
    assert next(gen) == {"artifact_id": "a2", "value": 2}
    assert next(gen) == {"artifact_id": "a3", "value": 3}
    with pytest.raises(StopIteration):
        next(gen)


def test_malformed_line_is_skipped_and_stream_continues(tmp_path, caplog):
    path = tmp_path / "malformed.jsonl"
    _write_jsonl(
        path,
        [
            json.dumps({"artifact_id": "a1"}),
            "{this is not valid json",
            json.dumps({"artifact_id": "a2"}),
        ],
    )

    with caplog.at_level(logging.WARNING, logger="mastra_prep.reader"):
        records = list(stream_annotations(path))

    assert records == [{"artifact_id": "a1"}, {"artifact_id": "a2"}]

    warnings = [
        r for r in caplog.records if r.name == "mastra_prep.reader" and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "line 2" in message
    assert "this is not valid json" in message


def test_blank_lines_are_skipped_without_warning(tmp_path, caplog):
    path = tmp_path / "blanks.jsonl"
    path.write_text(
        json.dumps({"artifact_id": "a1"}) + "\n\n\n" + json.dumps({"artifact_id": "a2"}) + "\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="mastra_prep.reader"):
        records = list(stream_annotations(path))

    assert records == [{"artifact_id": "a1"}, {"artifact_id": "a2"}]
    assert [
        r for r in caplog.records if r.name == "mastra_prep.reader" and r.levelno == logging.WARNING
    ] == []


def test_missing_file_raises_file_not_found(tmp_path):
    missing = tmp_path / "does_not_exist.jsonl"
    with pytest.raises(FileNotFoundError):
        next(stream_annotations(missing))


def test_empty_file_yields_nothing(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    assert list(stream_annotations(path)) == []


def test_malformed_line_warning_truncates_to_80_chars(tmp_path, caplog):
    """The spec pins the warning to `%.80s` — first 80 chars of the raw line,
    not the whole thing. A line long enough that truncation actually matters
    (well past 80 chars) is what proves the format spec, not just the code."""
    long_garbage = "{" + ("x" * 200)  # 201 chars, well past the 80-char cut
    path = tmp_path / "long_malformed.jsonl"
    _write_jsonl(path, [long_garbage])

    with caplog.at_level(logging.WARNING, logger="mastra_prep.reader"):
        records = list(stream_annotations(path))

    assert records == []
    warnings = [
        r for r in caplog.records if r.name == "mastra_prep.reader" and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert long_garbage[:80] in message
    assert long_garbage[80:] not in message
