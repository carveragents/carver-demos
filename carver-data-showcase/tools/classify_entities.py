"""Classify distinct annotation entities into 6 buckets via the OpenAI Batch API.

This is the ONLY module in the repo that imports ``openai`` and reads
``OPENAI_API_KEY``.  Everything sensitive sits behind a small client seam
(``make_client`` / an injectable ``client`` argument) so the test-suite drives a
stub and never constructs a real client or needs a key.

Pipeline (full run, no ``--sample``):
  1. Read distinct entities from ``ENTITY_MENTIONS_CSV`` (file order — already
     count-desc then entity-asc, so chunking is reproducible from the file).
  2. Incremental cache: classify only entities absent from ``ENTITY_TYPES_CSV``.
  3. Build one Batch request line per chunk of ``ENTITY_CHUNK_SIZE`` and write
     ``ENTITY_BATCH_REQUESTS_JSONL``.
  4. Resume-or-submit via the sidecar ``ENTITY_BATCH_STATE_JSON`` (hash-keyed on
     the exact distinct-entity set): submit ONE batch and persist the sidecar
     BEFORE the first poll, or resume an in-flight batch.
  5. Poll (bounded by ``DEFAULT_MAX_WAIT``, tolerant of transient retrieve
     errors) to ``completed``; fetch the output file (guarding a null
     ``output_file_id``) AND inspect ``error_file_id`` for never-run requests;
     parse + validate; detect short / malformed chunks and per-request batch
     errors (counted + logged); retry the unresolved entities synchronously up
     to ``MAX_RETRIES``; fall back still-unresolved entities to ``Other``
     (logging the count); merge new rows into ``ENTITY_TYPES_CSV``; clear the
     sidecar.

``--sample N`` runs the synchronous path on N entities only (no Files upload, no
batch, no polling, no cache write) — handy for prompt iteration.  The sync path
is shared by the batch retry logic.

Run:
    .venv/bin/python tools/classify_entities.py            # full batch run
    .venv/bin/python tools/classify_entities.py --sample 20
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any, Iterable

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from carver_showcase.config import (  # noqa: E402
    ENTITY_BATCH_OUTPUT_JSONL,
    ENTITY_BATCH_REQUESTS_JSONL,
    ENTITY_BATCH_STATE_JSON,
    ENTITY_CHUNK_SIZE,
    ENTITY_MENTIONS_CSV,
    ENTITY_TYPE_DEFINITIONS,
    ENTITY_TYPES,
    ENTITY_TYPES_CSV,
    MAX_RETRIES,
    OPENAI_MODEL,
)

# Terminal batch states (per OpenAI Batch API) that mean "give up, allow resubmit".
TERMINAL_BAD_STATES = frozenset({"failed", "expired", "cancelled", "cancelling"})
COMPLETED_STATE = "completed"
ENTITY_TYPES_HEADER = ["entity", "type", "canonical_name"]
JSON_MODE_KEY = "classifications"
DEFAULT_POLL_INTERVAL = 30  # seconds between batch status polls in a real run
# Upper bound on the poll loop so a stuck/never-terminal batch fails loudly
# instead of hanging forever.  24h matches the Batch completion window; the
# sidecar survives, so a rerun simply resumes the same in-flight batch.
DEFAULT_MAX_WAIT = 26 * 60 * 60  # seconds (24h window + a 2h grace margin)
# How many consecutive transient retrieve errors to tolerate before giving up.
MAX_POLL_RETRIEVE_ERRORS = 5

_ENTITY_TYPE_SET = frozenset(ENTITY_TYPES)


class BatchTerminalError(RuntimeError):
    """Raised when a batch reaches a terminal failed / expired / cancelled state."""


# ===========================================================================
# Prompt construction (the 6-bucket taxonomy carried ONCE in the system message)
# ===========================================================================

def _taxonomy_block() -> str:
    """Render the 6-bucket taxonomy + definitions for the system message."""
    return "\n".join(f"- {name}: {ENTITY_TYPE_DEFINITIONS[name]}" for name in ENTITY_TYPES)


SYSTEM_PROMPT = (
    "You are an expert at classifying named entities found in regulatory updates.\n"
    "Classify each input entity into EXACTLY ONE of these six types:\n"
    f"{_taxonomy_block()}\n\n"
    "For every input entity, emit one object with these three fields:\n"
    '  - "entity": the input string, echoed VERBATIM.\n'
    '  - "type": exactly one of the six type strings above.\n'
    '  - "canonical_name": the full, de-abbreviated, conventionally-cased name '
    "(e.g. \"FCA\" -> \"Financial Conduct Authority\").\n"
    "If an entity is unidentifiable, use type \"Other\" and set canonical_name to "
    "the input string unchanged.\n"
    "Return the SAME number of objects as inputs, in the SAME order.\n"
    'Respond with strict JSON only, shaped as: '
    '{"classifications": [{"entity": ..., "type": ..., "canonical_name": ...}, ...]}.'
)


def _user_prompt(entities: list[str]) -> str:
    """Render the per-chunk user message listing the entities to classify."""
    listing = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(entities))
    return (
        f"Classify these {len(entities)} entities (return one object each, in order):\n"
        f"{listing}"
    )


# ===========================================================================
# 2.1  Deterministic chunking + request builder (pure)
# ===========================================================================

def read_distinct_entities(
    csv_path: pathlib.Path | str, *, limit: int | None = None
) -> list[str]:
    """Read the ``entity`` column from an entity-mentions CSV in file order.

    File order is the count-desc / entity-asc order written by
    ``tools/extract_terms.py``, so downstream chunking is reproducible from the
    file alone.  Missing / blank entities are skipped.  When ``limit`` is set,
    the file is read lazily and only the first ``limit`` distinct entities are
    returned (no full ~281K-row load for a small ``--sample``).
    """
    entities: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            value = (row.get("entity") or "").strip()
            if value:
                entities.append(value)
                if limit is not None and len(entities) >= limit:
                    break
    return entities


def chunk_entities(entities: list[str], chunk_size: int) -> list[list[str]]:
    """Split ``entities`` into contiguous groups of ``chunk_size`` (last is remainder)."""
    return [entities[i : i + chunk_size] for i in range(0, len(entities), chunk_size)]


def build_request_line(index: int, entities: list[str]) -> dict[str, Any]:
    """Build one Batch request line for a chunk: ``custom_id = chunk-{index:05d}``."""
    return {
        "custom_id": f"chunk-{index:05d}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(entities)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
    }


def write_request_file(
    entities: list[str], path: pathlib.Path | str, chunk_size: int
) -> int:
    """Write one Batch request line per chunk to ``path``.  Returns the line count."""
    chunks = chunk_entities(entities, chunk_size)
    with open(path, "w", encoding="utf-8") as fh:
        for i, chunk in enumerate(chunks):
            fh.write(json.dumps(build_request_line(i, chunk)) + "\n")
    return len(chunks)


def chunk_map(entities: list[str], chunk_size: int) -> dict[str, list[str]]:
    """Map each ``custom_id`` to the exact entity list sent in that chunk."""
    return {
        f"chunk-{i:05d}": chunk
        for i, chunk in enumerate(chunk_entities(entities, chunk_size))
    }


# ===========================================================================
# 2.2  Response parser + schema validation (pure)
# ===========================================================================

def _valid_row(obj: Any) -> bool:
    """Row is valid iff it has all three fields, a known type, and a non-empty
    ``canonical_name`` (an empty ``canonical_name`` is rejected as missing)."""
    return (
        isinstance(obj, dict)
        and isinstance(obj.get("entity"), str)
        and isinstance(obj.get("canonical_name"), str)
        and obj.get("canonical_name") != ""
        and obj.get("type") in _ENTITY_TYPE_SET
    )


def parse_and_validate(
    content: str, sent: list[str]
) -> tuple[list[dict[str, str]], list[str]]:
    """Parse a model response into validated rows, returning ``(rows, missing)``.

    ``rows`` are the valid ``{entity, type, canonical_name}`` objects whose
    entity is one of those sent.  ``missing`` is the list of sent entities that
    were NOT validly returned (short, malformed JSON, bad type, missing field,
    or simply absent) — these are the ones to retry/fall back.  A well-formed
    ``type="Other"`` row is valid (not a failure).  Order of ``missing`` follows
    ``sent``.
    """
    sent_set = set(sent)
    resolved: dict[str, dict[str, str]] = {}

    try:
        payload = json.loads(content)
        objects = payload.get(JSON_MODE_KEY) if isinstance(payload, dict) else None
    except (json.JSONDecodeError, TypeError):
        objects = None

    if isinstance(objects, list):
        for obj in objects:
            if not _valid_row(obj):
                continue
            entity = obj["entity"]
            if entity in sent_set and entity not in resolved:
                resolved[entity] = {
                    "entity": entity,
                    "type": obj["type"],
                    "canonical_name": obj["canonical_name"],
                }

    rows = [resolved[e] for e in sent if e in resolved]
    missing = [e for e in sent if e not in resolved]
    return rows, missing


def extract_output_line(line: str) -> tuple[str | None, str, bool]:
    """Extract ``(custom_id, message_content, errored)`` from a Batch output line.

    ``errored`` is ``True`` when the line represents a *failed* request rather
    than a normal completion: a non-null top-level ``error`` (whose ``response``
    is typically ``null``), or a ``response.status_code`` other than 200.  Such a
    request produced no usable content, so the caller both COUNTS it as a batch
    error and routes its entities through the synchronous retry path.

    Returns ``(custom_id, "")`` (with ``errored=False``) when the line is merely
    malformed JSON or a completion with no usable content — distinct from an
    explicit error status so a clean-but-empty chunk is not miscounted.
    """
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None, "", False
    custom_id = record.get("custom_id")

    # A failed request: top-level error set, or a non-200 response status.
    if record.get("error") is not None:
        return custom_id, "", True
    response = record.get("response")
    if isinstance(response, dict) and response.get("status_code") not in (None, 200):
        return custom_id, "", True

    try:
        content = record["response"]["body"]["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = ""
    return custom_id, content or "", False


# ===========================================================================
# Sync (synchronous chat) path — shared by --sample and the batch retry logic
# ===========================================================================

def _chat_content(response: Any) -> str:
    """Pull the message content string out of a chat.completions response."""
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        return ""


def classify_sync(client: Any, entities: list[str]) -> str:
    """One synchronous chat.completions call classifying ``entities``; returns content."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(entities)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return _chat_content(response)


def _fallback_rows(entities: Iterable[str]) -> list[dict[str, str]]:
    """Fall back unresolved entities to ``type="Other", canonical_name=entity``."""
    return [
        {"entity": e, "type": "Other", "canonical_name": e} for e in entities
    ]


# ===========================================================================
# 2.3  detect -> retry -> bounded fallback (orchestration over the sync path)
# ===========================================================================

def resolve_with_retry(
    client: Any,
    entities: list[str],
    *,
    max_retries: int,
) -> tuple[list[dict[str, str]], int]:
    """Classify ``entities`` synchronously, retrying only the unresolved ones.

    Up to ``max_retries`` re-sends (each carrying only the still-unresolved
    entities); any entity still unresolved after that falls back to ``Other``.
    Returns ``(rows, fallback_count)`` where ``rows`` covers every input entity.
    """
    resolved: dict[str, dict[str, str]] = {}
    pending = list(entities)

    attempts = max_retries + 1  # one initial attempt plus the retries
    for _ in range(attempts):
        if not pending:
            break
        content = classify_sync(client, pending)
        rows, missing = parse_and_validate(content, pending)
        for row in rows:
            resolved[row["entity"]] = row
        pending = missing

    fallback_count = len(pending)
    for row in _fallback_rows(pending):
        resolved[row["entity"]] = row

    ordered = [resolved[e] for e in entities]
    return ordered, fallback_count


# ===========================================================================
# 2.4  Incremental cache + input hash + sidecar + merge (pure/IO helpers)
# ===========================================================================

def _read_cached_entities(types_csv: pathlib.Path | str) -> set[str]:
    """Return the set of entities already present in ``types_csv`` (empty if absent)."""
    path = pathlib.Path(types_csv)
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as fh:
        return {
            (row.get("entity") or "").strip()
            for row in csv.DictReader(fh)
            if (row.get("entity") or "").strip()
        }


def entities_to_classify(
    entities: list[str], types_csv: pathlib.Path | str
) -> list[str]:
    """Set-difference: entities absent from the cache, preserving file order."""
    cached = _read_cached_entities(types_csv)
    return [e for e in entities if e not in cached]


def input_hash(entities: list[str]) -> str:
    """SHA-256 over the distinct-entity SET (order-invariant, content-sensitive)."""
    payload = "\n".join(sorted(set(entities)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_sidecar(path: pathlib.Path | str, state: dict[str, Any]) -> None:
    """Persist the batch sidecar atomically (temp file + ``os.replace``).

    Writing to a sibling temp file and renaming means a crash mid-write leaves
    the previous sidecar intact rather than a truncated/corrupt one, so a rerun
    can always resume the in-flight batch.
    """
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_sidecar(path: pathlib.Path | str) -> dict[str, Any] | None:
    """Load the sidecar, or ``None`` if it is missing / unreadable."""
    p = pathlib.Path(path)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def clear_sidecar(path: pathlib.Path | str) -> None:
    """Remove the sidecar if present (idempotent)."""
    p = pathlib.Path(path)
    if p.exists():
        p.unlink()


def merge_into_cache(
    rows: list[dict[str, str]], types_csv: pathlib.Path | str
) -> int:
    """Append new ``rows`` into ``types_csv`` (create with header if absent).

    Rows whose entity is already cached are skipped (idempotent merge).
    Returns the number of rows actually written.
    """
    path = pathlib.Path(types_csv)
    cached = _read_cached_entities(path)
    new_rows = [r for r in rows if r["entity"] not in cached]
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ENTITY_TYPES_HEADER)
        if write_header:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)
    return len(new_rows)


# ===========================================================================
# Batch output collection: parse every line, retry/fallback unresolved chunks
# ===========================================================================

def collect_results(
    output_text: str,
    expected: dict[str, list[str]],
    client: Any,
    *,
    max_retries: int,
) -> tuple[list[dict[str, str]], int, int]:
    """Parse batch output, reconcile per chunk, retry+fallback the unresolved.

    ``expected`` maps ``custom_id -> entities sent`` so each output line is
    validated against the exact chunk it answers.  Any short / malformed chunk —
    and the specific missing entities within an otherwise-valid chunk — are
    collected and re-classified synchronously (``resolve_with_retry``).

    A line that signals a *failed* request (per ``extract_output_line``) is
    COUNTED in ``batch_errors`` and its entities are still routed through the
    retry path so they are never lost.  When ``batch_errors`` is nonzero a
    ``WARNING`` is logged.

    Returns ``(all_rows, total_fallback_count, batch_errors)``.
    """
    all_rows: list[dict[str, str]] = []
    unresolved: list[str] = []
    seen_ids: set[str] = set()
    batch_errors = 0

    for line in output_text.splitlines():
        if not line.strip():
            continue
        custom_id, content, errored = extract_output_line(line)
        if custom_id is None or custom_id not in expected:
            continue
        seen_ids.add(custom_id)
        sent = expected[custom_id]
        if errored:
            batch_errors += 1
            unresolved.extend(sent)  # retry every entity in the failed chunk
            continue
        rows, missing = parse_and_validate(content, sent)
        all_rows.extend(rows)
        unresolved.extend(missing)

    # Chunks with no output line at all are entirely unresolved.
    for custom_id, sent in expected.items():
        if custom_id not in seen_ids:
            unresolved.extend(sent)

    if batch_errors:
        logger.warning(
            "%d batch requests returned an error status; their entities were "
            "retried synchronously.",
            batch_errors,
        )

    fallback_total = 0
    if unresolved:
        retry_rows, fallback_total = resolve_with_retry(
            client, unresolved, max_retries=max_retries
        )
        all_rows.extend(retry_rows)

    return all_rows, fallback_total, batch_errors


# ===========================================================================
# Batch submit / resume / poll orchestration (network — uses the client seam)
# ===========================================================================

def _submit_batch(
    client: Any,
    *,
    requests_path: pathlib.Path,
    sidecar_path: pathlib.Path,
    entities: list[str],
    row_count: int,
) -> str:
    """Upload the request file, create ONE batch, persist the sidecar, return id."""
    with open(requests_path, "rb") as fh:
        uploaded = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    # Persist the sidecar BEFORE the first poll so a crash mid-run can resume.
    write_sidecar(
        sidecar_path,
        {
            "batch_id": batch.id,
            "input_file_path": str(requests_path),
            "model": OPENAI_MODEL,
            "input_row_count": row_count,
            "input_sha256": input_hash(entities),
        },
    )
    return batch.id


def _poll_until_terminal(
    client: Any,
    batch_id: str,
    *,
    poll_interval: float,
    max_wait: float = DEFAULT_MAX_WAIT,
    sleep: Any = time.sleep,
    now: Any = time.monotonic,
) -> Any:
    """Poll the batch until ``completed`` or a terminal-bad state.

    Bounded and observability-friendly:
      - each poll prints ``status`` + elapsed seconds so a long run shows progress;
      - a transient ``retrieve`` error is tolerated up to
        ``MAX_POLL_RETRIEVE_ERRORS`` consecutive failures (the sidecar survives,
        so a rerun resumes regardless);
      - if ``max_wait`` seconds elapse without a terminal state, a
        ``BatchTerminalError`` is raised rather than looping forever.

    ``sleep``/``now`` are injectable so tests run instantly and deterministically.
    """
    start = now()
    consecutive_errors = 0
    while True:
        try:
            batch = client.batches.retrieve(batch_id)
            consecutive_errors = 0
        except Exception as exc:  # transient network / API hiccup
            consecutive_errors += 1
            if consecutive_errors > MAX_POLL_RETRIEVE_ERRORS:
                raise BatchTerminalError(
                    f"batch {batch_id} status check failed "
                    f"{consecutive_errors} times in a row; giving up "
                    f"(sidecar preserved — rerun to resume): {exc}"
                ) from exc
            logger.warning(
                "transient error polling batch %s (%d/%d): %s",
                batch_id, consecutive_errors, MAX_POLL_RETRIEVE_ERRORS, exc,
            )
            if poll_interval:
                sleep(poll_interval)
            continue

        status = getattr(batch, "status", None)
        elapsed = now() - start
        print(f"batch {batch_id} status={status!r} (elapsed {elapsed:.0f}s)", flush=True)
        if status == COMPLETED_STATE or status in TERMINAL_BAD_STATES:
            return batch
        if elapsed >= max_wait:
            raise BatchTerminalError(
                f"batch {batch_id} did not reach a terminal state within "
                f"{max_wait:.0f}s (last status {status!r}); sidecar preserved — "
                f"rerun to resume."
            )
        if poll_interval:
            sleep(poll_interval)


def _fetch_output_text(
    client: Any, file_id: str, *, local_copy: pathlib.Path | str | None = ENTITY_BATCH_OUTPUT_JSONL
) -> str:
    """Download a batch file's text, optionally persisting a local copy.

    ``local_copy`` defaults to the output-file snapshot; pass ``None`` (used for
    the error file) to skip writing so the two fetches don't clobber each other.
    """
    content = client.files.content(file_id)
    text = getattr(content, "text", None)
    if text is None:
        raw = getattr(content, "content", b"")
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    if local_copy is not None:
        try:
            with open(local_copy, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass  # the local copy is a convenience, not load-bearing
    return text


def run_full(
    client: Any,
    *,
    entities: list[str],
    requests_path: pathlib.Path | str,
    sidecar_path: pathlib.Path | str,
    types_csv: pathlib.Path | str,
    chunk_size: int = ENTITY_CHUNK_SIZE,
    max_retries: int = MAX_RETRIES,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> dict[str, Any]:
    """Full batch run: incremental cache -> submit/resume -> poll -> merge.

    Returns a small summary dict (``submitted``, ``classified``, ``fallback``,
    ``batch_errors``).
    """
    requests_path = pathlib.Path(requests_path)
    sidecar_path = pathlib.Path(sidecar_path)
    types_csv = pathlib.Path(types_csv)

    todo = entities_to_classify(entities, types_csv)
    if not todo:
        print("entity_types cache is complete — no batch submitted.", flush=True)
        return {"submitted": False, "classified": 0, "fallback": 0, "batch_errors": 0}

    current_hash = input_hash(todo)
    sidecar = read_sidecar(sidecar_path)

    resumable = (
        sidecar is not None
        and sidecar.get("input_sha256") == current_hash
        and sidecar.get("model") == OPENAI_MODEL
    )
    if resumable:
        # Resume the in-flight batch — do NOT re-upload or create a new one.
        batch_id = sidecar["batch_id"]
        print(f"resuming in-flight batch {batch_id} ({len(todo):,} entities).", flush=True)
    else:
        # No sidecar, or it points at a different input set / model: submit fresh.
        if sidecar:
            print("sidecar input set or model changed — submitting a fresh batch.",
                  flush=True)
        row_count = write_request_file(todo, requests_path, chunk_size)
        batch_id = _submit_batch(
            client,
            requests_path=requests_path,
            sidecar_path=sidecar_path,
            entities=todo,
            row_count=row_count,
        )
        print(f"submitted batch {batch_id} ({len(todo):,} entities, {row_count} chunks).",
              flush=True)

    batch = _poll_until_terminal(
        client, batch_id, poll_interval=poll_interval, max_wait=max_wait
    )
    status = getattr(batch, "status", None)

    if status in TERMINAL_BAD_STATES:
        clear_sidecar(sidecar_path)  # allow a resubmit next run
        raise BatchTerminalError(
            f"batch {batch_id} ended in terminal state {status!r}; sidecar cleared."
        )

    # I1: a completed batch can carry a null output_file_id (everything errored).
    # Don't call files.content(None) — rely on the error-file path + missing-line
    # retry instead.
    output_file_id = getattr(batch, "output_file_id", None)
    if output_file_id is None:
        print(f"WARNING: batch {batch_id} completed with no output file; "
              f"all chunks will be retried synchronously.", flush=True)
        output_text = ""
    else:
        output_text = _fetch_output_text(client, output_file_id)

    # C2: requests that never executed land in the error file, not the output
    # file.  Count them so a partially-errored batch is not silently treated as
    # clean; their chunks still flow through the missing-line retry below.
    error_file_id = getattr(batch, "error_file_id", None)
    error_file_count = 0
    if error_file_id is not None:
        error_text = _fetch_output_text(client, error_file_id, local_copy=None)
        error_file_count = sum(1 for ln in error_text.splitlines() if ln.strip())
        if error_file_count:
            logger.warning(
                "%d batch requests never ran (error_file_id=%s); their entities "
                "were retried synchronously.",
                error_file_count, error_file_id,
            )
            print(f"WARNING: {error_file_count:,} batch requests landed in the "
                  f"error file; their entities will be retried synchronously.",
                  flush=True)

    expected = chunk_map(todo, chunk_size)
    rows, fallback, output_errors = collect_results(
        output_text, expected, client, max_retries=max_retries
    )
    batch_errors = output_errors + error_file_count

    merged = merge_into_cache(rows, types_csv)
    clear_sidecar(sidecar_path)  # only after a successful merge

    if fallback:
        print(f"WARNING: {fallback:,} entities fell back to 'Other' after "
              f"{max_retries} retries.", flush=True)
    print(f"merged {merged:,} new classifications into {types_csv}.", flush=True)
    return {
        "submitted": True,
        "classified": merged,
        "fallback": fallback,
        "batch_errors": batch_errors,
    }


# ===========================================================================
# 2.5  --sample N synchronous path
# ===========================================================================

def run_sample(
    client: Any,
    entities: list[str],
    *,
    max_retries: int = MAX_RETRIES,
    types_csv: pathlib.Path | str = ENTITY_TYPES_CSV,  # noqa: ARG001 (never written)
) -> list[dict[str, str]]:
    """Classify ``entities`` synchronously, print the result, write NO cache."""
    rows, fallback = resolve_with_retry(client, entities, max_retries=max_retries)
    for row in rows:
        print(f"  {row['entity']!r:40s} -> {row['type']:24s} | {row['canonical_name']}",
              flush=True)
    if fallback:
        print(f"({fallback} of {len(entities)} fell back to 'Other')", flush=True)
    return rows


# ===========================================================================
# Client seam + CLI wiring
# ===========================================================================

def make_client() -> Any:
    """Construct a real OpenAI client.  The ONLY place a key is read.

    Kept tiny and import-local so tests inject a stub and never call this.
    """
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI parser: optional ``--sample N`` selects the synchronous path."""
    parser = argparse.ArgumentParser(
        description="Classify distinct annotation entities into 6 types via the "
        "OpenAI Batch API (or a synchronous sample with --sample)."
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Classify N entities synchronously (no batch, no cache write) "
        "for prompt iteration.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)

    if not ENTITY_MENTIONS_CSV.exists():
        print(
            f"ERROR: {ENTITY_MENTIONS_CSV} not found. Run tools/extract_terms.py first.",
            flush=True,
        )
        sys.exit(1)

    client = make_client()

    if args.sample is not None:
        # I4: read only the first N distinct entities, not the whole CSV.
        sample = read_distinct_entities(ENTITY_MENTIONS_CSV, limit=args.sample)
        print(f"--sample: classifying {len(sample)} entities synchronously\n", flush=True)
        run_sample(client, sample, max_retries=MAX_RETRIES, types_csv=ENTITY_TYPES_CSV)
        return

    entities = read_distinct_entities(ENTITY_MENTIONS_CSV)
    run_full(
        client,
        entities=entities,
        requests_path=ENTITY_BATCH_REQUESTS_JSONL,
        sidecar_path=ENTITY_BATCH_STATE_JSON,
        types_csv=ENTITY_TYPES_CSV,
        chunk_size=ENTITY_CHUNK_SIZE,
        max_retries=MAX_RETRIES,
        poll_interval=DEFAULT_POLL_INTERVAL,
    )


if __name__ == "__main__":
    main()
