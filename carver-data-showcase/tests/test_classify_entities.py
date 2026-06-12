"""Tests for tools/classify_entities.py — LLM entity typing via the Batch API.

EVERY test uses a STUBBED client. No network, no real OpenAI client, no API key.

Coverage maps to the spec sub-steps:
  2.1  request-builder + deterministic chunking
  2.2  response parser + schema validation
  2.3  detect -> retry -> bounded fallback (sync path)
  2.4  resume-or-submit sidecar + incremental cache
  2.5  --sample N sync path + CLI wiring (seam, no real client)

The module under test keeps pure logic (chunking / request build / parse /
validate / hash / set-difference / retry decisions) in plain functions, and
all network calls behind an injectable `client` argument, so the stub seam is
tiny and no test ever constructs a real client.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib

import pytest


# ---------------------------------------------------------------------------
# Load tools/classify_entities.py as a module without running __main__.
# ---------------------------------------------------------------------------

def _load_module():
    here = pathlib.Path(__file__).parent
    root = here.parent
    mod_path = root / "tools" / "classify_entities.py"
    spec = importlib.util.spec_from_file_location("classify_entities", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


from carver_showcase.config import (
    ENTITY_CHUNK_SIZE,
    ENTITY_TYPES,
    ENTITY_TYPE_DEFINITIONS,
    MAX_RETRIES,
    OPENAI_MODEL,
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

def _classifications_json(rows):
    """rows: list of (entity, type, canonical_name) -> JSON-mode object string."""
    return json.dumps(
        {"classifications": [
            {"entity": e, "type": t, "canonical_name": c} for (e, t, c) in rows
        ]}
    )


def _write_mentions_csv(path, entities):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["entity", "count"])
        for i, e in enumerate(entities):
            w.writerow([e, len(entities) - i])  # descending counts, file order preserved


# ===========================================================================
# 2.1  Deterministic chunking + request builder
# ===========================================================================

class TestChunking:
    def test_chunks_of_chunk_size(self, mod):
        entities = [f"e{i}" for i in range(ENTITY_CHUNK_SIZE * 2)]
        chunks = mod.chunk_entities(entities, ENTITY_CHUNK_SIZE)
        assert len(chunks) == 2
        assert all(len(c) == ENTITY_CHUNK_SIZE for c in chunks)

    def test_last_chunk_remainder(self, mod):
        entities = [f"e{i}" for i in range(ENTITY_CHUNK_SIZE + 3)]
        chunks = mod.chunk_entities(entities, ENTITY_CHUNK_SIZE)
        assert len(chunks) == 2
        assert len(chunks[0]) == ENTITY_CHUNK_SIZE
        assert chunks[1] == entities[ENTITY_CHUNK_SIZE:]

    def test_empty_input(self, mod):
        assert mod.chunk_entities([], ENTITY_CHUNK_SIZE) == []

    def test_single_short_chunk(self, mod):
        chunks = mod.chunk_entities(["a", "b", "c"], ENTITY_CHUNK_SIZE)
        assert chunks == [["a", "b", "c"]]

    def test_chunking_is_reproducible_from_file(self, mod, tmp_path):
        """Chunking from the CSV is deterministic in file order."""
        entities = [f"ent{i:03d}" for i in range(120)]
        csv_path = tmp_path / "entity_mentions.csv"
        _write_mentions_csv(csv_path, entities)

        read_a = mod.read_distinct_entities(csv_path)
        read_b = mod.read_distinct_entities(csv_path)
        assert read_a == read_b == entities  # file order preserved

        chunks = mod.chunk_entities(read_a, ENTITY_CHUNK_SIZE)
        assert len(chunks) == 3
        assert chunks[0][0] == "ent000"
        assert chunks[-1][-1] == "ent119"


class TestRequestBuilder:
    def test_custom_id_format(self, mod):
        line = mod.build_request_line(0, ["FCA", "EBA"])
        assert line["custom_id"] == "chunk-00000"
        line9 = mod.build_request_line(9, ["X"])
        assert line9["custom_id"] == "chunk-00009"
        line_big = mod.build_request_line(12345, ["X"])
        assert line_big["custom_id"] == "chunk-12345"

    def test_request_body_shape(self, mod):
        line = mod.build_request_line(0, ["FCA", "EBA"])
        assert line["method"] == "POST"
        assert line["url"] == "/v1/chat/completions"
        body = line["body"]
        assert body["model"] == OPENAI_MODEL
        assert body["temperature"] == 0
        # JSON mode declared
        assert body["response_format"]["type"] == "json_object"

    def test_taxonomy_in_system_message(self, mod):
        line = mod.build_request_line(0, ["FCA"])
        messages = line["body"]["messages"]
        system_text = " ".join(
            m["content"] for m in messages if m["role"] in ("system", "developer")
        )
        # All six exact type strings present
        for t in ENTITY_TYPES:
            assert t in system_text
        # Definitions carried once
        for definition in ENTITY_TYPE_DEFINITIONS.values():
            assert definition in system_text

    def test_chunk_entities_in_user_payload(self, mod):
        line = mod.build_request_line(0, ["FCA", "EBA", "PRA"])
        messages = line["body"]["messages"]
        user_text = " ".join(m["content"] for m in messages if m["role"] == "user")
        for e in ["FCA", "EBA", "PRA"]:
            assert e in user_text

    def test_write_requests_jsonl(self, mod, tmp_path):
        entities = [f"ent{i:03d}" for i in range(120)]
        out = tmp_path / "requests.jsonl"
        n = mod.write_request_file(entities, out, ENTITY_CHUNK_SIZE)
        assert n == 3
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        first = json.loads(lines[0])
        assert first["custom_id"] == "chunk-00000"
        # Entities map back to file order
        body = first["body"]
        user_text = " ".join(m["content"] for m in body["messages"] if m["role"] == "user")
        assert "ent000" in user_text
        last = json.loads(lines[-1])
        assert last["custom_id"] == "chunk-00002"


# ===========================================================================
# 2.2  Response parser + schema validation
# ===========================================================================

class TestParseResponse:
    def test_valid_parse(self, mod):
        sent = ["FCA", "EBA"]
        content = _classifications_json([
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ("EBA", "Regulator / Supervisor", "European Banking Authority"),
        ])
        rows, missing = mod.parse_and_validate(content, sent)
        assert missing == []
        assert {r["entity"] for r in rows} == {"FCA", "EBA"}
        assert all(r["type"] in ENTITY_TYPES for r in rows)
        fca = next(r for r in rows if r["entity"] == "FCA")
        assert fca["canonical_name"] == "Financial Conduct Authority"

    def test_other_type_accepted(self, mod):
        sent = ["Atlantis"]
        content = _classifications_json([("Atlantis", "Other", "Atlantis")])
        rows, missing = mod.parse_and_validate(content, sent)
        assert missing == []
        assert rows[0]["type"] == "Other"

    def test_unknown_type_flagged(self, mod):
        sent = ["FCA"]
        content = _classifications_json([("FCA", "Banana", "Financial Conduct Authority")])
        rows, missing = mod.parse_and_validate(content, sent)
        # The invalid entity is unresolved; no valid row returned for it
        assert "FCA" in missing
        assert all(r["entity"] != "FCA" for r in rows)

    def test_missing_field_flagged(self, mod):
        sent = ["FCA"]
        content = json.dumps({"classifications": [{"entity": "FCA", "type": "Company"}]})
        rows, missing = mod.parse_and_validate(content, sent)
        assert "FCA" in missing

    def test_non_json_all_missing(self, mod):
        sent = ["FCA", "EBA"]
        rows, missing = mod.parse_and_validate("not json at all {", sent)
        assert rows == []
        assert sorted(missing) == ["EBA", "FCA"]

    def test_short_response_flags_only_missing(self, mod):
        """Fewer objects than sent: the unreturned entity is flagged, the rest pass."""
        sent = ["FCA", "EBA", "PRA"]
        content = _classifications_json([
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ("EBA", "Regulator / Supervisor", "European Banking Authority"),
        ])
        rows, missing = mod.parse_and_validate(content, sent)
        assert missing == ["PRA"]
        assert {r["entity"] for r in rows} == {"FCA", "EBA"}

    def test_extra_entity_not_in_sent_ignored(self, mod):
        """Hallucinated entity not in the sent set is dropped, not surfaced as a row."""
        sent = ["FCA"]
        content = _classifications_json([
            ("FCA", "Company", "Financial Conduct Authority"),
            ("GHOST", "Company", "Ghost Co"),
        ])
        rows, missing = mod.parse_and_validate(content, sent)
        assert {r["entity"] for r in rows} == {"FCA"}
        assert missing == []

    def test_parse_batch_output_line(self, mod):
        """A batch output JSONL line maps to its chunk via custom_id."""
        content = _classifications_json([("FCA", "Company", "Financial Conduct Authority")])
        line = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": content}}]
            }},
        })
        custom_id, body_content, errored = mod.extract_output_line(line)
        assert custom_id == "chunk-00000"
        assert errored is False
        rows, missing = mod.parse_and_validate(body_content, ["FCA"])
        assert rows[0]["entity"] == "FCA"


# ===========================================================================
# 2.3  detect -> retry -> bounded fallback (sync path)
# ===========================================================================

class TestRetryAndFallback:
    def test_malformed_then_valid_resolves(self, mod):
        """Malformed once, valid on retry: retry attempted, entity resolved."""
        client = StubClient()
        # First sync call returns garbage, second returns valid.
        client.chat_script = [
            _chat_response("garbage not json"),
            _chat_response(_classifications_json([
                ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ])),
        ]
        rows, fallback = mod.resolve_with_retry(
            client, ["FCA"], max_retries=MAX_RETRIES
        )
        assert len(client.chat_calls) == 2  # one fail + one retry
        assert fallback == 0
        assert rows[0]["type"] == "Regulator / Supervisor"

    def test_persistent_malformed_falls_back(self, mod):
        """Stays malformed through MAX_RETRIES -> explicit Other fallback + count."""
        client = StubClient()
        client.chat_script = [_chat_response("garbage") for _ in range(MAX_RETRIES + 1)]
        rows, fallback = mod.resolve_with_retry(
            client, ["Mystery"], max_retries=MAX_RETRIES
        )
        # 1 initial sync attempt + MAX_RETRIES retries
        assert len(client.chat_calls) == MAX_RETRIES + 1
        assert fallback == 1
        assert rows[0]["entity"] == "Mystery"
        assert rows[0]["type"] == "Other"
        assert rows[0]["canonical_name"] == "Mystery"

    def test_partial_retry_only_resends_unresolved(self, mod):
        """First call resolves one, leaves one; retry re-sends only the unresolved."""
        client = StubClient()
        client.chat_script = [
            # first attempt: FCA good, EBA missing (short)
            _chat_response(_classifications_json([
                ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ])),
            # retry: EBA resolved
            _chat_response(_classifications_json([
                ("EBA", "Regulator / Supervisor", "European Banking Authority"),
            ])),
        ]
        rows, fallback = mod.resolve_with_retry(
            client, ["FCA", "EBA"], max_retries=MAX_RETRIES
        )
        assert fallback == 0
        # The retry call must have carried only EBA in its user payload.
        retry_kwargs = client.chat_calls[1]
        user_text = " ".join(
            m["content"] for m in retry_kwargs["messages"] if m["role"] == "user"
        )
        assert "EBA" in user_text
        assert "FCA" not in user_text
        assert {r["entity"] for r in rows} == {"FCA", "EBA"}


# ===========================================================================
# 2.4  Resume-or-submit sidecar + incremental cache
# ===========================================================================

class TestIncrementalCache:
    def test_excludes_already_classified(self, mod, tmp_path):
        types_csv = tmp_path / "entity_types.csv"
        with open(types_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "type", "canonical_name"])
            w.writerow(["FCA", "Regulator / Supervisor", "Financial Conduct Authority"])
        todo = mod.entities_to_classify(["FCA", "EBA", "PRA"], types_csv)
        assert todo == ["EBA", "PRA"]  # file order preserved, FCA excluded

    def test_no_cache_file_all_todo(self, mod, tmp_path):
        missing = tmp_path / "nope.csv"
        todo = mod.entities_to_classify(["FCA", "EBA"], missing)
        assert todo == ["FCA", "EBA"]

    def test_complete_cache_empty_todo(self, mod, tmp_path):
        types_csv = tmp_path / "entity_types.csv"
        with open(types_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "type", "canonical_name"])
            w.writerow(["FCA", "Company", "Financial Conduct Authority"])
            w.writerow(["EBA", "Company", "European Banking Authority"])
        todo = mod.entities_to_classify(["FCA", "EBA"], types_csv)
        assert todo == []


class TestInputHash:
    def test_hash_is_set_order_invariant_but_content_sensitive(self, mod):
        """The hash identifies the exact distinct-entity set (order-stable input)."""
        h1 = mod.input_hash(["FCA", "EBA"])
        h2 = mod.input_hash(["FCA", "EBA"])
        h3 = mod.input_hash(["FCA", "PRA"])
        assert h1 == h2
        assert h1 != h3
        assert isinstance(h1, str) and len(h1) == 64  # sha256 hexdigest


class TestSidecar:
    def test_submit_fresh_writes_sidecar_before_polling(self, mod, tmp_path):
        """No sidecar -> upload + create ONE batch + write sidecar BEFORE first poll."""
        client = StubClient()
        client.batch_script = [_batch(id="batch-XYZ", status="validating")]
        # After write, the resume path polls -> completed with an output file.
        client.retrieve_script = [
            _batch(id="batch-XYZ", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
                    ("EBA", "Regulator / Supervisor", "European Banking Authority"),
                ])}}]
            }},
        }) + "\n"

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

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
                entities=["FCA", "EBA"],
                requests_path=requests_path,
                sidecar_path=sidecar,
                types_csv=types_csv,
                chunk_size=ENTITY_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        finally:
            mod.write_sidecar = orig_write

        # Exactly one batch created; sidecar written with returned id BEFORE poll.
        assert len(client.batches_create_calls) == 1
        assert recorded["batch_id"] == "batch-XYZ"
        assert recorded["polled_before"] == 0  # no retrieve calls yet when written
        assert recorded["hash"] == mod.input_hash(["FCA", "EBA"])

    def test_resume_matching_hash_does_not_create_batch(self, mod, tmp_path):
        """Live sidecar matching current input -> resume; NO new batch created."""
        client = StubClient()
        client.retrieve_script = [
            _batch(id="batch-EXIST", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
                ])}}]
            }},
        }) + "\n"

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        entities = ["FCA"]
        mod.write_sidecar(sidecar, {
            "batch_id": "batch-EXIST",
            "input_file_path": str(requests_path),
            "model": OPENAI_MODEL,
            "input_row_count": 1,
            "input_sha256": mod.input_hash(entities),
        })

        mod.run_full(
            client,
            entities=entities,
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )

        assert client.batches_create_calls == []  # resumed, did not create
        assert client.files_create_calls == []     # did not re-upload
        assert client.batches_retrieve_calls == ["batch-EXIST"]

    def test_hash_mismatch_submits_fresh(self, mod, tmp_path):
        """Sidecar hash != current input set -> submit fresh (new batch created)."""
        client = StubClient()
        client.batch_script = [_batch(id="batch-NEW", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-NEW", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("PRA", "Regulator / Supervisor", "Prudential Regulation Authority"),
                ])}}]
            }},
        }) + "\n"

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        # Sidecar points at a DIFFERENT input set.
        mod.write_sidecar(sidecar, {
            "batch_id": "batch-OLD",
            "input_file_path": str(requests_path),
            "model": OPENAI_MODEL,
            "input_row_count": 1,
            "input_sha256": mod.input_hash(["DIFFERENT"]),
        })

        mod.run_full(
            client,
            entities=["PRA"],
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert len(client.batches_create_calls) == 1  # fresh submit

    def test_sidecar_cleared_only_after_merge(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-1", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-1", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("FCA", "Company", "Financial Conduct Authority"),
                ])}}]
            }},
        }) + "\n"

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        mod.run_full(
            client,
            entities=["FCA"],
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        # Merge happened -> entity_types.csv has the row; sidecar cleared.
        assert not sidecar.exists()
        with open(types_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert any(r["entity"] == "FCA" for r in rows)

    def test_terminal_failed_clears_sidecar(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-F", status="validating")]
        client.retrieve_script = [_batch(id="batch-F", status="failed")]

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        with pytest.raises(mod.BatchTerminalError):
            mod.run_full(
                client,
                entities=["FCA"],
                requests_path=requests_path,
                sidecar_path=sidecar,
                types_csv=types_csv,
                chunk_size=ENTITY_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        # Sidecar cleared so a resubmit is possible next run.
        assert not sidecar.exists()

    def test_terminal_expired_clears_sidecar(self, mod, tmp_path):
        client = StubClient()
        client.batch_script = [_batch(id="batch-E", status="validating")]
        client.retrieve_script = [_batch(id="batch-E", status="expired")]

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        with pytest.raises(mod.BatchTerminalError):
            mod.run_full(
                client,
                entities=["FCA"],
                requests_path=requests_path,
                sidecar_path=sidecar,
                types_csv=types_csv,
                chunk_size=ENTITY_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        assert not sidecar.exists()

    def test_complete_cache_no_batch(self, mod, tmp_path):
        """An already-complete cache submits no batch and makes no client calls."""
        client = StubClient()
        types_csv = tmp_path / "entity_types.csv"
        with open(types_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "type", "canonical_name"])
            w.writerow(["FCA", "Company", "Financial Conduct Authority"])

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"

        result = mod.run_full(
            client,
            entities=["FCA"],
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert client.batches_create_calls == []
        assert client.files_create_calls == []
        assert client.batches_retrieve_calls == []
        assert result.get("submitted") is False

    def test_merge_appends_to_existing_cache(self, mod, tmp_path):
        """New rows merge into an existing partial cache (append/create)."""
        client = StubClient()
        client.batch_script = [_batch(id="batch-1", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-1", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("EBA", "Regulator / Supervisor", "European Banking Authority"),
                ])}}]
            }},
        }) + "\n"

        types_csv = tmp_path / "entity_types.csv"
        with open(types_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["entity", "type", "canonical_name"])
            w.writerow(["FCA", "Company", "Financial Conduct Authority"])

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"

        mod.run_full(
            client,
            entities=["FCA", "EBA"],  # FCA cached, only EBA classified
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        with open(types_csv, newline="", encoding="utf-8") as fh:
            rows = {r["entity"]: r for r in csv.DictReader(fh)}
        assert set(rows) == {"FCA", "EBA"}
        assert rows["EBA"]["type"] == "Regulator / Supervisor"


# ===========================================================================
# 2.5  --sample N sync path + CLI wiring (seam; no real client)
# ===========================================================================

class TestSamplePath:
    def test_sample_uses_sync_path_only(self, mod, tmp_path, capsys):
        """--sample classifies via sync chat; no Files/batch/poll calls; no cache write."""
        client = StubClient()
        client.chat_script = [
            _chat_response(_classifications_json([
                ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
                ("EBA", "Regulator / Supervisor", "European Banking Authority"),
            ])),
        ]
        types_csv = tmp_path / "entity_types.csv"

        rows = mod.run_sample(
            client, ["FCA", "EBA"], max_retries=MAX_RETRIES, types_csv=types_csv
        )
        # sync path only
        assert client.files_create_calls == []
        assert client.batches_create_calls == []
        assert client.batches_retrieve_calls == []
        assert len(client.chat_calls) == 1
        # did not write the full cache
        assert not types_csv.exists()
        # returned classifications
        assert {r["entity"] for r in rows} == {"FCA", "EBA"}

    def test_sample_prints_results(self, mod, tmp_path, capsys):
        client = StubClient()
        client.chat_script = [
            _chat_response(_classifications_json([
                ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ])),
        ]
        mod.run_sample(
            client, ["FCA"], max_retries=MAX_RETRIES, types_csv=tmp_path / "x.csv"
        )
        out = capsys.readouterr().out
        assert "FCA" in out
        assert "Regulator / Supervisor" in out


class TestClientSeam:
    def test_make_client_is_a_seam(self, mod):
        """make_client exists so tests can avoid constructing a real client."""
        assert hasattr(mod, "make_client")
        assert callable(mod.make_client)

    def test_build_arg_parser_has_sample(self, mod):
        parser = mod.build_arg_parser()
        ns = parser.parse_args(["--sample", "5"])
        assert ns.sample == 5
        ns2 = parser.parse_args([])
        assert ns2.sample is None


# ===========================================================================
# Error-path observability: per-request batch errors + error file + guards
# ===========================================================================

def _error_line(custom_id, *, status_code=None, top_level_error=None):
    """Build a Batch output JSONL line representing a FAILED request."""
    record = {"custom_id": custom_id}
    if top_level_error is not None:
        record["error"] = top_level_error
        record["response"] = None
    else:
        record["error"] = None
        record["response"] = {"status_code": status_code, "body": None}
    return json.dumps(record)


class TestBatchErrorSurfacing:
    def test_extract_error_status_code(self, mod):
        """A non-200 status_code line is flagged errored with empty content."""
        line = _error_line("chunk-00000", status_code=500)
        custom_id, content, errored = mod.extract_output_line(line)
        assert custom_id == "chunk-00000"
        assert content == ""
        assert errored is True

    def test_extract_top_level_error(self, mod):
        """A top-level error with response: null is flagged errored."""
        line = _error_line(
            "chunk-00000", top_level_error={"code": "rate_limit", "message": "slow down"}
        )
        custom_id, content, errored = mod.extract_output_line(line)
        assert custom_id == "chunk-00000"
        assert content == ""
        assert errored is True

    def test_t1a_status_500_counted_and_retried(self, mod):
        """T1a: status_code 500 -> counted in batch_errors AND retried synchronously."""
        client = StubClient()
        # The synchronous retry resolves the chunk's two entities.
        client.chat_script = [
            _chat_response(_classifications_json([
                ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
                ("EBA", "Regulator / Supervisor", "European Banking Authority"),
            ])),
        ]
        expected = {"chunk-00000": ["FCA", "EBA"]}
        output_text = _error_line("chunk-00000", status_code=500) + "\n"

        rows, fallback, batch_errors = mod.collect_results(
            output_text, expected, client, max_retries=MAX_RETRIES
        )
        assert batch_errors == 1                # the failed request was counted
        assert len(client.chat_calls) == 1      # entities retried synchronously
        assert {r["entity"] for r in rows} == {"FCA", "EBA"}
        assert fallback == 0                    # retry resolved them

    def test_t1b_top_level_error_counted_and_retried(self, mod):
        """T1b: top-level error / response null -> same handling, no crash."""
        client = StubClient()
        # Retry stays malformed -> the single entity falls back to Other.
        client.chat_script = [_chat_response("garbage") for _ in range(MAX_RETRIES + 1)]
        expected = {"chunk-00000": ["Mystery"]}
        output_text = _error_line(
            "chunk-00000", top_level_error={"code": "server_error"}
        ) + "\n"

        rows, fallback, batch_errors = mod.collect_results(
            output_text, expected, client, max_retries=MAX_RETRIES
        )
        assert batch_errors == 1
        assert fallback == 1                     # retried, then fell back
        assert rows[0]["entity"] == "Mystery"
        assert rows[0]["type"] == "Other"        # entity not lost

    def test_collect_results_warns_on_errors(self, mod, caplog):
        """A nonzero batch-error count logs a WARNING."""
        import logging
        client = StubClient()
        client.chat_script = [
            _chat_response(_classifications_json([
                ("FCA", "Company", "Financial Conduct Authority"),
            ])),
        ]
        expected = {"chunk-00000": ["FCA"]}
        output_text = _error_line("chunk-00000", status_code=429) + "\n"
        with caplog.at_level(logging.WARNING):
            mod.collect_results(output_text, expected, client, max_retries=MAX_RETRIES)
        assert any("error status" in r.message for r in caplog.records)

    def test_t1c_error_file_id_fetched_and_surfaced(self, mod, tmp_path, caplog):
        """T1c: a populated error_file_id is fetched and its count surfaced/logged."""
        import logging
        client = StubClient()
        client.batch_script = [_batch(id="batch-EF", status="validating")]
        # Completed with BOTH an output file and an error file.
        client.retrieve_script = [
            _batch(
                id="batch-EF",
                status="completed",
                output_file_id="file-out-1",
                error_file_id="file-err-1",
            ),
        ]
        # _StubFiles.content returns the same text for every file id; make it a
        # valid output line for chunk-00000 AND treat it as the error file body
        # (one non-blank line -> error count of 1).
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
                ])}}]
            }},
        }) + "\n"

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        with caplog.at_level(logging.WARNING):
            result = mod.run_full(
                client,
                entities=["FCA"],
                requests_path=requests_path,
                sidecar_path=sidecar,
                types_csv=types_csv,
                chunk_size=ENTITY_CHUNK_SIZE,
                max_retries=MAX_RETRIES,
                poll_interval=0,
            )
        # The error file was fetched (a second files.content call) ...
        assert "file-err-1" in client.files_content_calls
        # ... its count was surfaced in the summary and logged.
        assert result["batch_errors"] >= 1
        assert any("never ran" in r.message for r in caplog.records)

    def test_i1_null_output_file_id_guarded(self, mod, tmp_path):
        """I1: completed batch with output_file_id None must not call files.content(None)."""
        client = StubClient()
        client.batch_script = [_batch(id="batch-NULL", status="validating")]
        # Completed but everything is in the error file (output_file_id None).
        client.retrieve_script = [
            _batch(
                id="batch-NULL",
                status="completed",
                output_file_id=None,
                error_file_id="file-err-1",
            ),
        ]
        # Error file body: one non-blank line.
        client.output_file_text = "some error record\n"
        # Sync retry resolves the single entity that never produced output.
        client.chat_script = [
            _chat_response(_classifications_json([
                ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ])),
        ]

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        result = mod.run_full(
            client,
            entities=["FCA"],
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        # files.content called for the error file only, NEVER with None.
        assert None not in client.files_content_calls
        assert client.files_content_calls == ["file-err-1"]
        # The entity was retried + merged, not lost.
        with open(types_csv, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert any(r["entity"] == "FCA" for r in rows)
        assert result["batch_errors"] >= 1


class TestEmptyCanonicalRejection:
    def test_t2_empty_canonical_treated_as_missing(self, mod):
        """T2: a returned row with canonical_name == "" lands in retry (rejected)."""
        sent = ["FCA"]
        content = _classifications_json([("FCA", "Company", "")])
        rows, missing = mod.parse_and_validate(content, sent)
        assert "FCA" in missing
        assert all(r["entity"] != "FCA" for r in rows)


class TestPollLoopBound:
    def test_resume_model_mismatch_submits_fresh(self, mod, tmp_path):
        """I2: sidecar model != OPENAI_MODEL -> submit fresh, not resume."""
        client = StubClient()
        client.batch_script = [_batch(id="batch-NEWMODEL", status="validating")]
        client.retrieve_script = [
            _batch(id="batch-NEWMODEL", status="completed", output_file_id="file-out-1"),
        ]
        client.output_file_text = json.dumps({
            "custom_id": "chunk-00000",
            "response": {"status_code": 200, "body": {
                "choices": [{"message": {"content": _classifications_json([
                    ("FCA", "Company", "Financial Conduct Authority"),
                ])}}]
            }},
        }) + "\n"

        requests_path = tmp_path / "requests.jsonl"
        sidecar = tmp_path / "state.json"
        types_csv = tmp_path / "entity_types.csv"

        # Sidecar matches the input hash but records a DIFFERENT model.
        mod.write_sidecar(sidecar, {
            "batch_id": "batch-OLDMODEL",
            "input_file_path": str(requests_path),
            "model": OPENAI_MODEL + "-stale",
            "input_row_count": 1,
            "input_sha256": mod.input_hash(["FCA"]),
        })

        mod.run_full(
            client,
            entities=["FCA"],
            requests_path=requests_path,
            sidecar_path=sidecar,
            types_csv=types_csv,
            chunk_size=ENTITY_CHUNK_SIZE,
            max_retries=MAX_RETRIES,
            poll_interval=0,
        )
        assert len(client.batches_create_calls) == 1  # fresh submit, not resume

    def test_poll_max_wait_exceeded_raises(self, mod):
        """I3: exceeding max_wait raises a BatchTerminalError, not an infinite loop."""
        client = StubClient()
        # Always returns a non-terminal status.
        client.retrieve_script = [_batch(id="batch-STUCK", status="in_progress")] * 50

        # Fake clock: each now() call advances time so the deadline trips fast.
        ticks = iter(range(0, 1000, 100))

        def fake_now():
            return next(ticks)

        with pytest.raises(mod.BatchTerminalError):
            mod._poll_until_terminal(
                client,
                "batch-STUCK",
                poll_interval=0,
                max_wait=150,
                sleep=lambda _s: None,
                now=fake_now,
            )

    def test_poll_tolerates_transient_errors(self, mod):
        """I3: a few transient retrieve errors are tolerated, then a terminal state wins."""
        client = StubClient()

        class _FlakyBatches:
            def __init__(self):
                self.calls = 0

            def retrieve(self, batch_id):
                self.calls += 1
                if self.calls <= 2:
                    raise RuntimeError("transient")
                return _batch(id=batch_id, status="completed", output_file_id="file-out-1")

        client.batches = _FlakyBatches()
        batch = mod._poll_until_terminal(
            client, "batch-FLAKY", poll_interval=0, sleep=lambda _s: None
        )
        assert batch.status == "completed"

    def test_poll_gives_up_after_too_many_errors(self, mod):
        """I3: more than MAX_POLL_RETRIEVE_ERRORS consecutive failures -> give up."""
        client = StubClient()

        class _AlwaysFails:
            def retrieve(self, batch_id):
                raise RuntimeError("down")

        client.batches = _AlwaysFails()
        with pytest.raises(mod.BatchTerminalError):
            mod._poll_until_terminal(
                client, "batch-DEAD", poll_interval=0, sleep=lambda _s: None
            )


class TestLazySampleRead:
    def test_i4_limit_reads_only_first_n(self, mod, tmp_path):
        """I4: read_distinct_entities(limit=N) returns only the first N entities."""
        entities = [f"ent{i:03d}" for i in range(120)]
        csv_path = tmp_path / "entity_mentions.csv"
        _write_mentions_csv(csv_path, entities)
        first_five = mod.read_distinct_entities(csv_path, limit=5)
        assert first_five == entities[:5]
        # No limit -> full read (unchanged behaviour).
        assert mod.read_distinct_entities(csv_path) == entities


class TestAtomicSidecar:
    def test_sidecar_roundtrip_is_atomic(self, mod, tmp_path):
        """M3: write_sidecar writes via temp file + replace; no stray .tmp remains."""
        sidecar = tmp_path / "state.json"
        state = {"batch_id": "b1", "input_sha256": "deadbeef", "model": OPENAI_MODEL}
        mod.write_sidecar(sidecar, state)
        assert mod.read_sidecar(sidecar) == state
        # The temp file was renamed away, not left behind.
        assert not (tmp_path / "state.json.tmp").exists()
