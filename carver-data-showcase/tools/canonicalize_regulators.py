"""Deduplicate the ~11.4k raw, multilingual ``regulator_name`` values into a
canonical English name + an ``is_regulator`` flag.

``is_regulator`` is true for any governmental / public-sector body (regulators,
supervisors, central banks, ministries / departments / agencies, and
intergovernmental / standard-setting organisations) and false only for clearly
private-sector entities (companies, news / media outlets, named individuals,
trade associations).

Two transports are provided: the OpenAI **Batch** API (``run_full``) and a
**synchronous** path that classifies every name with sequential / concurrent
chat calls (``run_sync_full``, exposed as ``--sync-full [--workers N]``) for when
the batch queue is slow.  Both share the same prompt, validation, retry, and
merge logic.

This is the ONLY module in the repo (besides ``tools/classify_entities.py``)
that imports ``openai`` and reads ``OPENAI_API_KEY``.  Everything sensitive sits
behind a small client seam (``make_client`` / an injectable ``client`` argument)
so the test-suite drives a stub and never constructs a real client or needs a
key.

The pipeline mirrors the entity-typing job exactly:

PART A — pure context aggregation (no client):
  1. ``load_regulator_frame`` reads only the needed columns from the normalized
     annotations parquet.
  2. ``build_context`` collapses the rows to one compact record per distinct
     non-null ``regulator_name`` (mentions, top countries, dominant scope,
     divisions, official domains, sample titles), ordered ``mentions`` desc then
     ``name`` asc so chunking is reproducible.
  3. ``write_context_csv`` writes a reproducible debug artifact, storing the
     list-valued fields as JSON strings so they round-trip cleanly.

PART B — Batch LLM canonicalization (mirrors classify_entities):
  4. Incremental cache: canonicalize only names absent from
     ``REGULATOR_CANONICAL_CSV``.
  5. Build one Batch request line per chunk of ``REGULATOR_CHUNK_SIZE`` and write
     ``REGULATOR_BATCH_REQUESTS_JSONL``.
  6. Resume-or-submit via the sidecar ``REGULATOR_BATCH_STATE_JSON`` (hash-keyed
     on the exact sorted distinct-name set): submit ONE batch and persist the
     sidecar BEFORE the first poll, or resume an in-flight batch.
  7. Poll (bounded by ``DEFAULT_MAX_WAIT``, tolerant of transient retrieve
     errors) to ``completed``; fetch the output file (guarding a null
     ``output_file_id``) AND inspect ``error_file_id`` for never-run requests;
     parse + validate; retry the unresolved names synchronously up to
     ``MAX_RETRIES``; fall back still-unresolved names to ``canonical = raw,
     is_regulator = True`` (conservative — never silently drop a name); merge new
     rows into ``REGULATOR_CANONICAL_CSV``; clear the sidecar.

``--sample N`` runs the synchronous path on N names only (no Files upload, no
batch, no polling, no cache write) — handy for prompt iteration.  The sync path
is shared by the batch retry logic.

``--sync-full`` classifies every distinct regulator name via sequential
synchronous chat calls (no Batch API), checkpointing after each chunk for
resumability.  Use when the Batch endpoint is queue-stalled.

Run:
    .venv/bin/python tools/canonicalize_regulators.py            # full batch run
    .venv/bin/python tools/canonicalize_regulators.py --sample 20
    .venv/bin/python tools/canonicalize_regulators.py --sync-full
    .venv/bin/python tools/canonicalize_regulators.py --sync-full --workers 6
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import logging
import os
import pathlib
import sys
import time
from collections import Counter
from typing import Any
from urllib.parse import urlparse

import pandas as pd

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from carver_showcase.config import (  # noqa: E402
    ANNOTATIONS_PARQUET,
    MAX_RETRIES,
    OPENAI_MODEL,
    REGULATOR_BATCH_OUTPUT_JSONL,
    REGULATOR_BATCH_REQUESTS_JSONL,
    REGULATOR_BATCH_STATE_JSON,
    REGULATOR_CANONICAL_CSV,
    REGULATOR_CHUNK_SIZE,
    REGULATOR_CONTEXT_CSV,
    REGULATOR_CTX_MAX_DIVISIONS,
    REGULATOR_CTX_MAX_DOMAINS,
    REGULATOR_CTX_MAX_TITLES,
    REGULATOR_CTX_TITLE_MAXLEN,
    REGULATOR_CTX_TOP_COUNTRIES,
)

# Terminal batch states (per OpenAI Batch API) that mean "give up, allow resubmit".
TERMINAL_BAD_STATES = frozenset({"failed", "expired", "cancelled", "cancelling"})
COMPLETED_STATE = "completed"
# Columns of the canonical cache CSV (the merge output).
CANONICAL_HEADER = ["regulator_name", "canonical_regulator", "is_regulator", "mentions"]
# Columns of the reproducible context debug CSV.
CONTEXT_HEADER = [
    "regulator_name",
    "mentions",
    "countries",
    "scope",
    "divisions",
    "domains",
    "sample_titles",
]
# The list-valued context fields stored as JSON strings (round-trip cleanly).
_CONTEXT_LIST_FIELDS = ("countries", "divisions", "domains", "sample_titles")
JSON_MODE_KEY = "results"
DEFAULT_POLL_INTERVAL = 30  # seconds between batch status polls in a real run
# Upper bound on the poll loop so a stuck/never-terminal batch fails loudly
# instead of hanging forever.  24h matches the Batch completion window; the
# sidecar survives, so a rerun simply resumes the same in-flight batch.
DEFAULT_MAX_WAIT = 26 * 60 * 60  # seconds (24h window + a 2h grace margin)
# How many consecutive transient retrieve errors to tolerate before giving up.
MAX_POLL_RETRIEVE_ERRORS = 5

# Columns pulled from the annotations parquet for context aggregation.
_FRAME_COLUMNS = [
    "regulator_name",
    "jurisdiction_country",
    "jurisdiction_scope",
    "regulator_division",
    "base_url",
    "title",
]

# TODO: tools/classify_entities.py and this module duplicate the OpenAI Batch
# plumbing (client seam, chunking, sidecar read/write/clear, input_hash, bounded
# poll loop, extract_output_line, output fetch).  Consolidate the shared helpers
# into tools/_openai_batch.py once a third consumer appears.


class BatchTerminalError(RuntimeError):
    """Raised when a batch reaches a terminal failed / expired / cancelled state."""


# ===========================================================================
# Prompt construction (the canonicalization instruction carried ONCE in system)
# ===========================================================================

SYSTEM_PROMPT = (
    "You are an expert at normalizing the names of regulatory and supervisory "
    "bodies found in regulatory updates.\n"
    "You receive a JSON list of records, each describing one raw "
    '"regulator_name" string together with disambiguating context (how many '
    "times it appears, the most common jurisdiction countries, its dominant "
    "jurisdiction scope, any divisions/offices, its official web domains, and a "
    "few sample document titles it published).\n\n"
    "For EVERY record, decide two things:\n"
    '  - "canonical_name": the standard ENGLISH name of the regulatory / '
    "supervisory body. Expand abbreviations, drop parenthetical asides, "
    "translate native-language names to their official English name, and fold "
    "sub-units, divisions, and regional offices to their PARENT body.\n"
    '  - "is_regulator": true for ANY governmental or public-sector body. This '
    "includes: (a) regulators, supervisors, and central banks; (b) any "
    "government ministry, department, agency, authority, commission, "
    "legislature, court, prosecutor, or law-enforcement body, at national, "
    "state/provincial, or local level; and (c) intergovernmental / international "
    "organisations and official standard-setting bodies (e.g. the UN, OECD, IMF, "
    "World Bank, WHO, FATF, the Basel Committee, IOSCO, and EU institutions). "
    "Set it false ONLY for clearly NON-governmental entities: commercial "
    "companies and firms, news / media outlets, named individuals, and "
    "private-sector trade associations, industry groups, lobbying organisations, "
    "think-tanks, and forums. Use the context (country, official domain, "
    "divisions, what its titles publish) to decide; when genuinely unsure, "
    "prefer true.\n\n"
    "Return the SAME number of objects as inputs, echoing each input name so "
    "results map back.\n"
    "Respond with strict JSON only, shaped as: "
    '{"results": [{"name": <echoed raw name>, "canonical_name": <str>, '
    '"is_regulator": <bool>}, ...]}.'
)


def _user_prompt(records: list[dict[str, Any]]) -> str:
    """Render the per-chunk user message listing the records to canonicalize."""
    listing = json.dumps(records, ensure_ascii=False, indent=None)
    return (
        f"Canonicalize these {len(records)} regulator-name records (return one "
        f"object each, echoing every name):\n{listing}"
    )


# ===========================================================================
# PART A — Pure context aggregation (no client; fully unit-tested)
# ===========================================================================

def load_regulator_frame(
    parquet_path: pathlib.Path | str = ANNOTATIONS_PARQUET,
) -> pd.DataFrame:
    """Read ONLY the columns needed for context aggregation from the parquet."""
    return pd.read_parquet(parquet_path, columns=_FRAME_COLUMNS)


def _top_values(series: pd.Series, limit: int) -> list[str]:
    """Most-frequent non-null string values of ``series``, up to ``limit``.

    Ties break by value ascending so the output is reproducible.  Missing
    (NaN/None) values are dropped; remaining values are coerced to ``str``.
    """
    counts: Counter = Counter()
    for value in series.dropna():
        text = str(value).strip()
        if text:
            counts[text] += 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [value for value, _ in ordered[:limit]]


def _host_of(url: Any) -> str:
    """Parse a host from a ``base_url`` value (``urlparse(...).netloc``).

    The real ``base_url`` data is a mix of full URLs and bare hosts (e.g.
    ``"fca.org.uk"``), so when ``netloc`` is empty we fall back to the path's
    first segment.  A leading ``www.`` is stripped.  A trailing ``:port``
    suffix (e.g. ``fca.org.uk:8080``) is also stripped so the domain shown to
    the model is clean.  Returns ``""`` for missing / malformed input so the
    caller can skip it.

    Note: ``urlparse("fca.org.uk:8080")`` mis-parses the domain as the scheme
    and the port as the path (no double-slash, no real scheme).  We detect this
    by checking whether ``netloc`` is empty but ``scheme`` looks like a domain
    (contains a dot), and use ``scheme`` as the host in that case.
    """
    if not isinstance(url, str):
        return ""
    text = url.strip()
    if not text:
        return ""
    parsed = urlparse(text)
    host = parsed.netloc.lower()
    if not host:
        # urlparse("fca.org.uk:8080") -> scheme="fca.org.uk", path="8080".
        # Detect a bare host+port mis-parsed as scheme by looking for a dot.
        if parsed.scheme and "." in parsed.scheme:
            host = parsed.scheme.lower()
        else:  # plain bare host (no scheme, no port) lands in path
            host = parsed.path.lower().split("/")[0]
    if host.startswith("www."):
        host = host[4:]
    # Strip a trailing :port if present (e.g. netloc "fca.org.uk:8080" -> "fca.org.uk").
    if ":" in host:
        host = host.split(":")[0]
    return host


def _top_domains(series: pd.Series, limit: int) -> list[str]:
    """Most-frequent non-empty hosts parsed from ``base_url``, up to ``limit``."""
    counts: Counter = Counter()
    for value in series.dropna():
        host = _host_of(value)
        if host:
            counts[host] += 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [host for host, _ in ordered[:limit]]


def _sample_titles(series: pd.Series, limit: int, maxlen: int) -> list[str]:
    """Up to ``limit`` representative non-null titles, each truncated to ``maxlen``.

    Picks the most frequent titles (ties broken by title ascending), so the
    sample is reproducible and biased toward representative documents.
    """
    counts: Counter = Counter()
    for value in series.dropna():
        text = str(value).strip()
        if text:
            counts[text] += 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [title[:maxlen] for title, _ in ordered[:limit]]


def build_context(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate one compact context record per distinct non-null regulator name.

    Each record carries ``name``, ``mentions``, ``countries`` (top-N most
    frequent), ``scope`` (single most frequent, or ``""``), ``divisions``,
    ``domains`` (parsed hosts), and ``sample_titles`` (truncated).  Output is
    ordered by ``mentions`` desc then ``name`` asc so downstream chunking is
    reproducible.  Missingness is read from real NaN/None — the literal string
    ``"NA"`` is a genuine value, not missing.
    """
    rows: list[dict[str, Any]] = []
    # Group on the raw name; dropna drops the NaN/None name group entirely.
    for name, group in df.groupby("regulator_name", dropna=True, sort=False):
        countries = _top_values(
            group["jurisdiction_country"], REGULATOR_CTX_TOP_COUNTRIES
        )
        scope_top = _top_values(group["jurisdiction_scope"], 1)
        divisions = _top_values(
            group["regulator_division"], REGULATOR_CTX_MAX_DIVISIONS
        )
        domains = _top_domains(group["base_url"], REGULATOR_CTX_MAX_DOMAINS)
        sample_titles = _sample_titles(
            group["title"], REGULATOR_CTX_MAX_TITLES, REGULATOR_CTX_TITLE_MAXLEN
        )
        rows.append(
            {
                "name": str(name),
                "mentions": int(len(group)),
                "countries": countries,
                "scope": scope_top[0] if scope_top else "",
                "divisions": divisions,
                "domains": domains,
                "sample_titles": sample_titles,
            }
        )
    rows.sort(key=lambda r: (-r["mentions"], r["name"]))
    return rows


def write_context_csv(
    rows: list[dict[str, Any]], path: pathlib.Path | str = REGULATOR_CONTEXT_CSV
) -> None:
    """Write the context records to a reproducible debug CSV.

    The list-valued fields (``countries``, ``divisions``, ``domains``,
    ``sample_titles``) are stored as JSON strings so they round-trip cleanly.
    """
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CONTEXT_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "regulator_name": row["name"],
                    "mentions": row["mentions"],
                    "countries": json.dumps(row["countries"], ensure_ascii=False),
                    "scope": row["scope"],
                    "divisions": json.dumps(row["divisions"], ensure_ascii=False),
                    "domains": json.dumps(row["domains"], ensure_ascii=False),
                    "sample_titles": json.dumps(
                        row["sample_titles"], ensure_ascii=False
                    ),
                }
            )


def read_context_csv(path: pathlib.Path | str = REGULATOR_CONTEXT_CSV) -> list[dict[str, Any]]:
    """Read a context CSV back into records, restoring the JSON list fields.

    Uses ``keep_default_na=False, na_values=[]`` so a regulator literally named
    ``"NA"`` survives the round-trip rather than becoming a pandas NaN token.
    """
    frame = pd.read_csv(path, keep_default_na=False, na_values=[])
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        records.append(
            {
                "name": row["regulator_name"],
                "mentions": int(row["mentions"]),
                "countries": json.loads(row["countries"]),
                "scope": row["scope"],
                "divisions": json.loads(row["divisions"]),
                "domains": json.loads(row["domains"]),
                "sample_titles": json.loads(row["sample_titles"]),
            }
        )
    return records


# ===========================================================================
# PART B — deterministic chunking + request builder (pure)
# ===========================================================================

def chunk_records(
    records: list[dict[str, Any]], size: int = REGULATOR_CHUNK_SIZE
) -> list[list[dict[str, Any]]]:
    """Split ``records`` into contiguous groups of ``size`` (last is remainder)."""
    return [records[i : i + size] for i in range(0, len(records), size)]


def build_request_line(chunk: list[dict[str, Any]], idx: int) -> dict[str, Any]:
    """Build one Batch request line for a chunk: ``custom_id = chunk-{idx:05d}``."""
    return {
        "custom_id": f"chunk-{idx:05d}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(chunk)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
    }


def write_request_file(
    records: list[dict[str, Any]], path: pathlib.Path | str, size: int
) -> int:
    """Write one Batch request line per chunk to ``path``.  Returns the line count."""
    chunks = chunk_records(records, size)
    with open(path, "w", encoding="utf-8") as fh:
        for i, chunk in enumerate(chunks):
            fh.write(json.dumps(build_request_line(chunk, i), ensure_ascii=False) + "\n")
    return len(chunks)


def chunk_map(records: list[dict[str, Any]], size: int) -> dict[str, list[str]]:
    """Map each ``custom_id`` to the exact list of names sent in that chunk."""
    return {
        f"chunk-{i:05d}": [r["name"] for r in chunk]
        for i, chunk in enumerate(chunk_records(records, size))
    }


# ===========================================================================
# Response parser + schema validation (pure)
# ===========================================================================

def _valid_result(obj: Any) -> bool:
    """Result is valid iff it echoes a ``name``, has a non-empty string
    ``canonical_name``, and a real ``bool`` ``is_regulator``."""
    return (
        isinstance(obj, dict)
        and isinstance(obj.get("name"), str)
        and isinstance(obj.get("canonical_name"), str)
        and obj.get("canonical_name") != ""
        and isinstance(obj.get("is_regulator"), bool)
    )


def parse_and_validate(
    content: str, expected_names: list[str]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse a model response into validated results, returning ``(resolved, missing)``.

    ``resolved`` maps each echoed ``name`` (that was sent) to a validated
    ``{name, canonical_name, is_regulator}`` dict.  ``missing`` lists the sent
    names that were NOT validly returned (short, malformed JSON, bad
    ``is_regulator`` type, empty ``canonical_name``, or simply absent) — these
    are retried / fall back.  Order of ``missing`` follows ``expected_names``.
    """
    expected_set = set(expected_names)
    resolved: dict[str, dict[str, Any]] = {}

    try:
        payload = json.loads(content)
        objects = payload.get(JSON_MODE_KEY) if isinstance(payload, dict) else None
    except (json.JSONDecodeError, TypeError):
        objects = None

    if isinstance(objects, list):
        for obj in objects:
            if not _valid_result(obj):
                continue
            name = obj["name"]
            if name in expected_set and name not in resolved:
                resolved[name] = {
                    "name": name,
                    "canonical_name": obj["canonical_name"],
                    "is_regulator": obj["is_regulator"],
                }

    missing = [n for n in expected_names if n not in resolved]
    return resolved, missing


def extract_output_line(line: str) -> tuple[str | None, str, bool]:
    """Extract ``(custom_id, message_content, errored)`` from a Batch output line.

    ``errored`` is ``True`` when the line represents a *failed* request rather
    than a normal completion: a non-null top-level ``error`` (whose ``response``
    is typically ``null``), or a ``response.status_code`` other than 200.  Such a
    request produced no usable content, so the caller both COUNTS it as a batch
    error and routes its names through the synchronous retry path.

    Returns ``(custom_id, "", False)`` when the line is merely malformed JSON or
    a completion with no usable content — distinct from an explicit error status
    so a clean-but-empty chunk is not miscounted.
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


def canonicalize_sync(client: Any, records: list[dict[str, Any]]) -> str:
    """One synchronous chat.completions call canonicalizing ``records``; returns content."""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(records)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return _chat_content(response)


def _fallback_result(name: str) -> dict[str, Any]:
    """Fall back an unresolved name conservatively: keep the raw name, assume
    it IS a regulator (never silently drop a name on uncertainty)."""
    return {"name": name, "canonical_name": name, "is_regulator": True}


# ===========================================================================
# detect -> retry -> bounded fallback (orchestration over the sync path)
# ===========================================================================

def resolve_with_retry(
    unresolved: list[dict[str, Any]],
    client: Any,
    *,
    max_retries: int = MAX_RETRIES,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Canonicalize ``unresolved`` records synchronously, retrying the unresolved.

    Up to ``max_retries`` re-sends (each carrying only the still-unresolved
    records); any name still unresolved after that falls back conservatively to
    ``canonical_name = raw name, is_regulator = True``.  Returns
    ``(resolved, fallback_count)`` where ``resolved`` covers every input name.
    """
    by_name = {r["name"]: r for r in unresolved}
    resolved: dict[str, dict[str, Any]] = {}
    pending = list(unresolved)

    attempts = max_retries + 1  # one initial attempt plus the retries
    for _ in range(attempts):
        if not pending:
            break
        content = canonicalize_sync(client, pending)
        names = [r["name"] for r in pending]
        got, missing = parse_and_validate(content, names)
        resolved.update(got)
        pending = [by_name[n] for n in missing]

    fallback_count = len(pending)
    for record in pending:
        resolved[record["name"]] = _fallback_result(record["name"])

    if fallback_count:
        logger.warning(
            "%d regulator names fell back to (raw name, is_regulator=True) "
            "after %d retries.",
            fallback_count,
            max_retries,
        )
    return resolved, fallback_count


# ===========================================================================
# Incremental cache + input hash + sidecar + merge (pure / IO helpers)
# ===========================================================================

def _read_cached_names(canonical_csv: pathlib.Path | str) -> set[str]:
    """Return the set of names already present in ``canonical_csv`` (empty if absent).

    Uses ``keep_default_na=False, na_values=[]`` so a regulator literally named
    ``"NA"`` is treated as a real, already-cached value.
    """
    path = pathlib.Path(canonical_csv)
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as fh:
        return {
            row["regulator_name"]
            for row in csv.DictReader(fh)
            if (row.get("regulator_name") or "") != ""
        }


def records_to_classify(
    records: list[dict[str, Any]], canonical_csv: pathlib.Path | str
) -> list[dict[str, Any]]:
    """Set-difference: records whose name is absent from the cache (order preserved)."""
    cached = _read_cached_names(canonical_csv)
    return [r for r in records if r["name"] not in cached]


def input_hash(names: list[str]) -> str:
    """SHA-256 over the distinct-name SET (order-invariant, content-sensitive)."""
    payload = "\n".join(sorted(set(names)))
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
    results: dict[str, dict[str, Any]],
    context_by_name: dict[str, dict[str, Any]],
    canonical_csv: pathlib.Path | str = REGULATOR_CANONICAL_CSV,
) -> int:
    """Append new canonicalization rows into ``canonical_csv`` (create with header).

    Columns: ``regulator_name, canonical_regulator, is_regulator, mentions``
    (``mentions`` pulled from the per-name context).  Rows whose name is already
    cached are skipped (idempotent merge).  Returns the number of rows written.
    """
    path = pathlib.Path(canonical_csv)
    cached = _read_cached_names(path)
    write_header = not path.exists()
    written = 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CANONICAL_HEADER)
        if write_header:
            writer.writeheader()
        # Every value in `results` is shaped {name, canonical_name, is_regulator}
        # (produced by parse_and_validate or _fallback_result), so the accesses
        # below are always safe.
        for name, result in results.items():
            if name in cached:
                continue
            context = context_by_name.get(name, {})
            writer.writerow(
                {
                    "regulator_name": name,
                    "canonical_regulator": result["canonical_name"],
                    "is_regulator": result["is_regulator"],
                    "mentions": int(context.get("mentions", 0)),
                }
            )
            written += 1
    return written


# ===========================================================================
# Batch output collection: parse every line, retry/fallback unresolved chunks
# ===========================================================================

def collect_results(
    output_text: str,
    expected: dict[str, list[str]],
    context_by_name: dict[str, dict[str, Any]],
    client: Any,
    *,
    max_retries: int = MAX_RETRIES,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Parse batch output, reconcile per chunk, retry+fallback the unresolved.

    ``expected`` maps ``custom_id -> names sent`` so each output line is
    validated against the exact chunk it answers.  Any short / malformed chunk —
    and the specific missing names within an otherwise-valid chunk — are
    collected and re-canonicalized synchronously (``resolve_with_retry``), using
    each name's context record.

    A line that signals a *failed* request (per ``extract_output_line``) is
    COUNTED in ``batch_errors`` and its names are still routed through the retry
    path so they are never lost.  When ``batch_errors`` is nonzero a ``WARNING``
    is logged.

    Returns ``(all_results, total_fallback_count, batch_errors)``.
    """
    all_results: dict[str, dict[str, Any]] = {}
    unresolved_names: list[str] = []
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
            unresolved_names.extend(sent)  # retry every name in the failed chunk
            continue
        resolved, missing = parse_and_validate(content, sent)
        all_results.update(resolved)
        unresolved_names.extend(missing)

    # Chunks with no output line at all are entirely unresolved.
    for custom_id, sent in expected.items():
        if custom_id not in seen_ids:
            unresolved_names.extend(sent)

    if batch_errors:
        logger.warning(
            "%d batch requests returned an error status; their regulator names "
            "were retried synchronously.",
            batch_errors,
        )

    fallback_total = 0
    if unresolved_names:
        # De-dup while preserving order; rebuild context records for the retry.
        seen: set[str] = set()
        retry_records: list[dict[str, Any]] = []
        for name in unresolved_names:
            if name in seen:
                continue
            seen.add(name)
            retry_records.append(context_by_name.get(name, {"name": name}))
        retry_resolved, fallback_total = resolve_with_retry(
            retry_records, client, max_retries=max_retries
        )
        all_results.update(retry_resolved)

    return all_results, fallback_total, batch_errors


# ===========================================================================
# Batch submit / resume / poll orchestration (network — uses the client seam)
# ===========================================================================

def _submit_batch(
    client: Any,
    *,
    requests_path: pathlib.Path,
    sidecar_path: pathlib.Path,
    names: list[str],
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
            "input_sha256": input_hash(names),
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
    client: Any,
    file_id: str,
    *,
    local_copy: pathlib.Path | str | None = REGULATOR_BATCH_OUTPUT_JSONL,
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
    records: list[dict[str, Any]],
    requests_path: pathlib.Path | str,
    sidecar_path: pathlib.Path | str,
    canonical_csv: pathlib.Path | str,
    chunk_size: int = REGULATOR_CHUNK_SIZE,
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
    canonical_csv = pathlib.Path(canonical_csv)

    context_by_name = {r["name"]: r for r in records}
    todo = records_to_classify(records, canonical_csv)
    if not todo:
        print("regulator_canonical cache is complete — no batch submitted.", flush=True)
        return {"submitted": False, "classified": 0, "fallback": 0, "batch_errors": 0}

    todo_names = [r["name"] for r in todo]
    current_hash = input_hash(todo_names)
    sidecar = read_sidecar(sidecar_path)

    resumable = (
        sidecar is not None
        and sidecar.get("input_sha256") == current_hash
        and sidecar.get("model") == OPENAI_MODEL
    )
    if resumable:
        # Resume the in-flight batch — do NOT re-upload or create a new one.
        batch_id = sidecar["batch_id"]
        print(f"resuming in-flight batch {batch_id} ({len(todo):,} names).", flush=True)
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
            names=todo_names,
            row_count=row_count,
        )
        print(f"submitted batch {batch_id} ({len(todo):,} names, {row_count} chunks).",
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

    # A completed batch can carry a null output_file_id (everything errored).
    # Don't call files.content(None) — rely on the error-file path + missing-line
    # retry instead.
    output_file_id = getattr(batch, "output_file_id", None)
    if output_file_id is None:
        print(f"WARNING: batch {batch_id} completed with no output file; "
              f"all chunks will be retried synchronously.", flush=True)
        output_text = ""
    else:
        output_text = _fetch_output_text(client, output_file_id)

    # Requests that never executed land in the error file, not the output file.
    # Count them so a partially-errored batch is not silently treated as clean;
    # their chunks still flow through the missing-line retry below.
    error_file_id = getattr(batch, "error_file_id", None)
    error_file_count = 0
    if error_file_id is not None:
        error_text = _fetch_output_text(client, error_file_id, local_copy=None)
        error_file_count = sum(1 for ln in error_text.splitlines() if ln.strip())
        if error_file_count:
            logger.warning(
                "%d batch requests never ran (error_file_id=%s); their regulator "
                "names were retried synchronously.",
                error_file_count, error_file_id,
            )
            print(f"WARNING: {error_file_count:,} batch requests landed in the "
                  f"error file; their names will be retried synchronously.",
                  flush=True)

    expected = chunk_map(todo, chunk_size)
    results, fallback, output_errors = collect_results(
        output_text, expected, context_by_name, client, max_retries=max_retries
    )
    batch_errors = output_errors + error_file_count

    merged = merge_into_cache(results, context_by_name, canonical_csv)
    clear_sidecar(sidecar_path)  # only after a successful merge

    if fallback:
        print(f"WARNING: {fallback:,} names fell back to (raw, is_regulator=True) "
              f"after {max_retries} retries.", flush=True)
    print(f"merged {merged:,} new canonicalizations into {canonical_csv}.", flush=True)
    return {
        "submitted": True,
        "classified": merged,
        "fallback": fallback,
        "batch_errors": batch_errors,
    }


# ===========================================================================
# --sample N synchronous path
# ===========================================================================

def run_sample(
    client: Any,
    records: list[dict[str, Any]],
    *,
    max_retries: int = MAX_RETRIES,
) -> dict[str, dict[str, Any]]:
    """Canonicalize ``records`` synchronously, print the result, write NO cache."""
    resolved, fallback = resolve_with_retry(records, client, max_retries=max_retries)
    for record in records:
        result = resolved[record["name"]]
        flag = "regulator" if result["is_regulator"] else "NON-regulator"
        print(f"  {record['name']!r:40s} -> {result['canonical_name']:40s} | {flag}",
              flush=True)
    if fallback:
        print(f"({fallback} of {len(records)} fell back to raw name)", flush=True)
    return resolved


# ===========================================================================
# --sync-full: sequential synchronous full run (no Batch API)
# ===========================================================================

def run_sync_full(
    client: Any = None,
    *,
    context_csv: pathlib.Path | str = REGULATOR_CONTEXT_CSV,
    canonical_csv: pathlib.Path | str = REGULATOR_CANONICAL_CSV,
    chunk_size: int = REGULATOR_CHUNK_SIZE,
    max_retries: int = MAX_RETRIES,
    sleep_between_chunks: float = 0.3,
    workers: int = 1,
) -> dict[str, Any]:
    """Classify every distinct regulator name via synchronous chat calls.

    Writes the same ``canonical_csv`` cache as the batch path.  Use when the
    OpenAI Batch endpoint is queue-stalled.

    Checkpoints after every chunk (``merge_into_cache`` is idempotent), so a
    partial run can be resumed by re-running ``--sync-full``.

    ``workers=1`` (default): sequential path — chunks are processed one at a
    time with ``sleep_between_chunks`` pacing between them.

    ``workers>1``: concurrent path — chunks are dispatched to a
    ``ThreadPoolExecutor`` with ``max_workers=workers``.  The OpenAI client
    is thread-safe and shared.  All cache writes happen on the MAIN thread as
    futures complete (``as_completed``), keeping ``merge_into_cache`` calls
    single-threaded.  ``sleep_between_chunks`` is NOT used in the concurrent
    path; the pool size bounds the in-flight request rate.

    Returns a summary dict with keys:
      ``total_names``  — distinct names in the source (context CSV or parquet).
      ``classified``   — net new rows written to the cache this run.
      ``fallback_count`` — names that fell back to (raw name, is_regulator=True).
      ``already_cached`` — names skipped because they were already in the cache.
    """
    client = client or make_client()
    canonical_csv = pathlib.Path(canonical_csv)
    context_csv = pathlib.Path(context_csv)

    # --- 1. Load context records -------------------------------------------
    if context_csv.exists():
        records = read_context_csv(context_csv)
    else:
        records = build_context(load_regulator_frame())

    context_by_name = {r["name"]: r for r in records}
    total_names = len(records)

    # --- 2. Resumability: skip already-cached names -------------------------
    todo = records_to_classify(records, canonical_csv)
    already_cached = total_names - len(todo)

    if not todo:
        logger.info(
            "sync-full: all %d regulator names already cached — nothing to do.",
            total_names,
        )
        return {
            "total_names": total_names,
            "classified": 0,
            "fallback_count": 0,
            "already_cached": already_cached,
        }

    logger.info(
        "sync-full: %d names to classify (%d already cached), workers=%d.",
        len(todo), already_cached, workers,
    )

    chunks = chunk_records(todo, chunk_size)
    n_chunks = len(chunks)
    classified_total = 0
    pending: list[dict[str, Any]] = []

    # Inner helper: classify one chunk, return (resolved, missing_records).
    # Intentionally does NOT touch the cache or any shared state so it is safe
    # to call from worker threads.
    def _classify_chunk(chunk: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        names = [r["name"] for r in chunk]
        try:
            content = canonicalize_sync(client, chunk)
            resolved, missing_names = parse_and_validate(content, names)
            missing_records = [context_by_name.get(n, {"name": n}) for n in missing_names]
            return resolved, missing_records
        except Exception as exc:  # noqa: BLE001 — never let one bad call kill the run
            logger.warning(
                "sync-full: chunk raised an exception (%s); "
                "all %d names queued for retry.",
                exc, len(chunk),
            )
            return {}, list(chunk)

    if workers <= 1:
        # --- 3a. Sequential path (original behavior, unchanged) -------------
        for i, chunk in enumerate(chunks):
            resolved, missing_records = _classify_chunk(chunk)
            written = merge_into_cache(resolved, context_by_name, canonical_csv)
            classified_total += written
            pending.extend(missing_records)

            if sleep_between_chunks > 0:
                time.sleep(sleep_between_chunks)

            if (i + 1) % 25 == 0:
                logger.info(
                    "sync-full: chunk %d/%d processed, %d names cached so far.",
                    i + 1, n_chunks, classified_total,
                )
    else:
        # --- 3b. Concurrent path: workers submit chunks, main thread merges --
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_chunk = {
                executor.submit(_classify_chunk, chunk): chunk
                for chunk in chunks
            }
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_chunk):
                resolved, missing_records = future.result()
                # Cache write stays on the main thread — single-threaded and safe.
                written = merge_into_cache(resolved, context_by_name, canonical_csv)
                classified_total += written
                pending.extend(missing_records)
                completed_count += 1
                if completed_count % 25 == 0:
                    logger.info(
                        "sync-full: %d/%d chunks done, %d names cached so far.",
                        completed_count, n_chunks, classified_total,
                    )

    # --- 4. Retry / fallback pending names ----------------------------------
    if pending:
        # De-dup while preserving first-seen order (a name can land in pending
        # from both a missing parse result and a chunk exception on retry).
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for r in pending:
            if r["name"] not in seen:
                seen.add(r["name"])
                deduped.append(r)

        retry_resolved, fallback_count = resolve_with_retry(
            deduped, client, max_retries=max_retries
        )
        written = merge_into_cache(retry_resolved, context_by_name, canonical_csv)
        classified_total += written
        fallback_total = fallback_count
    else:
        fallback_total = 0

    logger.info(
        "sync-full complete: %d classified, %d fallbacks, %d already cached.",
        classified_total, fallback_total, already_cached,
    )
    return {
        "total_names": total_names,
        "classified": classified_total,
        "fallback_count": fallback_total,
        "already_cached": already_cached,
    }


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
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=6, timeout=60.0)


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI parser: ``--sample N`` or ``--sync-full`` select synchronous paths."""
    parser = argparse.ArgumentParser(
        description="Deduplicate raw regulator_name values into canonical English "
        "names + an is_regulator flag via the OpenAI Batch API (or a synchronous "
        "sample with --sample, or a full synchronous run with --sync-full)."
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Canonicalize N names synchronously (no batch, no cache write) "
        "for prompt iteration.",
    )
    parser.add_argument(
        "--sync-full",
        action="store_true",
        default=False,
        help="Classify every distinct regulator name via sequential synchronous "
        "chat calls (no Batch API).  Checkpoints after each chunk for "
        "resumability.  Use when the Batch endpoint is queue-stalled.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of concurrent worker threads for --sync-full (default: 1 = "
        "sequential).  With N>1 chunks are dispatched to a ThreadPoolExecutor; "
        "cache writes always happen on the main thread.  sleep_between_chunks "
        "is not used in the concurrent path.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.sync_full:
        # --sync-full: read context CSV if it exists (fast), otherwise build
        # from parquet.  The function handles both paths internally.
        if not REGULATOR_CONTEXT_CSV.exists() and not ANNOTATIONS_PARQUET.exists():
            print(
                f"ERROR: neither {REGULATOR_CONTEXT_CSV} nor {ANNOTATIONS_PARQUET} "
                f"found.  Run tools/pull_full.py first.",
                flush=True,
            )
            sys.exit(1)
        print("--sync-full: classifying all regulator names synchronously ...",
              flush=True)
        summary = run_sync_full(workers=args.workers)
        print(
            f"sync-full done: {summary['classified']:,} classified, "
            f"{summary['fallback_count']:,} fallbacks, "
            f"{summary['already_cached']:,} already cached "
            f"(total {summary['total_names']:,}).",
            flush=True,
        )
        return

    if not ANNOTATIONS_PARQUET.exists():
        print(
            f"ERROR: {ANNOTATIONS_PARQUET} not found. Run tools/pull_full.py first.",
            flush=True,
        )
        sys.exit(1)

    print(f"loading regulator context from {ANNOTATIONS_PARQUET} ...", flush=True)
    df = load_regulator_frame()
    records = build_context(df)
    write_context_csv(records, REGULATOR_CONTEXT_CSV)
    print(f"wrote {REGULATOR_CONTEXT_CSV} ({len(records):,} distinct regulator names).",
          flush=True)

    client = make_client()

    if args.sample is not None:
        sample = records[: args.sample]
        print(f"--sample: canonicalizing {len(sample)} names synchronously\n", flush=True)
        run_sample(client, sample, max_retries=MAX_RETRIES)
        return

    run_full(
        client,
        records=records,
        requests_path=REGULATOR_BATCH_REQUESTS_JSONL,
        sidecar_path=REGULATOR_BATCH_STATE_JSON,
        canonical_csv=REGULATOR_CANONICAL_CSV,
        chunk_size=REGULATOR_CHUNK_SIZE,
        max_retries=MAX_RETRIES,
        poll_interval=DEFAULT_POLL_INTERVAL,
    )


if __name__ == "__main__":
    main()
