"""Tests for tools/canonicalize_regulators.py — regulator-name canonicalization.

EVERY test uses a STUBBED client. No network, no real OpenAI client, no API key.

Coverage:
  PART A  pure context aggregation (load/build/write/read CSV round-trip)
  PART B  request-builder + deterministic chunking
          response parser + schema validation
          detect -> retry -> bounded fallback (sync path)
          resume-or-submit sidecar + incremental cache + merge
          batch error surfacing (per-request error, error file, null output id)
          --sample N sync path + CLI wiring (seam, no real client)
          --sync-full workers>1 concurrent path (thread-safe input-driven stub)

The module under test keeps pure logic (context aggregation / chunking / request
build / parse / validate / hash / set-difference / retry decisions) in plain
functions, and all network calls behind an injectable `client` argument, so the
stub seam is tiny and no test ever constructs a real client.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import threading

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Load tools/canonicalize_regulators.py as a module without running __main__.
# ---------------------------------------------------------------------------

def _load_module():
    here = pathlib.Path(__file__).parent
    root = here.parent
    mod_path = root / "tools" / "canonicalize_regulators.py"
    spec = importlib.util.spec_from_file_location("canonicalize_regulators", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


from carver_showcase.config import (
    MAX_RETRIES,
    OPENAI_MODEL,
    REGULATOR_CHUNK_SIZE,
    REGULATOR_CTX_MAX_DIVISIONS,
    REGULATOR_CTX_MAX_DOMAINS,
    REGULATOR_CTX_MAX_TITLES,
    REGULATOR_CTX_TITLE_MAXLEN,
    REGULATOR_CTX_TOP_COUNTRIES,
)


# ===========================================================================
# Stub OpenAI client — records calls, returns scripted responses.
# Mirrors only the surface the module uses; constructing it needs no key.
# ===========================================================================

class _Obj:
    """Tiny attribute bag so responses look like SDK pydantic objects."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _chat_response(content: str):
    """Build a stub chat.completions response with one choice carrying content."""
    return _Obj(choices=[_Obj(message=_Obj(content=content))])


class _StubChat:
    def __init__(self, parent):
        self._parent = parent
        self.completions = self

    def create(self, **kwargs):
        self._parent.chat_calls.append(kwargs)
        resp = self._parent.chat_script.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


class _StubFiles:
    def __init__(self, parent):
        self._parent = parent

    def create(self, **kwargs):
        self._parent.files_create_calls.append(kwargs)
        return _Obj(id=self._parent.uploaded_file_id)

    def content(self, file_id):
        self._parent.files_content_calls.append(file_id)
        text = self._parent.output_file_text
        return _Obj(text=text, content=text.encode("utf-8"))


class _StubBatches:
    def __init__(self, parent):
        self._parent = parent

    def create(self, **kwargs):
        self._parent.batches_create_calls.append(kwargs)
        return self._parent.batch_script.pop(0)

    def retrieve(self, batch_id):
        self._parent.batches_retrieve_calls.append(batch_id)
        return self._parent.retrieve_script.pop(0)


class StubClient:
    """Injectable stand-in for an OpenAI client."""

    def __init__(self):
        self.chat_calls = []
        self.chat_script = []
        self.files_create_calls = []
        self.files_content_calls = []
        self.batches_create_calls = []
        self.batches_retrieve_calls = []
        self.uploaded_file_id = "file-up-1"
        self.output_file_text = ""
        self.batch_script = []
        self.retrieve_script = []

        self.chat = _StubChat(self)
        self.files = _StubFiles(self)
        self.batches = _StubBatches(self)


def _batch(**kw):
    base = dict(id="batch-1", status="validating", output_file_id=None, error_file_id=None)
    base.update(kw)
    return _Obj(**base)


# ---------------------------------------------------------------------------
# Helpers for building model output payloads in the chosen JSON-mode shape.
# ---------------------------------------------------------------------------

def _results_json(rows):
    """rows: list of (name, canonical_name, is_regulator) -> JSON-mode object string."""
    return json.dumps(
        {"results": [
            {"name": n, "canonical_name": c, "is_regulator": r} for (n, c, r) in rows
        ]}
    )


def _ctx(name, mentions=1):
    """Minimal context record for the batch/sync helpers."""
    return {
        "name": name,
        "mentions": mentions,
        "countries": [],
        "scope": "",
        "divisions": [],
        "domains": [],
        "sample_titles": [],
    }


# ===========================================================================
# PART A — pure context aggregation
# ===========================================================================

class TestBuildContext:
    def test_per_name_counts(self, mod):
        df = pd.DataFrame(
            {
                "regulator_name": ["FCA", "FCA", "EBA"],
                "jurisdiction_country": ["GB", "GB", "EU"],
                "jurisdiction_scope": ["national", "national", "bloc"],
                "regulator_division": [None, None, None],
                "base_url": [None, None, None],
                "title": [None, None, None],
            }
        )
        rows = mod.build_context(df)
        by_name = {r["name"]: r for r in rows}
        assert by_name["FCA"]["mentions"] == 2
        assert by_name["EBA"]["mentions"] == 1

    def test_ordering_mentions_desc_then_name_asc(self, mod):
        df = pd.DataFrame(
            {
                "regulator_name": ["B", "B", "A", "C", "C"],
                "jurisdiction_country": [None] * 5,
                "jurisdiction_scope": [None] * 5,
                "regulator_division": [None] * 5,
                "base_url": [None] * 5,
                "title": [None] * 5,
            }
        )
        rows = mod.build_context(df)
        # B(2) and C(2) tie on mentions -> name asc; A(1) last.
        assert [r["name"] for r in rows] == ["B", "C", "A"]

    def test_top_countries_capped_and_ranked(self, mod):
        countries = (
            ["GB"] * 5 + ["US"] * 4 + ["FR"] * 3 + ["DE"] * 2 + ["IT"] * 1
        )
        n = len(countries)
        df = pd.DataFrame(
            {
                "regulator_name": ["X"] * n,
                "jurisdiction_country": countries,
                "jurisdiction_scope": [None] * n,
                "regulator_division": [None] * n,
                "base_url": [None] * n,
                "title": [None] * n,
            }
        )
        rows = mod.build_context(df)
        assert rows[0]["countries"] == ["GB", "US", "FR"][:REGULATOR_CTX_TOP_COUNTRIES]
        assert len(rows[0]["countries"]) == REGULATOR_CTX_TOP_COUNTRIES

    def test_scope_is_single_most_frequent(self, mod):
        df = pd.DataFrame(
            {
                "regulator_name": ["X"] * 4,
                "jurisdiction_country": [None] * 4,
                "jurisdiction_scope": ["national", "national", "bloc", None],
                "regulator_division": [None] * 4,
                "base_url": [None] * 4,
                "title": [None] * 4,
            }
        )
        rows = mod.build_context(df)
        assert rows[0]["scope"] == "national"

    def test_scope_empty_string_when_all_missing(self, mod):
        df = pd.DataFrame(
            {
                "regulator_name": ["X"],
                "jurisdiction_country": [None],
                "jurisdiction_scope": [None],
                "regulator_division": [None],
                "base_url": [None],
                "title": [None],
            }
        )
        rows = mod.build_context(df)
        assert rows[0]["scope"] == ""

    def test_divisions_capped(self, mod):
        divs = ["Banking", "Banking", "Markets", "Insurance", "Pensions"]
        n = len(divs)
        df = pd.DataFrame(
            {
                "regulator_name": ["X"] * n,
                "jurisdiction_country": [None] * n,
                "jurisdiction_scope": [None] * n,
                "regulator_division": divs,
                "base_url": [None] * n,
                "title": [None] * n,
            }
        )
        rows = mod.build_context(df)
        assert len(rows[0]["divisions"]) == REGULATOR_CTX_MAX_DIVISIONS
        assert rows[0]["divisions"][0] == "Banking"  # most frequent first

    def test_domains_parsed_www_stripped_and_capped(self, mod):
        urls = [
            "https://www.fca.org.uk/news/x",  # host fca.org.uk
            "https://www.fca.org.uk/about",   # host fca.org.uk
            "bankofengland.co.uk",            # bare host
            "http://EXAMPLE.com/path",        # mixed case -> example.com
            "",                                # empty -> skipped
            "   ",                             # whitespace -> skipped
        ]
        n = len(urls)
        df = pd.DataFrame(
            {
                "regulator_name": ["X"] * n,
                "jurisdiction_country": [None] * n,
                "jurisdiction_scope": [None] * n,
                "regulator_division": [None] * n,
                "base_url": urls,
                "title": [None] * n,
            }
        )
        rows = mod.build_context(df)
        domains = rows[0]["domains"]
        assert len(domains) == REGULATOR_CTX_MAX_DOMAINS
        # fca.org.uk is most frequent (2) -> first; www. stripped.
        assert domains[0] == "fca.org.uk"
        assert all(not d.startswith("www.") for d in domains)

    def test_domains_empty_when_all_na(self, mod):
        df = pd.DataFrame(
            {
                "regulator_name": ["X", "X"],
                "jurisdiction_country": [None, None],
                "jurisdiction_scope": [None, None],
                "regulator_division": [None, None],
                "base_url": [None, None],
                "title": [None, None],
            }
        )
        rows = mod.build_context(df)
        assert rows[0]["domains"] == []

    def test_sample_titles_capped_and_truncated(self, mod):
        long_title = "T" * (REGULATOR_CTX_TITLE_MAXLEN + 50)
        titles = [long_title, long_title, "short one", "another", "third"]
        n = len(titles)
        df = pd.DataFrame(
            {
                "regulator_name": ["X"] * n,
                "jurisdiction_country": [None] * n,
                "jurisdiction_scope": [None] * n,
                "regulator_division": [None] * n,
                "base_url": [None] * n,
                "title": titles,
            }
        )
        rows = mod.build_context(df)
        sample = rows[0]["sample_titles"]
        assert len(sample) == REGULATOR_CTX_MAX_TITLES
        # Most frequent title (long_title x2) is first and truncated.
        assert sample[0] == "T" * REGULATOR_CTX_TITLE_MAXLEN
        assert all(len(t) <= REGULATOR_CTX_TITLE_MAXLEN for t in sample)

    def test_null_name_group_dropped(self, mod):
        df = pd.DataFrame(
            {
                "regulator_name": ["FCA", None, "EBA"],
                "jurisdiction_country": [None, None, None],
                "jurisdiction_scope": [None, None, None],
                "regulator_division": [None, None, None],
                "base_url": [None, None, None],
                "title": [None, None, None],
            }
        )
        rows = mod.build_context(df)
        assert {r["name"] for r in rows} == {"FCA", "EBA"}

    def test_literal_na_name_survives_csv_round_trip(self, mod, tmp_path):
        """A regulator literally named "NA" must survive a CSV round-trip."""
        df = pd.DataFrame(
            {
                "regulator_name": ["NA", "NA", "FCA"],
                "jurisdiction_country": ["US", "US", "GB"],
                "jurisdiction_scope": ["national", "national", "national"],
                "regulator_division": [None, None, None],
                "base_url": [None, None, None],
                "title": ["Title A", "Title A", "Title F"],
            }
        )
        rows = mod.build_context(df)
        assert "NA" in {r["name"] for r in rows}

        path = tmp_path / "regulator_context.csv"
        mod.write_context_csv(rows, path)
        back = mod.read_context_csv(path)
        names = {r["name"] for r in back}
        assert "NA" in names  # not lost to a pandas NaN token
        na_row = next(r for r in back if r["name"] == "NA")
        assert na_row["mentions"] == 2
        assert na_row["countries"] == ["US"]


class TestWriteContextCsv:
    def test_round_trips_json_list_fields(self, mod, tmp_path):
        rows = [
            {
                "name": "FCA",
                "mentions": 3,
                "countries": ["GB", "US"],
                "scope": "national",
                "divisions": ["Markets"],
                "domains": ["fca.org.uk"],
                "sample_titles": ["A title", "Another title"],
            }
        ]
        path = tmp_path / "ctx.csv"
        mod.write_context_csv(rows, path)
        # Header + JSON-encoded list fields present on disk.
        text = path.read_text(encoding="utf-8")
        assert text.splitlines()[0] == ",".join(mod.CONTEXT_HEADER)

        back = mod.read_context_csv(path)
        assert back[0]["countries"] == ["GB", "US"]
        assert back[0]["divisions"] == ["Markets"]
        assert back[0]["domains"] == ["fca.org.uk"]
        assert back[0]["sample_titles"] == ["A title", "Another title"]
        assert back[0]["scope"] == "national"
        assert back[0]["mentions"] == 3


class TestHostParsing:
    def test_host_of_full_url(self, mod):
        assert mod._host_of("https://www.fca.org.uk/news") == "fca.org.uk"

    def test_host_of_bare_host(self, mod):
        assert mod._host_of("bankofengland.co.uk") == "bankofengland.co.uk"

    def test_host_of_bare_host_with_path(self, mod):
        assert mod._host_of("example.com/a/b") == "example.com"

    def test_host_of_empty_and_non_str(self, mod):
        assert mod._host_of("") == ""
        assert mod._host_of("   ") == ""
        assert mod._host_of(None) == ""
        assert mod._host_of(float("nan")) == ""

    def test_host_of_lowercases(self, mod):
        assert mod._host_of("HTTPS://WWW.EXAMPLE.COM") == "example.com"

    def test_host_of_strips_port_from_full_url(self, mod):
        # A full URL whose netloc carries a port -> port stripped.
        assert mod._host_of("https://fca.org.uk:8080/news") == "fca.org.uk"

    def test_host_of_strips_port_from_bare_host(self, mod):
        # A bare host with a port (no scheme) -> port stripped.
        assert mod._host_of("fca.org.uk:8080") == "fca.org.uk"


# ===========================================================================
# PART B — Deterministic chunking + request builder
# ===========================================================================

class TestChunking:
    def test_chunks_of_chunk_size(self, mod):
        records = [_ctx(f"r{i}") for i in range(REGULATOR_CHUNK_SIZE * 2)]
        chunks = mod.chunk_records(records, REGULATOR_CHUNK_SIZE)
        assert len(chunks) == 2
        assert all(len(c) == REGULATOR_CHUNK_SIZE for c in chunks)

    def test_last_chunk_remainder(self, mod):
        records = [_ctx(f"r{i}") for i in range(REGULATOR_CHUNK_SIZE + 3)]
        chunks = mod.chunk_records(records, REGULATOR_CHUNK_SIZE)
        assert len(chunks) == 2
        assert len(chunks[0]) == REGULATOR_CHUNK_SIZE
        assert len(chunks[1]) == 3

    def test_empty_input(self, mod):
        assert mod.chunk_records([], REGULATOR_CHUNK_SIZE) == []


class TestRequestBuilder:
    def test_custom_id_format(self, mod):
        line = mod.build_request_line([_ctx("FCA")], 0)
        assert line["custom_id"] == "chunk-00000"
        assert mod.build_request_line([_ctx("X")], 9)["custom_id"] == "chunk-00009"
        assert mod.build_request_line([_ctx("X")], 12345)["custom_id"] == "chunk-12345"

    def test_request_body_shape(self, mod):
        line = mod.build_request_line([_ctx("FCA"), _ctx("EBA")], 0)
        assert line["method"] == "POST"
        assert line["url"] == "/v1/chat/completions"
        body = line["body"]
        assert body["model"] == OPENAI_MODEL
        assert body["temperature"] == 0
        assert body["response_format"]["type"] == "json_object"

    def test_system_message_carries_schema(self, mod):
        line = mod.build_request_line([_ctx("FCA")], 0)
        messages = line["body"]["messages"]
        system_text = " ".join(m["content"] for m in messages if m["role"] == "system")
        assert "canonical_name" in system_text
        assert "is_regulator" in system_text
        assert "English" in system_text

    def test_names_and_context_in_user_payload(self, mod):
        recs = [
            {**_ctx("FCA"), "countries": ["GB"], "domains": ["fca.org.uk"]},
            _ctx("EBA"),
        ]
        line = mod.build_request_line(recs, 0)
        user_text = " ".join(
            m["content"] for m in line["body"]["messages"] if m["role"] == "user"
        )
        assert "FCA" in user_text
        assert "EBA" in user_text
        assert "fca.org.uk" in user_text  # context travels with the name

    def test_write_requests_jsonl(self, mod, tmp_path):
        records = [_ctx(f"r{i:03d}") for i in range(REGULATOR_CHUNK_SIZE * 2 + 1)]
        out = tmp_path / "requests.jsonl"
        n = mod.write_request_file(records, out, REGULATOR_CHUNK_SIZE)
        assert n == 3
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["custom_id"] == "chunk-00000"
        assert json.loads(lines[-1])["custom_id"] == "chunk-00002"

    def test_chunk_map_maps_custom_id_to_names(self, mod):
        records = [_ctx(f"r{i}") for i in range(REGULATOR_CHUNK_SIZE + 2)]
        cmap = mod.chunk_map(records, REGULATOR_CHUNK_SIZE)
        assert set(cmap) == {"chunk-00000", "chunk-00001"}
        assert cmap["chunk-00001"] == ["r%d" % (REGULATOR_CHUNK_SIZE), "r%d" % (REGULATOR_CHUNK_SIZE + 1)]


# ===========================================================================
# Response parser + schema validation
# ===========================================================================

class TestParseResponse:
    def test_valid_parse(self, mod):
        sent = ["FCA", "Reuters"]
        content = _results_json([
            ("FCA", "Financial Conduct Authority", True),
            ("Reuters", "Reuters", False),
        ])
        resolved, missing = mod.parse_and_validate(content, sent)
        assert missing == []
        assert resolved["FCA"]["canonical_name"] == "Financial Conduct Authority"
        assert resolved["FCA"]["is_regulator"] is True
        assert resolved["Reuters"]["is_regulator"] is False

    def test_short_response_flags_only_missing(self, mod):
        sent = ["FCA", "EBA", "PRA"]
        content = _results_json([
            ("FCA", "Financial Conduct Authority", True),
            ("EBA", "European Banking Authority", True),
        ])
        resolved, missing = mod.parse_and_validate(content, sent)
        assert missing == ["PRA"]
        assert set(resolved) == {"FCA", "EBA"}

    def test_malformed_json_all_missing(self, mod):
        sent = ["FCA", "EBA"]
        resolved, missing = mod.parse_and_validate("not json {", sent)
        assert resolved == {}
        assert missing == ["FCA", "EBA"]  # order follows expected_names

    def test_bad_is_regulator_type_flagged(self, mod):
        sent = ["FCA"]
        # is_regulator is a string, not a bool -> rejected.
        content = json.dumps(
            {"results": [{"name": "FCA", "canonical_name": "Financial Conduct Authority",
                          "is_regulator": "true"}]}
        )
        resolved, missing = mod.parse_and_validate(content, sent)
        assert "FCA" in missing
        assert "FCA" not in resolved

    def test_empty_canonical_name_flagged(self, mod):
        sent = ["FCA"]
        content = _results_json([("FCA", "", True)])
        resolved, missing = mod.parse_and_validate(content, sent)
        assert "FCA" in missing

    def test_missing_name_field_flagged(self, mod):
        sent = ["FCA"]
        content = json.dumps(
            {"results": [{"canonical_name": "Financial Conduct Authority",
                          "is_regulator": True}]}
        )
        resolved, missing = mod.parse_and_validate(content, sent)
        assert "FCA" in missing

    def test_extra_name_not_in_sent_ignored(self, mod):
        sent = ["FCA"]
        content = _results_json([
            ("FCA", "Financial Conduct Authority", True),
            ("GHOST", "Ghost Co", False),
        ])
        resolved, missing = mod.parse_and_validate(content, sent)
        assert set(resolved) == {"FCA"}
        assert missing == []

    def test_is_regulator_false_is_valid(self, mod):
        """is_regulator False is a real value (bool), not a failure."""
        sent = ["Bloomberg"]
        content = _results_json([("Bloomberg", "Bloomberg", False)])
        resolved, missing = mod.parse_and_validate(content, sent)
        assert missing == []
        assert resolved["Bloomberg"]["is_regulator"] is False


class TestExtractOutputLine:
    def test_normal_output_line(self, mod):
        content = _results_json([("FCA", "Financial Conduct Authority", True)])
        line = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": content}}]
            }},
        })
        custom_id, body_content, errored = mod.extract_output_line(line)
        assert custom_id == "chunk-00000"
        assert errored is False
        resolved, _ = mod.parse_and_validate(body_content, ["FCA"])
        assert "FCA" in resolved

    def test_per_request_error_status(self, mod):
        line = json.dumps(
            {"custom_id": "chunk-00000", "error": None,
             "response": {"status_code": 500, "body": None}}
        )
        custom_id, content, errored = mod.extract_output_line(line)
        assert custom_id == "chunk-00000"
        assert content == ""
        assert errored is True

    def test_top_level_error(self, mod):
        line = json.dumps(
            {"custom_id": "chunk-00000",
             "error": {"code": "rate_limit", "message": "slow"}, "response": None}
        )
        custom_id, content, errored = mod.extract_output_line(line)
        assert custom_id == "chunk-00000"
        assert errored is True

    def test_malformed_json_line(self, mod):
        custom_id, content, errored = mod.extract_output_line("{not json")
        assert custom_id is None
        assert content == ""
        assert errored is False


# ===========================================================================
# detect -> retry -> bounded fallback (sync path)
# ===========================================================================

class TestRetryAndFallback:
    def test_malformed_then_valid_resolves(self, mod):
        client = StubClient()
        client.chat_script = [
            _chat_response("garbage not json"),
            _chat_response(_results_json([("FCA", "Financial Conduct Authority", True)])),
        ]
        resolved, fallback = mod.resolve_with_retry(
            [_ctx("FCA")], client, max_retries=MAX_RETRIES
        )
        assert len(client.chat_calls) == 2
        assert fallback == 0
        assert resolved["FCA"]["canonical_name"] == "Financial Conduct Authority"

    def test_persistent_malformed_falls_back_conservatively(self, mod):
        """Stays malformed -> keep raw name, is_regulator=True (never dropped)."""
        client = StubClient()
        client.chat_script = [_chat_response("garbage") for _ in range(MAX_RETRIES + 1)]
        resolved, fallback = mod.resolve_with_retry(
            [_ctx("Mystery Source")], client, max_retries=MAX_RETRIES
        )
        assert len(client.chat_calls) == MAX_RETRIES + 1
        assert fallback == 1
        assert resolved["Mystery Source"]["canonical_name"] == "Mystery Source"
        assert resolved["Mystery Source"]["is_regulator"] is True

    def test_partial_retry_only_resends_unresolved(self, mod):
        client = StubClient()
        client.chat_script = [
            _chat_response(_results_json([("FCA", "Financial Conduct Authority", True)])),
            _chat_response(_results_json([("EBA", "European Banking Authority", True)])),
        ]
        resolved, fallback = mod.resolve_with_retry(
            [_ctx("FCA"), _ctx("EBA")], client, max_retries=MAX_RETRIES
        )
        assert fallback == 0
        retry_user = " ".join(
            m["content"] for m in client.chat_calls[1]["messages"] if m["role"] == "user"
        )
        assert "EBA" in retry_user
        assert "FCA" not in retry_user
        assert set(resolved) == {"FCA", "EBA"}

    def test_fallback_warning_logged(self, mod, caplog):
        import logging
        client = StubClient()
        client.chat_script = [_chat_response("garbage") for _ in range(MAX_RETRIES + 1)]
        with caplog.at_level(logging.WARNING):
            mod.resolve_with_retry([_ctx("Mystery")], client, max_retries=MAX_RETRIES)
        assert any("fell back" in r.message for r in caplog.records)


# ===========================================================================
# Incremental cache + input hash + merge
# ===========================================================================

class TestIncrementalCache:
    def test_excludes_already_cached(self, mod, tmp_path):
        canonical = tmp_path / "regulator_canonical.csv"
        with open(canonical, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(mod.CANONICAL_HEADER)
            w.writerow(["FCA", "Financial Conduct Authority", "True", "5"])
        todo = mod.records_to_classify(
            [_ctx("FCA"), _ctx("EBA"), _ctx("PRA")], canonical
        )
        assert [r["name"] for r in todo] == ["EBA", "PRA"]

    def test_no_cache_file_all_todo(self, mod, tmp_path):
        todo = mod.records_to_classify([_ctx("FCA"), _ctx("EBA")], tmp_path / "nope.csv")
        assert [r["name"] for r in todo] == ["FCA", "EBA"]

    def test_literal_na_name_treated_as_cached(self, mod, tmp_path):
        """A cached regulator literally named "NA" is not re-classified."""
        canonical = tmp_path / "regulator_canonical.csv"
        with open(canonical, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(mod.CANONICAL_HEADER)
            w.writerow(["NA", "North American Authority", "True", "3"])
        todo = mod.records_to_classify([_ctx("NA"), _ctx("FCA")], canonical)
        assert [r["name"] for r in todo] == ["FCA"]  # NA already cached


class TestInputHash:
    def test_hash_set_order_invariant_content_sensitive(self, mod):
        h1 = mod.input_hash(["FCA", "EBA"])
        h2 = mod.input_hash(["EBA", "FCA"])  # different order, same set
        h3 = mod.input_hash(["FCA", "PRA"])
        assert h1 == h2
        assert h1 != h3
        assert isinstance(h1, str) and len(h1) == 64


class TestMergeIntoCache:
    def test_writes_four_columns_with_mentions(self, mod, tmp_path):
        canonical = tmp_path / "regulator_canonical.csv"
        results = {
            "FCA": {"name": "FCA", "canonical_name": "Financial Conduct Authority",
                    "is_regulator": True},
        }
        context = {"FCA": _ctx("FCA", mentions=42)}
        written = mod.merge_into_cache(results, context, canonical)
        assert written == 1
        with open(canonical, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert list(rows[0].keys()) == mod.CANONICAL_HEADER
        assert rows[0]["regulator_name"] == "FCA"
        assert rows[0]["canonical_regulator"] == "Financial Conduct Authority"
        assert rows[0]["is_regulator"] == "True"
        assert rows[0]["mentions"] == "42"

    def test_incremental_skips_already_present(self, mod, tmp_path):
        canonical = tmp_path / "regulator_canonical.csv"
        with open(canonical, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(mod.CANONICAL_HEADER)
            w.writerow(["FCA", "Financial Conduct Authority", "True", "5"])
        results = {
            "FCA": {"name": "FCA", "canonical_name": "Financial Conduct Authority",
                    "is_regulator": True},
            "EBA": {"name": "EBA", "canonical_name": "European Banking Authority",
                    "is_regulator": True},
        }
        context = {"FCA": _ctx("FCA", 5), "EBA": _ctx("EBA", 3)}
        written = mod.merge_into_cache(results, context, canonical)
        assert written == 1  # only EBA
        with open(canonical, newline="", encoding="utf-8") as fh:
            names = [r["regulator_name"] for r in csv.DictReader(fh)]
        assert names == ["FCA", "EBA"]


# ===========================================================================
# Sidecar read/write/clear + hash stability/mismatch
# ===========================================================================

class TestSidecar:
    def test_roundtrip_and_clear(self, mod, tmp_path):
        sidecar = tmp_path / "state.json"
        state = {"batch_id": "b1", "input_sha256": "deadbeef", "model": OPENAI_MODEL}
        mod.write_sidecar(sidecar, state)
        assert mod.read_sidecar(sidecar) == state
        assert not (tmp_path / "state.json.tmp").exists()  # atomic write
        mod.clear_sidecar(sidecar)
        assert not sidecar.exists()
        assert mod.read_sidecar(sidecar) is None  # missing -> None

    def test_clear_is_idempotent(self, mod, tmp_path):
        mod.clear_sidecar(tmp_path / "absent.json")  # no error

    def test_submit_fresh_writes_sidecar_before_polling(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-XYZ", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-XYZ", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _results_json([
                    ("FCA", "Financial Conduct Authority", True),
                    ("EBA", "European Banking Authority", True),
                ])}}]
            }},
        }) + "\n"

        recorded = {}
        orig_write = mod.write_sidecar

        def spy_write(path, state):
            recorded["batch_id"] = state["batch_id"]
            recorded["hash"] = state["input_sha256"]
            recorded["polled_before"] = len(client.batches_retrieve_calls)
            return orig_write(path, state)

        mod.write_sidecar = spy_write
        try:
            mod.run_full(
                client,
                records=[_ctx("FCA"), _ctx("EBA")],
                requests_path=tmp_path / "requests.jsonl",
                sidecar_path=tmp_path / "state.json",
                canonical_csv=tmp_path / "regulator_canonical.csv",
                chunk_size=REGULATOR_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        finally:
            mod.write_sidecar = orig_write

        assert len(client.batches_create_calls) == 1
        assert recorded["batch_id"] == "batch-XYZ"
        assert recorded["polled_before"] == 0  # sidecar written before any poll
        assert recorded["hash"] == mod.input_hash(["FCA", "EBA"])

    def test_resume_matching_hash_does_not_create_batch(self, mod, tmp_path):
        client = StubClient()
        client.retrieve_script = [
            _batch(id="batch-EXIST", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _results_json([
                    ("FCA", "Financial Conduct Authority", True),
                ])}}]
            }},
        }) + "\n"

        sidecar = tmp_path / "state.json"
        mod.write_sidecar(sidecar, {
            "batch_id": "batch-EXIST",
            "model": OPENAI_MODEL,
            "input_sha256": mod.input_hash(["FCA"]),
        })

        mod.run_full(
            client,
            records=[_ctx("FCA")],
            requests_path=tmp_path / "requests.jsonl",
            sidecar_path=sidecar,
            canonical_csv=tmp_path / "regulator_canonical.csv",
            chunk_size=REGULATOR_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert client.batches_create_calls == []
        assert client.files_create_calls == []
        assert client.batches_retrieve_calls == ["batch-EXIST"]

    def test_hash_mismatch_submits_fresh(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-NEW", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-NEW", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _results_json([
                    ("PRA", "Prudential Regulation Authority", True),
                ])}}]
            }},
        }) + "\n"

        sidecar = tmp_path / "state.json"
        mod.write_sidecar(sidecar, {
            "batch_id": "batch-OLD",
            "model": OPENAI_MODEL,
            "input_sha256": mod.input_hash(["DIFFERENT"]),
        })

        mod.run_full(
            client,
            records=[_ctx("PRA")],
            requests_path=tmp_path / "requests.jsonl",
            sidecar_path=sidecar,
            canonical_csv=tmp_path / "regulator_canonical.csv",
            chunk_size=REGULATOR_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert len(client.batches_create_calls) == 1

    def test_sidecar_cleared_after_merge(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-1", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-1", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _results_json([
                    ("FCA", "Financial Conduct Authority", True),
                ])}}]
            }},
        }) + "\n"

        sidecar = tmp_path / "state.json"
        canonical = tmp_path / "regulator_canonical.csv"
        mod.run_full(
            client,
            records=[_ctx("FCA")],
            requests_path=tmp_path / "requests.jsonl",
            sidecar_path=sidecar,
            canonical_csv=canonical,
            chunk_size=REGULATOR_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert not sidecar.exists()
        with open(canonical, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert any(r["regulator_name"] == "FCA" for r in rows)

    def test_terminal_failed_clears_sidecar(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-F", status="validating")]
        client.retrieve_script = [_batch(id="batch-F", status="failed")]

        sidecar = tmp_path / "state.json"
        with pytest.raises(mod.BatchTerminalError):
            mod.run_full(
                client,
                records=[_ctx("FCA")],
                requests_path=tmp_path / "requests.jsonl",
                sidecar_path=sidecar,
                canonical_csv=tmp_path / "regulator_canonical.csv",
                chunk_size=REGULATOR_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        assert not sidecar.exists()

    def test_complete_cache_no_batch(self, mod, tmp_path):
        client = StubClient()
        canonical = tmp_path / "regulator_canonical.csv"
        with open(canonical, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(mod.CANONICAL_HEADER)
            w.writerow(["FCA", "Financial Conduct Authority", "True", "5"])

        result = mod.run_full(
            client,
            records=[_ctx("FCA")],
            requests_path=tmp_path / "requests.jsonl",
            sidecar_path=tmp_path / "state.json",
            canonical_csv=canonical,
            chunk_size=REGULATOR_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert client.batches_create_calls == []
        assert client.batches_retrieve_calls == []
        assert result["submitted"] is False


# ===========================================================================
# Batch error surfacing: per-request error, error file, null output id
# ===========================================================================

class TestBatchErrorSurfacing:
    def test_status_500_counted_and_retried(self, mod):
        client = StubClient()
        client.chat_script = [
            _chat_response(_results_json([
                ("FCA", "Financial Conduct Authority", True),
                ("EBA", "European Banking Authority", True),
            ])),
        ]
        expected = {"chunk-00000": ["FCA", "EBA"]}
        context = {"FCA": _ctx("FCA"), "EBA": _ctx("EBA")}
        output_text = json.dumps(
            {"custom_id": "chunk-00000", "error": None,
             "response": {"status_code": 500, "body": None}}
        ) + "\n"

        results, fallback, batch_errors = mod.collect_results(
            output_text, expected, context, client, max_retries=MAX_RETRIES
        )
        assert batch_errors == 1
        assert len(client.chat_calls) == 1  # retried synchronously
        assert set(results) == {"FCA", "EBA"}
        assert fallback == 0

    def test_top_level_error_counted_and_falls_back(self, mod):
        client = StubClient()
        client.chat_script = [_chat_response("garbage") for _ in range(MAX_RETRIES + 1)]
        expected = {"chunk-00000": ["Mystery"]}
        context = {"Mystery": _ctx("Mystery")}
        output_text = json.dumps(
            {"custom_id": "chunk-00000", "error": {"code": "server_error"},
             "response": None}
        ) + "\n"

        results, fallback, batch_errors = mod.collect_results(
            output_text, expected, context, client, max_retries=MAX_RETRIES
        )
        assert batch_errors == 1
        assert fallback == 1
        assert results["Mystery"]["canonical_name"] == "Mystery"  # not lost
        assert results["Mystery"]["is_regulator"] is True

    def test_collect_results_warns_on_errors(self, mod, caplog):
        import logging
        client = StubClient()
        client.chat_script = [
            _chat_response(_results_json([("FCA", "Financial Conduct Authority", True)])),
        ]
        expected = {"chunk-00000": ["FCA"]}
        context = {"FCA": _ctx("FCA")}
        output_text = json.dumps(
            {"custom_id": "chunk-00000", "error": None,
             "response": {"status_code": 429, "body": None}}
        ) + "\n"
        with caplog.at_level(logging.WARNING):
            mod.collect_results(output_text, expected, context, client, max_retries=MAX_RETRIES)
        assert any("error status" in r.message for r in caplog.records)

    def test_collect_results_absent_chunk_retried_synchronously(self, mod):
        """A custom_id that produces NO output line at all is routed through the
        synchronous retry path so every input name is still resolved.

        Setup: two chunks (chunk-00000 with FCA, chunk-00001 with EBA + PRA).
        Output text contains a valid line ONLY for chunk-00000; chunk-00001 is
        entirely absent from the output.  The test asserts:
          (a) FCA is resolved from the batch output line as normal.
          (b) EBA and PRA (absent chunk) are resolved via the sync retry path.
          (c) all_results covers every input name with zero fallbacks.
        """
        client = StubClient()
        # The sync retry will be called once for the two absent names.
        client.chat_script = [
            _chat_response(_results_json([
                ("EBA", "European Banking Authority", True),
                ("PRA", "Prudential Regulation Authority", True),
            ])),
        ]
        expected = {
            "chunk-00000": ["FCA"],
            "chunk-00001": ["EBA", "PRA"],
        }
        context = {
            "FCA": _ctx("FCA"),
            "EBA": _ctx("EBA"),
            "PRA": _ctx("PRA"),
        }
        # Only chunk-00000 has an output line; chunk-00001 is absent.
        output_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _results_json([
                    ("FCA", "Financial Conduct Authority", True),
                ])}}]
            }},
        }) + "\n"

        all_results, fallback, batch_errors = mod.collect_results(
            output_text, expected, context, client, max_retries=MAX_RETRIES
        )

        # (a) FCA resolved from batch output.
        assert all_results["FCA"]["canonical_name"] == "Financial Conduct Authority"
        # (b) EBA and PRA resolved via sync retry (absent chunk path).
        assert all_results["EBA"]["canonical_name"] == "European Banking Authority"
        assert all_results["PRA"]["canonical_name"] == "Prudential Regulation Authority"
        # (c) full coverage, no fallbacks, no batch errors.
        assert set(all_results) == {"FCA", "EBA", "PRA"}
        assert fallback == 0
        assert batch_errors == 0
        # The sync client was called exactly once (for the absent chunk's two names).
        assert len(client.chat_calls) == 1

    def test_error_file_id_fetched_and_surfaced(self, mod, tmp_path, caplog):
        import logging
        client = StubClient()
        client.batch_script = [_batch(id="batch-EF", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-EF", status="completed",
                   output_file_id="file-out-1", error_file_id="file-err-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _results_json([
                    ("FCA", "Financial Conduct Authority", True),
                ])}}]
            }},
        }) + "\n"

        with caplog.at_level(logging.WARNING):
            result = mod.run_full(
                client,
                records=[_ctx("FCA")],
                requests_path=tmp_path / "requests.jsonl",
                sidecar_path=tmp_path / "state.json",
                canonical_csv=tmp_path / "regulator_canonical.csv",
                chunk_size=REGULATOR_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        assert "file-err-1" in client.files_content_calls
        assert result["batch_errors"] >= 1
        assert any("never ran" in r.message for r in caplog.records)

    def test_null_output_file_id_guarded(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-NULL", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-NULL", status="completed",
                   output_file_id=None, error_file_id="file-err-1"),
        ]
        client.output_file_text = "some error record\n"
        client.chat_script = [
            _chat_response(_results_json([("FCA", "Financial Conduct Authority", True)])),
        ]

        canonical = tmp_path / "regulator_canonical.csv"
        result = mod.run_full(
            client,
            records=[_ctx("FCA")],
            requests_path=tmp_path / "requests.jsonl",
            sidecar_path=tmp_path / "state.json",
            canonical_csv=canonical,
            chunk_size=REGULATOR_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert None not in client.files_content_calls
        assert client.files_content_calls == ["file-err-1"]
        with open(canonical, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert any(r["regulator_name"] == "FCA" for r in rows)
        assert result["batch_errors"] >= 1


# ===========================================================================
# Poll loop bound + transient error tolerance
# ===========================================================================

class TestPollLoopBound:
    def test_poll_max_wait_exceeded_raises(self, mod):
        client = StubClient()
        client.retrieve_script = [_batch(id="batch-STUCK", status="in_progress")] * 50
        ticks = iter(range(0, 1000, 100))
        with pytest.raises(mod.BatchTerminalError):
            mod._poll_until_terminal(
                client, "batch-STUCK", poll_interval=0, max_wait=150,
                sleep=lambda _s: None, now=lambda: next(ticks),
            )

    def test_poll_tolerates_transient_errors(self, mod):
        client = StubClient()

        class _Flaky:
            def __init__(self):
                self.calls = 0

            def retrieve(self, batch_id):
                self.calls += 1
                if self.calls <= 2:
                    raise RuntimeError("transient")
                return _batch(id=batch_id, status="completed", output_file_id="file-out-1")

        client.batches = _Flaky()
        batch = mod._poll_until_terminal(
            client, "batch-FLAKY", poll_interval=0, sleep=lambda _s: None
        )
        assert batch.status == "completed"

    def test_poll_gives_up_after_too_many_errors(self, mod):
        client = StubClient()

        class _AlwaysFails:
            def retrieve(self, batch_id):
                raise RuntimeError("down")

        client.batches = _AlwaysFails()
        with pytest.raises(mod.BatchTerminalError):
            mod._poll_until_terminal(
                client, "batch-DEAD", poll_interval=0, sleep=lambda _s: None
            )


# ===========================================================================
# --sample N sync path + CLI wiring (seam; no real client)
# ===========================================================================

class TestSamplePath:
    def test_sample_uses_sync_path_only(self, mod, tmp_path):
        client = StubClient()
        client.chat_script = [
            _chat_response(_results_json([
                ("FCA", "Financial Conduct Authority", True),
                ("Reuters", "Reuters", False),
            ])),
        ]
        resolved = mod.run_sample(
            client, [_ctx("FCA"), _ctx("Reuters")], max_retries=MAX_RETRIES
        )
        assert client.files_create_calls == []
        assert client.batches_create_calls == []
        assert client.batches_retrieve_calls == []
        assert len(client.chat_calls) == 1
        assert set(resolved) == {"FCA", "Reuters"}

    def test_sample_prints_results(self, mod, capsys):
        client = StubClient()
        client.chat_script = [
            _chat_response(_results_json([("FCA", "Financial Conduct Authority", True)])),
        ]
        mod.run_sample(client, [_ctx("FCA")], max_retries=MAX_RETRIES)
        out = capsys.readouterr().out
        assert "FCA" in out
        assert "Financial Conduct Authority" in out


class TestClientSeam:
    def test_make_client_is_a_seam(self, mod):
        assert hasattr(mod, "make_client")
        assert callable(mod.make_client)

    def test_build_arg_parser_has_sample(self, mod):
        parser = mod.build_arg_parser()
        assert parser.parse_args(["--sample", "5"]).sample == 5
        assert parser.parse_args([]).sample is None

    def test_build_arg_parser_has_sync_full(self, mod):
        parser = mod.build_arg_parser()
        assert parser.parse_args(["--sync-full"]).sync_full is True
        assert parser.parse_args([]).sync_full is False


# ===========================================================================
# --sync-full: run_sync_full orchestration
# ===========================================================================

def _write_context_csv(path: pathlib.Path, names: list[str]) -> None:
    """Write a minimal context CSV at ``path`` with the given names."""
    import csv as _csv
    import json as _json

    header = ["regulator_name", "mentions", "countries", "scope",
              "divisions", "domains", "sample_titles"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = _csv.writer(fh)
        writer.writerow(header)
        for name in names:
            writer.writerow([
                name, 1,
                _json.dumps([]), "",
                _json.dumps([]), _json.dumps([]), _json.dumps([]),
            ])


class TestRunSyncFull:
    def test_classifies_all_and_checkpoints(self, mod, tmp_path):
        """All 5 names across >=2 chunks end up in the cache with correct values."""
        names = ["FCA", "EBA", "PRA", "SEC", "CFTC"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        client = StubClient()
        # chunk_size=3: chunk 0 = [FCA, EBA, PRA], chunk 1 = [SEC, CFTC]
        client.chat_script = [
            _chat_response(_results_json([
                ("FCA", "Financial Conduct Authority", True),
                ("EBA", "European Banking Authority", True),
                ("PRA", "Prudential Regulation Authority", True),
            ])),
            _chat_response(_results_json([
                ("SEC", "Securities and Exchange Commission", True),
                ("CFTC", "Commodity Futures Trading Commission", True),
            ])),
        ]

        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=3,
            max_retries=0,
            sleep_between_chunks=0,
        )

        # All 5 names written to the cache.
        with open(canonical_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cached_names = {r["regulator_name"] for r in rows}
        assert cached_names == set(names)

        # Verify canonical values for spot check.
        by_name = {r["regulator_name"]: r for r in rows}
        assert by_name["FCA"]["canonical_regulator"] == "Financial Conduct Authority"
        assert by_name["SEC"]["canonical_regulator"] == "Securities and Exchange Commission"
        assert by_name["FCA"]["is_regulator"] == "True"

        # Summary counts.
        assert summary["total_names"] == 5
        assert summary["classified"] == 5
        assert summary["fallback_count"] == 0
        assert summary["already_cached"] == 0

    def test_recovers_from_chunk_exception(self, mod, tmp_path):
        """Names from a chunk that raises are recovered via the retry/fallback path."""
        names = ["FCA", "EBA", "PRA"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        client = StubClient()
        # chunk_size=2: chunk 0 = [FCA, EBA] raises; chunk 1 = [PRA] succeeds.
        # After the loop, the retry path handles FCA + EBA; we exhaust retries
        # so they fall back to (raw name, is_regulator=True).
        client.chat_script = (
            [RuntimeError("simulated API failure")]           # chunk 0 raises
            + [_chat_response(_results_json([                 # chunk 1 succeeds
                ("PRA", "Prudential Regulation Authority", True),
            ]))]
            + [_chat_response("garbage")] * (MAX_RETRIES + 1)  # retry fallback
        )

        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=2,
            max_retries=MAX_RETRIES,
            sleep_between_chunks=0,
        )

        # No name is lost — all 3 must appear in the cache.
        with open(canonical_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cached_names = {r["regulator_name"] for r in rows}
        assert cached_names == {"FCA", "EBA", "PRA"}

        # FCA and EBA fell back (is_regulator=True, canonical = raw name).
        by_name = {r["regulator_name"]: r for r in rows}
        assert by_name["FCA"]["canonical_regulator"] == "FCA"
        assert by_name["FCA"]["is_regulator"] == "True"
        assert by_name["EBA"]["canonical_regulator"] == "EBA"
        assert by_name["EBA"]["is_regulator"] == "True"
        # PRA was classified correctly.
        assert by_name["PRA"]["canonical_regulator"] == "Prudential Regulation Authority"

        # Summary: 2 fallbacks (FCA + EBA), PRA classified normally.
        assert summary["fallback_count"] == 2
        assert summary["total_names"] == 3

    def test_resumes_skips_cached(self, mod, tmp_path):
        """Pre-cached names are skipped; already_cached count is correct."""
        names = ["FCA", "EBA", "PRA"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        # Pre-populate FCA in the cache.
        with open(canonical_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["regulator_name", "canonical_regulator", "is_regulator", "mentions"])
            w.writerow(["FCA", "Financial Conduct Authority", "True", "1"])

        client = StubClient()
        # Only EBA and PRA need classifying (2 names, 1 chunk with size=10).
        client.chat_script = [
            _chat_response(_results_json([
                ("EBA", "European Banking Authority", True),
                ("PRA", "Prudential Regulation Authority", True),
            ])),
        ]

        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=10,
            max_retries=0,
            sleep_between_chunks=0,
        )

        # All 3 names in cache after the run.
        with open(canonical_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cached_names = {r["regulator_name"] for r in rows}
        assert cached_names == {"FCA", "EBA", "PRA"}

        assert summary["already_cached"] == 1
        assert summary["classified"] == 2
        assert summary["total_names"] == 3
        assert summary["fallback_count"] == 0

    def test_all_cached_returns_early(self, mod, tmp_path):
        """When every name is cached, the function returns immediately with classified=0."""
        names = ["FCA", "EBA"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        # Pre-populate all names.
        with open(canonical_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["regulator_name", "canonical_regulator", "is_regulator", "mentions"])
            w.writerow(["FCA", "Financial Conduct Authority", "True", "1"])
            w.writerow(["EBA", "European Banking Authority", "True", "1"])

        client = StubClient()  # no chat_script needed — should not be called
        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=10,
            max_retries=0,
            sleep_between_chunks=0,
        )

        assert client.chat_calls == []
        assert summary["classified"] == 0
        assert summary["already_cached"] == 2
        assert summary["fallback_count"] == 0

    def test_run_sync_full_paces_between_chunks(self, mod, tmp_path):
        """time.sleep is called once per chunk with the configured interval."""
        from unittest.mock import patch

        names = ["FCA", "EBA", "PRA", "SEC"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        client = StubClient()
        # chunk_size=2 -> 2 chunks: [FCA, EBA] and [PRA, SEC]
        client.chat_script = [
            _chat_response(_results_json([
                ("FCA", "Financial Conduct Authority", True),
                ("EBA", "European Banking Authority", True),
            ])),
            _chat_response(_results_json([
                ("PRA", "Prudential Regulation Authority", True),
                ("SEC", "Securities and Exchange Commission", True),
            ])),
        ]

        with patch("tools.canonicalize_regulators.time.sleep") as mock_sleep:
            mod.run_sync_full(
                client,
                context_csv=context_csv,
                canonical_csv=canonical_csv,
                chunk_size=2,
                max_retries=0,
                sleep_between_chunks=0.3,
            )

        # sleep called once per chunk (2 chunks -> 2 sleep calls), each with 0.3.
        assert mock_sleep.call_count == 2
        for call in mock_sleep.call_args_list:
            assert call.args[0] == 0.3

    def test_run_sync_full_no_sleep_when_zero(self, mod, tmp_path):
        """sleep_between_chunks=0 results in no time.sleep calls at all."""
        from unittest.mock import patch

        names = ["FCA", "EBA", "PRA"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        client = StubClient()
        # chunk_size=2 -> 2 chunks: [FCA, EBA] and [PRA]
        client.chat_script = [
            _chat_response(_results_json([
                ("FCA", "Financial Conduct Authority", True),
                ("EBA", "European Banking Authority", True),
            ])),
            _chat_response(_results_json([
                ("PRA", "Prudential Regulation Authority", True),
            ])),
        ]

        with patch("tools.canonicalize_regulators.time.sleep") as mock_sleep:
            mod.run_sync_full(
                client,
                context_csv=context_csv,
                canonical_csv=canonical_csv,
                chunk_size=2,
                max_retries=0,
                sleep_between_chunks=0,
            )

        assert mock_sleep.call_count == 0


# ===========================================================================
# Concurrent (workers > 1) path — thread-safe input-driven stub
# ===========================================================================

# The existing StubClient.chat_script pops responses by CALL ORDER, which races
# under concurrent workers.  For the concurrent tests we use an input-driven
# stub: it inspects the names present in the user message and synthesises a
# deterministic response, so the result is independent of call order.

_CANONICAL_OVERRIDE = {
    "FCA": "Financial Conduct Authority",
    "EBA": "European Banking Authority",
    "PRA": "Prudential Regulation Authority",
    "SEC": "Securities and Exchange Commission",
    "CFTC": "Commodity Futures Trading Commission",
    "FINRA": "Financial Industry Regulatory Authority",
    "OCC": "Office of the Comptroller of the Currency",
    "FDIC": "Federal Deposit Insurance Corporation",
}


def _echo_response_for_messages(messages: list[dict]) -> "_Obj":
    """Build a valid JSON-mode response by extracting names from the user message.

    Parses the JSON records embedded in the user message, builds a
    ``{"results": [...]}`` payload echoing every name found there, and wraps it
    in a stub chat completion object.  Thread-safe because it reads only the
    immutable ``messages`` input.
    """
    user_text = " ".join(m["content"] for m in messages if m["role"] == "user")
    # The user message embeds the JSON array after the first newline.
    try:
        json_start = user_text.index("[")
        records = json.loads(user_text[json_start:])
    except (ValueError, json.JSONDecodeError):
        records = []

    results = [
        {
            "name": r["name"],
            "canonical_name": _CANONICAL_OVERRIDE.get(r["name"], r["name"]),
            "is_regulator": True,
        }
        for r in records
        if isinstance(r, dict) and "name" in r
    ]
    content = json.dumps({"results": results})
    return _chat_response(content)


class _InputDrivenChat:
    """Thread-safe chat stub: builds responses from the input messages, not a script."""

    def __init__(self, parent: "_InputDrivenStubClient"):
        self._parent = parent
        self.completions = self
        self._lock = threading.Lock()

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        with self._lock:
            self._parent.call_count += 1
            # Allow the test to inject a one-time error for a specific chunk.
            key = self._parent._error_trigger_name
            if key and any(key in m.get("content", "") for m in messages):
                self._parent._error_trigger_name = None  # fire only once
                raise RuntimeError(f"simulated error for chunk containing {key!r}")
        return _echo_response_for_messages(messages)


class _InputDrivenStubClient:
    """Thread-safe stub: responses derived from input, not a pop-queue.

    ``error_on_name`` (optional): if set, the FIRST chunk whose user message
    contains that exact name string will raise ``RuntimeError`` (simulating a
    transient API failure for exactly one chunk).
    """

    def __init__(self, error_on_name: str | None = None):
        self.call_count = 0
        self._error_trigger_name = error_on_name
        self._lock = threading.Lock()

        self.chat = _InputDrivenChat(self)
        # Files / batches not used by run_sync_full; provide empty stubs.
        self.files = None
        self.batches = None


class TestRunSyncFullConcurrent:
    def test_concurrent_classifies_all(self, mod, tmp_path):
        """workers=4 with multiple small chunks classifies every input name.

        Uses the input-driven stub (order-independent, thread-safe).
        Final set of cached names must equal the full input set; summary counts
        must be consistent.
        """
        names = [
            "FCA", "EBA", "PRA", "SEC", "CFTC", "FINRA", "OCC", "FDIC",
        ]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        client = _InputDrivenStubClient()

        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=2,   # 4 chunks of 2 names each
            max_retries=0,
            sleep_between_chunks=0,
            workers=4,
        )

        with open(canonical_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cached_names = {r["regulator_name"] for r in rows}

        # Every input name must land in the cache.
        assert cached_names == set(names)

        # Check canonical values for a couple of spot checks.
        by_name = {r["regulator_name"]: r for r in rows}
        assert by_name["FCA"]["canonical_regulator"] == "Financial Conduct Authority"
        assert by_name["SEC"]["canonical_regulator"] == "Securities and Exchange Commission"
        assert by_name["FDIC"]["is_regulator"] == "True"

        # Summary counts must be internally consistent.
        assert summary["total_names"] == len(names)
        assert summary["classified"] == len(names)
        assert summary["fallback_count"] == 0
        assert summary["already_cached"] == 0

    def test_concurrent_recovers_from_chunk_error(self, mod, tmp_path):
        """One chunk raises; those names still land via fallback; no name is lost.

        ``_InputDrivenStubClient(error_on_name="EBA")`` will raise exactly once
        for the first chunk whose user message mentions EBA.  With chunk_size=2
        and names [FCA, EBA, PRA, SEC] the affected chunk is [FCA, EBA] (or
        whichever chunk the worker picks up first that contains EBA) — its two
        names must end up resolved via the retry/fallback path.
        """
        names = ["FCA", "EBA", "PRA", "SEC"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        # Stub raises for the chunk containing "EBA"; all other chunks succeed.
        # After the chunk fails, EBA (and its chunk-mate) go to resolve_with_retry
        # which will also use the input-driven client — but the error trigger was
        # already consumed, so retry succeeds normally.
        client = _InputDrivenStubClient(error_on_name="EBA")

        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=2,
            max_retries=1,
            sleep_between_chunks=0,
            workers=2,
        )

        with open(canonical_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cached_names = {r["regulator_name"] for r in rows}

        # No name is lost — all 4 must appear.
        assert cached_names == set(names)

        # The two names from the errored chunk ended up somewhere — either
        # correctly resolved (retry succeeded) or fallen back conservatively.
        # Either way, is_regulator must be True (fallback or real).
        by_name = {r["regulator_name"]: r for r in rows}
        assert by_name["EBA"]["is_regulator"] == "True"

        # fallback_count accounts for names that exhausted retries.
        # Summary totals must be consistent: classified + already_cached == total_names.
        assert summary["total_names"] == len(names)
        assert summary["classified"] + summary["already_cached"] == len(names)

    def test_concurrent_resumes_skips_cached(self, mod, tmp_path):
        """Pre-cached names are skipped and already_cached=1 with workers=4."""
        names = ["FCA", "EBA", "PRA"]
        context_csv = tmp_path / "regulator_context.csv"
        canonical_csv = tmp_path / "regulator_canonical.csv"
        _write_context_csv(context_csv, names)

        # Pre-populate FCA.
        with open(canonical_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["regulator_name", "canonical_regulator", "is_regulator", "mentions"])
            w.writerow(["FCA", "Financial Conduct Authority", "True", "1"])

        client = _InputDrivenStubClient()

        summary = mod.run_sync_full(
            client,
            context_csv=context_csv,
            canonical_csv=canonical_csv,
            chunk_size=2,
            max_retries=0,
            sleep_between_chunks=0,
            workers=4,
        )

        with open(canonical_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        cached_names = {r["regulator_name"] for r in rows}
        assert cached_names == {"FCA", "EBA", "PRA"}

        assert summary["already_cached"] == 1
        assert summary["classified"] == 2
        assert summary["total_names"] == 3
        assert summary["fallback_count"] == 0
