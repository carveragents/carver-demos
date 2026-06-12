"""Tests for tools/classify_domains.py — institution domain classification.

EVERY test uses a STUBBED client. No network, no real OpenAI client, no API key.

Coverage:
  Stage 1  build_context_rows — correct columns, None/list coercion
           chunk_records — even split + remainder
  Stage 2  parse_and_validate — valid leaf kept, unknown/missing leaf coerced to fallback
           build_domain_rows — top_level derived from INSTITUTION_DOMAIN_PARENT
           build_system_prompt — every leaf present in the prompt text
           _extract_secondary — valid/invalid secondary handling
  Classify run_classify sequential + concurrent paths (stub client; no network)
  CLI      build_arg_parser flags; --help works without an API key
"""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import threading

import pytest

from carver_showcase.config import (
    DOMAIN_CHUNK_SIZE,
    DOMAIN_FALLBACK_LEAF,
    INSTITUTION_DOMAIN_LEAVES,
    INSTITUTION_DOMAIN_PARENT,
    INSTITUTION_DOMAIN_TAXONOMY,
    TOPIC_DOMAIN_CONTEXT_CSV,
    TOPIC_DOMAINS_CSV,
)


# ---------------------------------------------------------------------------
# Load tools/classify_domains.py as a module without running __main__.
# ---------------------------------------------------------------------------

def _load_module():
    here = pathlib.Path(__file__).parent
    root = here.parent
    mod_path = root / "tools" / "classify_domains.py"
    spec = importlib.util.spec_from_file_location("classify_domains", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# ---------------------------------------------------------------------------
# Stub OpenAI client — mirrors the surface the module uses.
# Constructing it needs no key and makes no network calls.
# ---------------------------------------------------------------------------

class _Obj:
    """Tiny attribute bag so responses look like SDK pydantic objects."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _chat_response(content: str) -> _Obj:
    """Build a stub chat.completions response with one choice carrying content."""
    return _Obj(choices=[_Obj(message=_Obj(content=content))])


def _domain_response(results: dict) -> _Obj:
    """Build a valid JSON-mode classify_domains response.

    results: {topic_id: {"sub_domain": <leaf>, "secondary": <leaf or "">}}
    """
    return _chat_response(json.dumps({"results": results}))


class _StubChat:
    def __init__(self, parent: "StubClient"):
        self._parent = parent
        self.completions = self

    def create(self, **kwargs):
        self._parent.chat_calls.append(kwargs)
        resp = self._parent.chat_script.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


class StubClient:
    """Injectable stand-in for an OpenAI client."""

    def __init__(self):
        self.chat_calls: list[dict] = []
        self.chat_script: list = []
        self.chat = _StubChat(self)


# ---------------------------------------------------------------------------
# Helper: build a minimal topic dict as the API would return it.
# ---------------------------------------------------------------------------

def _topic(tid: str, name: str, **extras) -> dict:
    base = {
        "id": tid,
        "name": name,
        "sectors": None,
        "industries": None,
        "sub_entity_type": None,
        "entity_type": None,
        "scope": None,
        "description": None,
    }
    base.update(extras)
    return base


# ===========================================================================
# Stage 1 — build_context_rows
# ===========================================================================

class TestBuildContextRows:
    def test_basic_columns_present(self, mod):
        topics = [_topic("1", "FCA")]
        rows = mod.build_context_rows(topics)
        assert len(rows) == 1
        row = rows[0]
        for col in mod.CONTEXT_HEADER:
            assert col in row, f"Missing column: {col}"

    def test_topic_id_and_name(self, mod):
        topics = [_topic("42", "Bank of England")]
        rows = mod.build_context_rows(topics)
        assert rows[0]["topic_id"] == "42"
        assert rows[0]["name"] == "Bank of England"

    def test_none_coerced_to_empty_string(self, mod):
        topics = [_topic("1", "FCA", sectors=None, description=None)]
        rows = mod.build_context_rows(topics)
        row = rows[0]
        assert row["sectors"] == ""
        assert row["description"] == ""

    def test_list_coerced_to_semicolon_join(self, mod):
        topics = [_topic("1", "FCA", sectors=["Finance", "Banking"],
                          industries=["Retail Banking", "Investment"])]
        rows = mod.build_context_rows(topics)
        assert rows[0]["sectors"] == "Finance; Banking"
        assert rows[0]["industries"] == "Retail Banking; Investment"

    def test_single_value_list_no_trailing_semicolon(self, mod):
        topics = [_topic("1", "FCA", sectors=["Finance"])]
        rows = mod.build_context_rows(topics)
        assert rows[0]["sectors"] == "Finance"

    def test_empty_list_produces_empty_string(self, mod):
        topics = [_topic("1", "FCA", sectors=[])]
        rows = mod.build_context_rows(topics)
        assert rows[0]["sectors"] == ""

    def test_topic_without_id_skipped(self, mod):
        topics = [{"name": "No ID"}]
        rows = mod.build_context_rows(topics)
        assert rows == []

    def test_multiple_topics_ordered(self, mod):
        topics = [_topic("10", "Alpha"), _topic("20", "Beta"), _topic("30", "Gamma")]
        rows = mod.build_context_rows(topics)
        assert [r["topic_id"] for r in rows] == ["10", "20", "30"]

    def test_mixed_none_and_list(self, mod):
        topics = [_topic("1", "MAS", sectors=["Finance"], description=None,
                          sub_entity_type="Regulator")]
        rows = mod.build_context_rows(topics)
        assert rows[0]["sectors"] == "Finance"
        assert rows[0]["description"] == ""
        assert rows[0]["sub_entity_type"] == "Regulator"

    def test_empty_input(self, mod):
        assert mod.build_context_rows([]) == []


# ===========================================================================
# chunk_records
# ===========================================================================

class TestChunkRecords:
    def test_even_split(self, mod):
        rows = [{"topic_id": str(i)} for i in range(6)]
        chunks = mod.chunk_records(rows, 3)
        assert len(chunks) == 2
        assert len(chunks[0]) == 3
        assert len(chunks[1]) == 3

    def test_remainder(self, mod):
        rows = [{"topic_id": str(i)} for i in range(7)]
        chunks = mod.chunk_records(rows, 3)
        assert len(chunks) == 3
        assert len(chunks[0]) == 3
        assert len(chunks[1]) == 3
        assert len(chunks[2]) == 1

    def test_empty_input(self, mod):
        assert mod.chunk_records([], 5) == []

    def test_chunk_size_larger_than_input(self, mod):
        rows = [{"topic_id": str(i)} for i in range(3)]
        chunks = mod.chunk_records(rows, 10)
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_single_element(self, mod):
        rows = [{"topic_id": "1"}]
        chunks = mod.chunk_records(rows, 5)
        assert len(chunks) == 1
        assert chunks[0] == [{"topic_id": "1"}]


# ===========================================================================
# parse_and_validate
# ===========================================================================

class TestParseAndValidate:
    def _chunk(self, ids: list[str]) -> list[dict]:
        return [{"topic_id": tid} for tid in ids]

    def test_valid_leaf_kept(self, mod):
        valid_leaf = INSTITUTION_DOMAIN_LEAVES[0]
        response = _domain_response({"1": {"sub_domain": valid_leaf, "secondary": ""}})
        result = mod.parse_and_validate(response, self._chunk(["1"]))
        assert result["1"] == valid_leaf

    def test_unknown_leaf_coerced_to_fallback(self, mod):
        response = _domain_response({"1": {"sub_domain": "Made Up Domain", "secondary": ""}})
        result = mod.parse_and_validate(response, self._chunk(["1"]))
        assert result["1"] == DOMAIN_FALLBACK_LEAF

    def test_missing_sub_domain_key_coerced_to_fallback(self, mod):
        # Entry exists but has no sub_domain key
        response = _chat_response(json.dumps({"results": {"1": {"secondary": ""}}}))
        result = mod.parse_and_validate(response, self._chunk(["1"]))
        assert result["1"] == DOMAIN_FALLBACK_LEAF

    def test_missing_topic_id_in_results_coerced_to_fallback(self, mod):
        # Model returns results for "2" but chunk contains "1"
        response = _domain_response({"2": {"sub_domain": INSTITUTION_DOMAIN_LEAVES[0], "secondary": ""}})
        result = mod.parse_and_validate(response, self._chunk(["1"]))
        assert result["1"] == DOMAIN_FALLBACK_LEAF

    def test_malformed_json_all_fallback(self, mod):
        response = _chat_response("not valid json {")
        result = mod.parse_and_validate(response, self._chunk(["1", "2"]))
        assert result["1"] == DOMAIN_FALLBACK_LEAF
        assert result["2"] == DOMAIN_FALLBACK_LEAF

    def test_results_not_dict_all_fallback(self, mod):
        response = _chat_response(json.dumps({"results": [{"id": "1"}]}))
        result = mod.parse_and_validate(response, self._chunk(["1"]))
        assert result["1"] == DOMAIN_FALLBACK_LEAF

    def test_all_valid_leaves_accepted(self, mod):
        """Every leaf in the closed set is accepted as-is."""
        for leaf in INSTITUTION_DOMAIN_LEAVES:
            response = _domain_response({"1": {"sub_domain": leaf, "secondary": ""}})
            result = mod.parse_and_validate(response, self._chunk(["1"]))
            assert result["1"] == leaf, f"Leaf should be accepted: {leaf!r}"

    def test_multiple_ids_mixed_validity(self, mod):
        valid_leaf = INSTITUTION_DOMAIN_LEAVES[0]
        response = _domain_response({
            "1": {"sub_domain": valid_leaf, "secondary": ""},
            "2": {"sub_domain": "INVALID", "secondary": ""},
        })
        result = mod.parse_and_validate(response, self._chunk(["1", "2"]))
        assert result["1"] == valid_leaf
        assert result["2"] == DOMAIN_FALLBACK_LEAF


# ===========================================================================
# build_domain_rows — top_level derivation
# ===========================================================================

class TestBuildDomainRows:
    def test_top_level_derived_from_parent_map(self, mod):
        """top_level must always match INSTITUTION_DOMAIN_PARENT[sub_domain]."""
        # Pick a known leaf and check its parent is derived correctly.
        leaf = "Tax & Revenue"
        expected_top = INSTITUTION_DOMAIN_PARENT[leaf]
        assert expected_top == "Finance"

        validated = {"1": leaf}
        secondary = {"1": ""}
        context = [{"topic_id": "1"}]
        rows = mod.build_domain_rows(validated, secondary, context)
        assert len(rows) == 1
        assert rows[0]["sub_domain"] == leaf
        assert rows[0]["top_level"] == "Finance"

    def test_all_known_leaves_derive_correct_parent(self, mod):
        for leaf, expected_top in INSTITUTION_DOMAIN_PARENT.items():
            validated = {"x": leaf}
            secondary = {"x": ""}
            context = [{"topic_id": "x"}]
            rows = mod.build_domain_rows(validated, secondary, context)
            assert rows[0]["top_level"] == expected_top, (
                f"Leaf {leaf!r}: expected top {expected_top!r}, got {rows[0]['top_level']!r}"
            )

    def test_secondary_carried_through(self, mod):
        leaf = INSTITUTION_DOMAIN_LEAVES[0]
        sec_leaf = INSTITUTION_DOMAIN_LEAVES[1]
        validated = {"1": leaf}
        secondary = {"1": sec_leaf}
        context = [{"topic_id": "1"}]
        rows = mod.build_domain_rows(validated, secondary, context)
        assert rows[0]["secondary"] == sec_leaf

    def test_empty_secondary_carried_through(self, mod):
        leaf = INSTITUTION_DOMAIN_LEAVES[0]
        validated = {"1": leaf}
        secondary = {"1": ""}
        context = [{"topic_id": "1"}]
        rows = mod.build_domain_rows(validated, secondary, context)
        assert rows[0]["secondary"] == ""

    def test_output_columns(self, mod):
        leaf = DOMAIN_FALLBACK_LEAF
        validated = {"1": leaf}
        secondary = {"1": ""}
        context = [{"topic_id": "1"}]
        rows = mod.build_domain_rows(validated, secondary, context)
        assert set(rows[0].keys()) == {"topic_id", "sub_domain", "top_level", "secondary"}

    def test_order_follows_context_rows(self, mod):
        """Output row order mirrors context_rows order."""
        leaves = list(INSTITUTION_DOMAIN_LEAVES[:3])
        validated = {str(i): leaves[i] for i in range(3)}
        secondary = {str(i): "" for i in range(3)}
        context = [{"topic_id": "2"}, {"topic_id": "0"}, {"topic_id": "1"}]
        rows = mod.build_domain_rows(validated, secondary, context)
        assert [r["topic_id"] for r in rows] == ["2", "0", "1"]

    def test_secondary_cleared_when_equals_sub_domain(self, mod):
        """secondary must be "" when it duplicates the row's sub_domain (Fix 3)."""
        leaf = INSTITUTION_DOMAIN_LEAVES[0]
        validated = {"1": leaf}
        # LLM returned the same leaf for both primary and secondary.
        secondary = {"1": leaf}
        context = [{"topic_id": "1"}]
        rows = mod.build_domain_rows(validated, secondary, context)
        assert rows[0]["sub_domain"] == leaf
        assert rows[0]["secondary"] == ""


# ===========================================================================
# build_system_prompt — every leaf must appear in the prompt text
# ===========================================================================

class TestBuildSystemPrompt:
    def test_all_leaves_in_prompt(self, mod):
        prompt = mod.build_system_prompt()
        for leaf in INSTITUTION_DOMAIN_LEAVES:
            assert leaf in prompt, f"Leaf missing from system prompt: {leaf!r}"

    def test_all_top_levels_in_prompt(self, mod):
        prompt = mod.build_system_prompt()
        for top_level in INSTITUTION_DOMAIN_TAXONOMY:
            assert top_level in prompt, f"Top level missing from prompt: {top_level!r}"

    def test_fallback_leaf_in_prompt(self, mod):
        prompt = mod.build_system_prompt()
        assert DOMAIN_FALLBACK_LEAF in prompt

    def test_prompt_is_non_empty_string(self, mod):
        prompt = mod.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_system_prompt_constant_matches_function(self, mod):
        """SYSTEM_PROMPT module constant matches build_system_prompt() output."""
        assert mod.SYSTEM_PROMPT == mod.build_system_prompt()


# ===========================================================================
# run_classify — sequential path
# ===========================================================================

class TestRunClassifySequential:
    def _make_rows(self, n: int) -> list[dict]:
        return [
            {
                "topic_id": str(i),
                "name": f"Body {i}",
                "sectors": "Finance",
                "industries": "",
                "sub_entity_type": "Regulator",
                "entity_type": "Regulator / Supervisor",
                "scope": "national",
                "description": "",
            }
            for i in range(n)
        ]

    def test_writes_csv_with_correct_columns(self, mod, tmp_path):
        leaf = INSTITUTION_DOMAIN_LEAVES[0]
        client = StubClient()
        client.chat_script = [
            _domain_response({"0": {"sub_domain": leaf, "secondary": ""},
                              "1": {"sub_domain": leaf, "secondary": ""}}),
        ]
        rows = self._make_rows(2)
        summary = mod.run_classify(
            client, rows, chunk_size=10,
            sleep_between_chunks=0, workers=1,
            out_path=tmp_path / "domains.csv",
        )
        with open(tmp_path / "domains.csv", newline="", encoding="utf-8") as fh:
            read_rows = list(csv.DictReader(fh))
        assert len(read_rows) == 2
        assert list(read_rows[0].keys()) == mod.DOMAINS_HEADER
        assert all(r["sub_domain"] == leaf for r in read_rows)

    def test_top_level_written_correctly(self, mod, tmp_path):
        leaf = "Tax & Revenue"
        client = StubClient()
        client.chat_script = [
            _domain_response({"0": {"sub_domain": leaf, "secondary": ""}}),
        ]
        rows = self._make_rows(1)
        mod.run_classify(
            client, rows, chunk_size=10,
            sleep_between_chunks=0, workers=1,
            out_path=tmp_path / "domains.csv",
        )
        with open(tmp_path / "domains.csv", newline="", encoding="utf-8") as fh:
            read_rows = list(csv.DictReader(fh))
        assert read_rows[0]["top_level"] == "Finance"

    def test_summary_counts(self, mod, tmp_path):
        leaf = INSTITUTION_DOMAIN_LEAVES[0]
        client = StubClient()
        client.chat_script = [
            _domain_response({"0": {"sub_domain": leaf, "secondary": ""},
                              "1": {"sub_domain": leaf, "secondary": ""}}),
        ]
        rows = self._make_rows(2)
        summary = mod.run_classify(
            client, rows, chunk_size=10,
            sleep_between_chunks=0, workers=1,
            out_path=tmp_path / "domains.csv",
        )
        assert summary["total"] == 2
        assert summary["classified"] == 2
        assert summary["fallback_count"] == 0

    def test_chunk_exception_falls_back(self, mod, tmp_path):
        """A chunk that raises routes all its institutions to DOMAIN_FALLBACK_LEAF."""
        client = StubClient()
        client.chat_script = [RuntimeError("simulated API error")]
        rows = self._make_rows(2)
        summary = mod.run_classify(
            client, rows, chunk_size=10,
            sleep_between_chunks=0, workers=1,
            out_path=tmp_path / "domains.csv",
        )
        with open(tmp_path / "domains.csv", newline="", encoding="utf-8") as fh:
            read_rows = list(csv.DictReader(fh))
        assert all(r["sub_domain"] == DOMAIN_FALLBACK_LEAF for r in read_rows)
        assert summary["fallback_count"] == len(rows)


# ===========================================================================
# run_classify — concurrent path
# ===========================================================================

class _InputDrivenChat:
    """Thread-safe chat stub: synthesises responses from input, not a script."""

    def __init__(self, parent: "_InputDrivenClient"):
        self._parent = parent
        self.completions = self
        self._lock = threading.Lock()

    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        with self._lock:
            self._parent.call_count += 1
            key = self._parent._error_trigger_id
            if key:
                user_text = " ".join(m.get("content", "") for m in messages)
                if key in user_text:
                    self._parent._error_trigger_id = None
                    raise RuntimeError(f"simulated error for chunk containing {key!r}")

        # Build a deterministic response from the input records
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        try:
            json_start = user_text.index("[")
            records = json.loads(user_text[json_start:])
        except (ValueError, json.JSONDecodeError):
            records = []

        leaf = INSTITUTION_DOMAIN_LEAVES[0]
        results = {
            str(r["id"]): {"sub_domain": leaf, "secondary": ""}
            for r in records
            if isinstance(r, dict) and "id" in r
        }
        return _domain_response(results)


class _InputDrivenClient:
    def __init__(self, error_on_id: str | None = None):
        self.call_count = 0
        self._error_trigger_id = error_on_id
        self.chat = _InputDrivenChat(self)


class TestRunClassifyConcurrent:
    def _make_rows(self, n: int) -> list[dict]:
        return [
            {
                "topic_id": str(i),
                "name": f"Body {i}",
                "sectors": "",
                "industries": "",
                "sub_entity_type": "",
                "entity_type": "",
                "scope": "",
                "description": "",
            }
            for i in range(n)
        ]

    def test_concurrent_classifies_all(self, mod, tmp_path):
        n = 8
        rows = self._make_rows(n)
        client = _InputDrivenClient()
        summary = mod.run_classify(
            client, rows, chunk_size=2,
            sleep_between_chunks=0, workers=4,
            out_path=tmp_path / "domains.csv",
        )
        with open(tmp_path / "domains.csv", newline="", encoding="utf-8") as fh:
            read_rows = list(csv.DictReader(fh))
        assert len(read_rows) == n
        assert summary["classified"] == n
        # Row order must match the original context_rows order regardless of worker count.
        assert [r["topic_id"] for r in read_rows] == [str(i) for i in range(n)]

    def test_concurrent_no_name_lost_on_error(self, mod, tmp_path):
        """One chunk raises; all institutions still appear in the output."""
        n = 6
        rows = self._make_rows(n)
        # Error triggered on chunk containing id "2"
        client = _InputDrivenClient(error_on_id="\"id\": \"2\"")
        mod.run_classify(
            client, rows, chunk_size=2,
            sleep_between_chunks=0, workers=3,
            out_path=tmp_path / "domains.csv",
        )
        with open(tmp_path / "domains.csv", newline="", encoding="utf-8") as fh:
            read_rows = list(csv.DictReader(fh))
        assert len(read_rows) == n


# ===========================================================================
# Client seam + CLI
# ===========================================================================

class TestClientSeam:
    def test_make_client_is_callable_seam(self, mod):
        assert hasattr(mod, "make_client")
        assert callable(mod.make_client)

    def test_build_arg_parser_context_only(self, mod):
        parser = mod.build_arg_parser()
        args = parser.parse_args(["--context-only"])
        assert args.context_only is True

    def test_build_arg_parser_sample(self, mod):
        parser = mod.build_arg_parser()
        args = parser.parse_args(["--sample", "20"])
        assert args.sample == 20

    def test_build_arg_parser_workers(self, mod):
        parser = mod.build_arg_parser()
        args = parser.parse_args(["--workers", "4"])
        assert args.workers == 4

    def test_build_arg_parser_defaults(self, mod):
        parser = mod.build_arg_parser()
        args = parser.parse_args([])
        assert args.context_only is False
        assert args.sample is None
        assert args.workers == 1
        assert args.sync_full is False

    def test_help_exits_cleanly_without_key(self, mod):
        """build_arg_parser().parse_args(['--help']) raises SystemExit(0).

        The key point: the module was loaded (exec'd) without OPENAI_API_KEY
        being set, yet no ImportError or KeyError was raised.  The lazy import
        inside make_client() guards key access so --help works without a key.
        """
        parser = mod.build_arg_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0
