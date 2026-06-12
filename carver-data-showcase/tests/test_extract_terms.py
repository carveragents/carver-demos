"""Tests for tools/extract_terms.py — deterministic mention counting.

Tests target the pure, factored functions (no I/O):
  count_terms(records) -> (entity_counter, tag_counter)
  sorted_rows(counter)  -> list of (term, count) sorted count desc, term asc

All assertions use in-memory dicts / temp JSONL — no real data file.
"""
from __future__ import annotations

import csv
import json
import pathlib
from collections import Counter
from typing import Iterator

import pytest


# ---------------------------------------------------------------------------
# Import the module under test
# (tools/ is not a package; we load the module from disk via importlib)
# ---------------------------------------------------------------------------

import importlib.util
import sys
import os


def _load_extract_terms():
    """Load tools/extract_terms.py as a module without executing __main__."""
    here = pathlib.Path(__file__).parent
    root = here.parent
    mod_path = root / "tools" / "extract_terms.py"
    spec = importlib.util.spec_from_file_location("extract_terms", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_extract_terms()


# ---------------------------------------------------------------------------
# Helpers to build in-memory record dicts
# ---------------------------------------------------------------------------

def _record(entities=None, tags=None) -> dict:
    """Build a minimal annotation envelope with the given entities/tags."""
    rec = {"output_data": {"metadata": {}}}
    if entities is not None:
        rec["output_data"]["metadata"]["entities"] = entities
    if tags is not None:
        rec["output_data"]["metadata"]["tags"] = tags
    return rec


# ===========================================================================
# count_terms tests
# ===========================================================================

class TestCountTermsPerOccurrence:
    """Per-occurrence counting: same string twice in one record → count += 2."""

    def test_single_entity_once(self, mod):
        entity_ctr, tag_ctr = mod.count_terms([_record(entities=["FCA"])])
        assert entity_ctr["FCA"] == 1
        assert len(tag_ctr) == 0

    def test_entity_duplicate_in_one_record(self, mod):
        """Duplicate within a single record must contribute 2, not 1."""
        entity_ctr, _ = mod.count_terms([_record(entities=["FCA", "FCA"])])
        assert entity_ctr["FCA"] == 2

    def test_entity_across_records(self, mod):
        """Same entity in two different records → count == 2."""
        records = [_record(entities=["EBA"]), _record(entities=["EBA"])]
        entity_ctr, _ = mod.count_terms(records)
        assert entity_ctr["EBA"] == 2

    def test_tag_per_occurrence(self, mod):
        _, tag_ctr = mod.count_terms([_record(tags=["Basel III", "Basel III", "AML"])])
        assert tag_ctr["Basel III"] == 2
        assert tag_ctr["AML"] == 1

    def test_mixed_entities_and_tags(self, mod):
        records = [
            _record(entities=["FCA", "EBA"], tags=["AML"]),
            _record(entities=["FCA"], tags=["AML", "KYC"]),
        ]
        entity_ctr, tag_ctr = mod.count_terms(records)
        assert entity_ctr["FCA"] == 2
        assert entity_ctr["EBA"] == 1
        assert tag_ctr["AML"] == 2
        assert tag_ctr["KYC"] == 1


class TestWhitespaceTrimAndEmptyDrop:
    """Whitespace trimming and empty/whitespace-only entry dropping."""

    def test_leading_trailing_whitespace_trimmed(self, mod):
        entity_ctr, _ = mod.count_terms([_record(entities=["  EBA  "])])
        assert entity_ctr["EBA"] == 1
        assert "  EBA  " not in entity_ctr

    def test_empty_string_dropped(self, mod):
        entity_ctr, _ = mod.count_terms([_record(entities=[""])])
        assert len(entity_ctr) == 0

    def test_whitespace_only_dropped(self, mod):
        entity_ctr, _ = mod.count_terms([_record(entities=["   ", "\t", "\n"])])
        assert len(entity_ctr) == 0

    def test_trim_and_valid_mixed(self, mod):
        entity_ctr, _ = mod.count_terms([_record(entities=["  FCA  ", "", "  ", "EBA"])])
        assert entity_ctr["FCA"] == 1
        assert entity_ctr["EBA"] == 1
        assert len(entity_ctr) == 2

    def test_tag_whitespace_trimmed(self, mod):
        _, tag_ctr = mod.count_terms([_record(tags=["  Basel III  ", ""])])
        assert tag_ctr["Basel III"] == 1
        assert len(tag_ctr) == 1


class TestMissingOrMalformedFields:
    """Records with absent / None / non-list entities or tags are skipped gracefully."""

    def test_no_output_data_metadata_key(self, mod):
        record = {}  # no output_data at all
        entity_ctr, tag_ctr = mod.count_terms([record])
        assert len(entity_ctr) == 0
        assert len(tag_ctr) == 0

    def test_no_metadata_key(self, mod):
        record = {"output_data": {}}
        entity_ctr, tag_ctr = mod.count_terms([record])
        assert len(entity_ctr) == 0
        assert len(tag_ctr) == 0

    def test_entities_absent(self, mod):
        """Record with tags but no entities key — tags still counted."""
        _, tag_ctr = mod.count_terms([_record(tags=["AML"])])
        assert tag_ctr["AML"] == 1

    def test_tags_absent(self, mod):
        """Record with entities but no tags key — entities still counted."""
        entity_ctr, _ = mod.count_terms([_record(entities=["FCA"])])
        assert entity_ctr["FCA"] == 1

    def test_entities_is_none(self, mod):
        record = {"output_data": {"metadata": {"entities": None, "tags": ["AML"]}}}
        entity_ctr, tag_ctr = mod.count_terms([record])
        assert len(entity_ctr) == 0
        assert tag_ctr["AML"] == 1

    def test_tags_is_none(self, mod):
        record = {"output_data": {"metadata": {"entities": ["FCA"], "tags": None}}}
        entity_ctr, tag_ctr = mod.count_terms([record])
        assert entity_ctr["FCA"] == 1
        assert len(tag_ctr) == 0

    def test_entities_is_non_list(self, mod):
        """A string value for entities must be skipped, not iterated char-by-char."""
        record = {"output_data": {"metadata": {"entities": "FCA"}}}
        entity_ctr, _ = mod.count_terms([record])
        assert len(entity_ctr) == 0

    def test_tags_is_non_list(self, mod):
        record = {"output_data": {"metadata": {"tags": 42}}}
        _, tag_ctr = mod.count_terms([record])
        assert len(tag_ctr) == 0

    def test_empty_records_list(self, mod):
        entity_ctr, tag_ctr = mod.count_terms([])
        assert len(entity_ctr) == 0
        assert len(tag_ctr) == 0


# ===========================================================================
# sorted_rows tests — deterministic output order
# ===========================================================================

class TestSortedRows:
    """sorted_rows(counter) -> list of (term, count), count desc then term asc."""

    def test_higher_count_first(self, mod):
        ctr = Counter({"FCA": 10, "EBA": 5})
        rows = mod.sorted_rows(ctr)
        assert rows[0] == ("FCA", 10)
        assert rows[1] == ("EBA", 5)

    def test_equal_count_ascending_lex(self, mod):
        """Two terms with equal counts must come out in ascending lexical order."""
        ctr = Counter({"Zebra Corp": 3, "Alpha Inc": 3})
        rows = mod.sorted_rows(ctr)
        assert rows[0] == ("Alpha Inc", 3)
        assert rows[1] == ("Zebra Corp", 3)

    def test_three_way_tie_lex(self, mod):
        ctr = Counter({"C": 5, "A": 5, "B": 5})
        rows = mod.sorted_rows(ctr)
        assert [t for t, _ in rows] == ["A", "B", "C"]

    def test_mixed_counts_and_ties(self, mod):
        ctr = Counter({"X": 10, "B": 7, "A": 7, "Z": 1})
        rows = mod.sorted_rows(ctr)
        assert rows[0] == ("X", 10)
        assert rows[1] == ("A", 7)
        assert rows[2] == ("B", 7)
        assert rows[3] == ("Z", 1)

    def test_empty_counter(self, mod):
        assert mod.sorted_rows(Counter()) == []

    def test_single_entry(self, mod):
        rows = mod.sorted_rows(Counter({"EBA": 42}))
        assert rows == [("EBA", 42)]


# ===========================================================================
# write_csv tests — correct CSV columns, encoding, ordering preserved
# ===========================================================================

class TestWriteCsv:
    """write_csv(rows, path, term_col) writes a proper CSV and round-trips."""

    def test_entity_csv_roundtrip(self, mod, tmp_path):
        rows = [("FCA", 10), ("EBA", 5)]
        out = tmp_path / "entity_mentions.csv"
        mod.write_csv(rows, out, term_col="entity")
        with open(out, newline="", encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        assert reader[0] == {"entity": "FCA", "count": "10"}
        assert reader[1] == {"entity": "EBA", "count": "5"}

    def test_tag_csv_roundtrip(self, mod, tmp_path):
        rows = [("Basel III", 20), ("AML", 3)]
        out = tmp_path / "tag_mentions.csv"
        mod.write_csv(rows, out, term_col="tag")
        with open(out, newline="", encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        assert reader[0] == {"tag": "Basel III", "count": "20"}
        assert reader[1] == {"tag": "AML", "count": "3"}

    def test_empty_rows_writes_header_only(self, mod, tmp_path):
        out = tmp_path / "empty.csv"
        mod.write_csv([], out, term_col="entity")
        with open(out, newline="", encoding="utf-8") as fh:
            lines = fh.readlines()
        assert len(lines) == 1  # header only
        assert lines[0].strip() == "entity,count"


# ===========================================================================
# Integration: load from JSONL temp file -> count_terms -> write_csv
# ===========================================================================

class TestIntegrationWithJSONL:
    """End-to-end test using a tiny JSONL fixture written to a temp file."""

    def test_end_to_end(self, mod, tmp_path):
        records = [
            _record(entities=["FCA", "EBA", "FCA"], tags=["AML", "KYC"]),
            _record(entities=["EBA"], tags=["AML"]),
            _record(entities=[], tags=[]),
            {},  # no output_data — must not raise
        ]
        jsonl_path = tmp_path / "mini.jsonl"
        jsonl_path.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )

        entity_out = tmp_path / "entity_mentions.csv"
        tag_out = tmp_path / "tag_mentions.csv"

        # Use load_snapshot to stream, then count_terms, then write_csv
        from carver_showcase.ingest import load_snapshot

        loaded = list(load_snapshot(jsonl_path))
        entity_ctr, tag_ctr = mod.count_terms(loaded)

        assert entity_ctr["FCA"] == 2
        assert entity_ctr["EBA"] == 2
        assert tag_ctr["AML"] == 2
        assert tag_ctr["KYC"] == 1

        entity_rows = mod.sorted_rows(entity_ctr)
        tag_rows = mod.sorted_rows(tag_ctr)

        # Equal counts (FCA==EBA==2) → ascending lex: EBA before FCA
        assert entity_rows[0] == ("EBA", 2)
        assert entity_rows[1] == ("FCA", 2)

        mod.write_csv(entity_rows, entity_out, term_col="entity")
        mod.write_csv(tag_rows, tag_out, term_col="tag")

        with open(entity_out, newline="", encoding="utf-8") as fh:
            e_rows = list(csv.DictReader(fh))
        assert e_rows[0]["entity"] == "EBA"
        assert e_rows[1]["entity"] == "FCA"

        with open(tag_out, newline="", encoding="utf-8") as fh:
            t_rows = list(csv.DictReader(fh))
        assert t_rows[0] == {"tag": "AML", "count": "2"}
        assert t_rows[1] == {"tag": "KYC", "count": "1"}
