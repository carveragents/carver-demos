"""Tests for carver_showcase/ingest.py.

All network calls are stubbed via httpx.MockTransport — zero live API calls.
"""

import json
import pathlib

import httpx
import pytest

from carver_showcase import ingest


# ---------------------------------------------------------------------------
# load_snapshot
# ---------------------------------------------------------------------------


class TestLoadSnapshot:
    def test_load_snapshot_streams_each_line(self, tiny_jsonl: pathlib.Path):
        """load_snapshot yields one dict per JSONL line; all ids round-trip correctly."""
        results = list(ingest.load_snapshot(tiny_jsonl))
        assert len(results) == 3
        for i, row in enumerate(results):
            assert row["id"] == f"rec-{i:04d}"

    def test_load_snapshot_yields_dicts(self, tiny_jsonl: pathlib.Path):
        """Every yielded item is a dict."""
        for row in ingest.load_snapshot(tiny_jsonl):
            assert isinstance(row, dict)

    def test_load_snapshot_is_lazy(self, tiny_jsonl: pathlib.Path):
        """load_snapshot returns a generator/iterator, not a materialised list."""
        result = ingest.load_snapshot(tiny_jsonl)
        # Should be an iterator (not list/tuple/set)
        assert hasattr(result, "__iter__") and hasattr(result, "__next__")

    def test_load_snapshot_skips_blank_lines(self, tmp_path: pathlib.Path):
        """Blank lines in the JSONL are silently skipped."""
        p = tmp_path / "with_blanks.jsonl"
        p.write_text('{"id": "a"}\n\n{"id": "b"}\n')
        results = list(ingest.load_snapshot(p))
        assert len(results) == 2
        assert results[0]["id"] == "a"
        assert results[1]["id"] == "b"


# ---------------------------------------------------------------------------
# pull_snapshot — empty filter guard
# ---------------------------------------------------------------------------


class TestPullSnapshotEmptyFilterGuard:
    def test_pull_refuses_empty_topic_ids(self):
        """pull_snapshot MUST raise ValueError when topic_ids is an empty list.

        An empty topic_ids_in filter hits the API with no filter at all and
        would pull the whole corpus — a real past bug (pull_stratified.py § docstring).
        """
        with pytest.raises(ValueError, match="empty"):
            ingest.pull_snapshot(
                api_key="fake-key",
                dag="fake-dag",
                out_path=pathlib.Path("/dev/null"),
                topic_ids=[],  # ← the guard must fire
            )

    def test_pull_accepts_none_topic_ids(self, tmp_path: pathlib.Path):
        """pull_snapshot with topic_ids=None (no filter) is allowed — it's a full pull.

        The guard must NOT fire for None (only for an explicit empty list).
        We stub the transport to return an empty page, confirming the call
        succeeds (returns 0) without raising ValueError.
        """

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        # Must not raise — especially must not raise ValueError about "empty"
        result = ingest.pull_snapshot(
            api_key="fake-key",
            dag="fake-dag",
            out_path=tmp_path / "out.jsonl",
            topic_ids=None,
            _transport=httpx.MockTransport(_handler),
        )
        assert result == 0  # empty page → 0 records written


# ---------------------------------------------------------------------------
# pull_snapshot — pagination
# ---------------------------------------------------------------------------


def _make_paginated_handler(page_size: int, total: int):
    """Return an httpx handler that serves `total` fake records page_size at a time."""
    DAG = "fake-dag"

    def _handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", page_size))
        remaining = max(0, total - offset)
        count = min(limit, remaining)
        records = [{"id": f"art-{offset + i}", "topic_id": "t1", "state": "completed"} for i in range(count)]
        return httpx.Response(200, json=records)

    return _handler


class TestPullSnapshotPagination:
    def test_pull_snapshot_paginates_until_short_page(self, tmp_path: pathlib.Path):
        """pull_snapshot stops when it receives a page shorter than page_size."""
        total_records = 25
        page_size = 10
        out = tmp_path / "out.jsonl"

        handler = _make_paginated_handler(page_size=page_size, total=total_records)

        n = ingest.pull_snapshot(
            api_key="fake-key",
            dag="fake-dag",
            out_path=out,
            page_size=page_size,
            _transport=httpx.MockTransport(handler),
        )

        assert n == total_records
        lines = [l for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == total_records

    def test_pull_snapshot_stops_on_empty_page(self, tmp_path: pathlib.Path):
        """pull_snapshot stops immediately when the first page is empty."""
        out = tmp_path / "out.jsonl"
        handler = _make_paginated_handler(page_size=10, total=0)

        n = ingest.pull_snapshot(
            api_key="fake-key",
            dag="fake-dag",
            out_path=out,
            page_size=10,
            _transport=httpx.MockTransport(handler),
        )

        assert n == 0
        assert not out.exists() or out.read_text().strip() == ""

    def test_pull_snapshot_topic_ids_in_filter(self, tmp_path: pathlib.Path):
        """When topic_ids is provided, the URL contains topic_ids_in."""
        captured_urls: list[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(200, json=[])

        out = tmp_path / "out.jsonl"
        ingest.pull_snapshot(
            api_key="fake-key",
            dag="fake-dag",
            out_path=out,
            topic_ids=["tid-1", "tid-2"],
            page_size=100,
            _transport=httpx.MockTransport(_handler),
        )

        assert len(captured_urls) >= 1
        assert "topic_ids_in" in captured_urls[0]
        assert "tid-1" in captured_urls[0]
        assert "tid-2" in captured_urls[0]

    def test_pull_snapshot_writes_valid_jsonl(self, tmp_path: pathlib.Path):
        """Each line written by pull_snapshot must be valid JSON."""
        out = tmp_path / "out.jsonl"
        handler = _make_paginated_handler(page_size=10, total=5)

        ingest.pull_snapshot(
            api_key="fake-key",
            dag="fake-dag",
            out_path=out,
            page_size=10,
            _transport=httpx.MockTransport(handler),
        )

        for line in out.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# pull_topic_catalog
# ---------------------------------------------------------------------------


class TestPullTopicCatalog:
    def test_pull_topic_catalog_writes_rows(self, tmp_path: pathlib.Path):
        """pull_topic_catalog must write rows from the API response to out_path."""

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {"id": "topic-1", "name": "Basel III Compliance", "jurisdiction_code": "GB"},
                    {"id": "topic-2", "name": "GDPR Enforcement", "jurisdiction_code": "EU"},
                ],
            )

        out = tmp_path / "catalog.jsonl"
        n = ingest.pull_topic_catalog(
            api_key="fake-key",
            out_path=out,
            _transport=httpx.MockTransport(_handler),
        )

        assert n == 2
        lines = [l for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["id"] == "topic-1"
