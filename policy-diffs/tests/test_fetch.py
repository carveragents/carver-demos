# tests/test_fetch.py
from unittest.mock import MagicMock

import pytest

from pipeline.fetch import enumerate_versions, raw_url, Snapshot


def test_enumerate_versions_dedupes_by_digest():
    cdx_rows = [
        ["timestamp", "digest", "statuscode", "mimetype"],
        ["20220628210349", "AAAA", "200", "application/pdf"],
        ["20220708091346", "AAAA", "200", "application/pdf"],          # dupe digest
        ["20230516183156", "BBBB", "200", "application/pdf"],
        ["20230516183200", "CCCC", "200", "warc/revisit"],             # skip revisit
        ["20230907012045", "DDDD", "200", "application/pdf"],
    ]

    snapshots = enumerate_versions(cdx_rows)

    assert [s.digest for s in snapshots] == ["AAAA", "BBBB", "DDDD"]
    assert snapshots[0].timestamp == "20220628210349"  # earliest kept


def test_raw_url_uses_id_form():
    s = Snapshot(timestamp="20220628210349", digest="AAAA", original="https://example.com/a.pdf")
    assert raw_url(s) == "https://web.archive.org/web/20220628210349id_/https://example.com/a.pdf"
