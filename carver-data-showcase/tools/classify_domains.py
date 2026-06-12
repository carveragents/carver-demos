"""Classify every monitored institution into a two-level domain taxonomy.

Stage 1 — context (reproducible LLM input):
    Fetch /api/v1/feeds/topics?details=true; write one row per topic to
    TOPIC_DOMAIN_CONTEXT_CSV with columns:
        topic_id, name, sectors, industries, sub_entity_type, entity_type,
        scope, description
    List-valued fields are coerced to "; "-joined strings; None -> "".

Stage 2 — classify:
    Read the context CSV; chunk into DOMAIN_CHUNK_SIZE; for each chunk call
    gpt-4o-mini (temp 0, json_object mode) to assign EXACTLY ONE leaf from the
    fixed INSTITUTION_DOMAIN_TAXONOMY (defined in carver_showcase/config.py).
    Any leaf not in INSTITUTION_DOMAIN_LEAVES is coerced to DOMAIN_FALLBACK_LEAF.
    Writes TOPIC_DOMAINS_CSV with columns:
        topic_id, sub_domain, top_level, secondary

This is the ONLY module in the repo (besides tools/classify_entities.py and
tools/canonicalize_regulators.py) that imports openai and reads OPENAI_API_KEY.
All network calls sit behind an injectable client argument (make_client / a
supplied client) so the test-suite drives a stub and never constructs a real
client or needs a key.

Run:
    .venv/bin/python tools/classify_domains.py --context-only
    .venv/bin/python tools/classify_domains.py --sample 10
    .venv/bin/python tools/classify_domains.py
    .venv/bin/python tools/classify_domains.py --workers 4
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from carver_showcase.config import (  # noqa: E402
    CARVER_BASE_URL_DEFAULT,
    DOMAIN_CHUNK_SIZE,
    DOMAIN_FALLBACK_LEAF,
    DOMAIN_MODEL,
    INSTITUTION_DOMAIN_LEAVES,
    INSTITUTION_DOMAIN_PARENT,
    INSTITUTION_DOMAIN_TAXONOMY,
    MAX_RETRIES,
    TOPIC_DOMAIN_CONTEXT_CSV,
    TOPIC_DOMAINS_CSV,
)

# ---------------------------------------------------------------------------
# Output headers
# ---------------------------------------------------------------------------

CONTEXT_HEADER = [
    "topic_id",
    "name",
    "sectors",
    "industries",
    "sub_entity_type",
    "entity_type",
    "scope",
    "description",
]

DOMAINS_HEADER = ["topic_id", "sub_domain", "top_level", "secondary"]

# Fields to pull from /feeds/topics?details=true
_TOPIC_DETAIL_ATTRS = [
    "name",
    "sectors",
    "industries",
    "sub_entity_type",
    "entity_type",
    "scope",
    "description",
]


# ---------------------------------------------------------------------------
# System prompt (built once from config so it always matches the taxonomy)
# ---------------------------------------------------------------------------

def build_system_prompt() -> str:
    """Render the classification system prompt from INSTITUTION_DOMAIN_TAXONOMY.

    The taxonomy is rendered inline so the prompt always reflects config and the
    LLM sees the parent/leaf hierarchy to guide its choice.
    """
    taxonomy_lines = []
    for top_level, leaves in INSTITUTION_DOMAIN_TAXONOMY.items():
        taxonomy_lines.append(f"  {top_level}:")
        for leaf in leaves:
            taxonomy_lines.append(f"    - {leaf}")
    taxonomy_block = "\n".join(taxonomy_lines)

    leaf_list = ", ".join(f'"{leaf}"' for leaf in INSTITUTION_DOMAIN_LEAVES)

    return (
        "You are classifying monitored regulatory, supervisory and government "
        "institutions into a fixed two-level domain taxonomy.\n\n"
        "For EACH institution in the input, choose EXACTLY ONE sub-domain leaf from "
        "the closed list below. Reproduce the leaf string VERBATIM (exact spelling, "
        "capitalisation, and punctuation). If an institution fits none of the specific "
        f'sub-domains, use the fallback: "{DOMAIN_FALLBACK_LEAF}".\n\n'
        "You may also provide an optional 'secondary' leaf (a second-best fit, also "
        "verbatim from the same closed list) when a strong secondary classification "
        "exists. Leave it as an empty string if there is no clear second domain.\n\n"
        f"Taxonomy (top-level: leaves):\n{taxonomy_block}\n\n"
        f"Closed leaf set: {leaf_list}\n\n"
        "CLASSIFICATION GUIDANCE — read carefully:\n"
        "1. Classify by the institution's PRIMARY SUBJECT-MATTER DOMAIN — the sector "
        "it regulates, supervises, serves, or represents — regardless of whether it "
        "is a regulator, supervisor, central bank, ministry, department, agency, "
        "industry association, or standards body. For example an 'Association of "
        "Banks' or a 'Banking Ombudsman' belongs to 'Banking & Central Banking', not "
        "to a government catch-all.\n"
        "2. A body that operates ACROSS MULTIPLE FINANCIAL sub-sectors — e.g. a "
        "CENTRAL BANK or national/reserve bank, an integrated/'twin-peaks' financial "
        "supervisor, a state Department/Division of Financial Regulation, an "
        "anti-money-laundering / financial-intelligence authority, a deposit-insurer, "
        "a development or multilateral bank, a securities-and-futures commission, or "
        "a financial-stability body — is ALWAYS Finance. Pick the single most "
        "representative Finance leaf (default 'Banking & Central Banking' when no one "
        "finance sub-sector dominates). NEVER place such a body in the fallback "
        "merely because it spans several financial sectors. A central bank is NEVER "
        "'Other Government'.\n"
        "3. Many bodies belong to a NON-finance specific domain — route them there "
        "rather than to the fallback. Use the listed domains for: environmental "
        "protection, climate, energy, utilities, water, mining, nuclear/radiation → "
        "'Environment & Energy'; public health, food & drug, medicines, medical "
        "devices → 'Healthcare & Life Sciences'; telecoms, broadcasting, spectrum, "
        "postal, data protection, cybersecurity → 'Technology'; competition/antitrust, "
        "consumer protection, intellectual property, company/business registration, "
        "professional/accounting bodies, trade & customs → 'Trade, Corporate & "
        "Professional'; courts, prosecutors, police, attorneys-general, anti-"
        "corruption, emergency management, alcohol/firearms/vice control → 'Justice & "
        "Public Safety'; aviation, maritime, rail, roads & motor vehicles, housing, "
        "construction, public works → 'Transport & Infrastructure'; labour, "
        "employment, social security, welfare, education, vocational skills → "
        "'Education, Labour & Social'; scientific research, space, AI, metrology/"
        "standards, statistics, meteorology/weather → 'Science, Research & "
        "Standards'.\n"
        f'4. Use the fallback "{DOMAIN_FALLBACK_LEAF}" ONLY for genuine general-'
        "government bodies that fit NO specific domain above — e.g. legislatures / "
        "parliaments, whole-of-government ministries or cabinets, national / state / "
        "municipal governments and e-government portals, supreme audit institutions, "
        "civil-service / public-administration commissions, foreign-affairs or "
        "diplomatic bodies, and multi-purpose political or economic unions (e.g. the "
        "African Union, ASEAN, APEC, the EU institutions). When a more specific "
        "listed domain clearly fits, ALWAYS prefer it over the fallback.\n"
        "5. Judge each institution INDEPENDENTLY on its own context fields; do not let "
        "the other institutions in the batch influence its classification.\n\n"
        "Input: a JSON array of institution records, each with an 'id' plus context "
        "fields (name, sectors, industries, sub_entity_type, entity_type, scope, "
        "description).\n\n"
        "Respond with strict JSON only, shaped as:\n"
        '{"results": {"<id>": {"sub_domain": "<leaf>", "secondary": "<leaf or empty>"}, ...}}\n'
        "where the keys are the institution ids from the input."
    )


SYSTEM_PROMPT = build_system_prompt()


# ---------------------------------------------------------------------------
# Stage 1 — context builder (pure; no network; unit-testable)
# ---------------------------------------------------------------------------

def _coerce_field(value: Any) -> str:
    """Coerce a topic attribute value to a clean string.

    Rules:
    - None  -> ""
    - list  -> "; ".join(str(v) for v in value)  (consistent delimiter)
    - other -> str(value)
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def build_context_rows(topics: list[dict]) -> list[dict]:
    """Build one context row per topic dict.

    Pure builder — no network calls, fully unit-testable.

    Each row contains: topic_id, name, sectors, industries, sub_entity_type,
    entity_type, scope, description.  List-valued fields are joined with "; ";
    None values become "".
    """
    rows: list[dict] = []
    for topic in topics:
        tid = topic.get("id")
        if not tid:
            continue
        row = {"topic_id": str(tid)}
        for attr in _TOPIC_DETAIL_ATTRS:
            row[attr] = _coerce_field(topic.get(attr))
        rows.append(row)
    return rows


def fetch_topics(base_url: str, api_key: str) -> list[dict]:
    """Fetch all topics from GET /api/v1/feeds/topics?details=true."""
    url = f"{base_url}/api/v1/feeds/topics"
    headers = {"X-API-Key": api_key}
    with httpx.Client(timeout=300) as client:
        r = client.get(url, params={"details": "true"}, headers=headers)
        r.raise_for_status()
    topics = r.json()
    if not isinstance(topics, list):
        raise ValueError(f"Expected a list from {url}, got {type(topics)}")
    return topics


def write_context_csv(rows: list[dict], path: pathlib.Path | str) -> None:
    """Write context rows to CSV (creates parent dir if needed)."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CONTEXT_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def fetch_and_write_context(
    base_url: str = CARVER_BASE_URL_DEFAULT,
    api_key: str | None = None,
    out_path: pathlib.Path | str = TOPIC_DOMAIN_CONTEXT_CSV,
) -> list[dict]:
    """Fetch topics from the API and write the context CSV.

    Returns the context rows so callers can chain directly into classify.
    """
    if api_key is None:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))
        api_key = os.environ["CARVER_API_KEY"]

    print(f"fetching topics from {base_url} ...", flush=True)
    topics = fetch_topics(base_url, api_key)
    print(f"  fetched {len(topics)} institutions", flush=True)

    rows = build_context_rows(topics)
    write_context_csv(rows, out_path)
    print(f"wrote context CSV: {out_path} ({len(rows)} rows)", flush=True)
    return rows


# ---------------------------------------------------------------------------
# Stage 2 — chunking (pure; shared by context and classify paths)
# ---------------------------------------------------------------------------

def chunk_records(rows: list[dict], size: int = DOMAIN_CHUNK_SIZE) -> list[list[dict]]:
    """Split rows into contiguous groups of size (last group is the remainder)."""
    return [rows[i : i + size] for i in range(0, len(rows), size)]


# ---------------------------------------------------------------------------
# Stage 2 — LLM classify (sync + concurrent)
# ---------------------------------------------------------------------------

def _user_message(chunk: list[dict]) -> str:
    """Render the per-chunk user message listing the institutions to classify."""
    records = [
        {
            "id": row.get("topic_id", ""),
            "name": row.get("name", ""),
            "sectors": row.get("sectors", ""),
            "industries": row.get("industries", ""),
            "sub_entity_type": row.get("sub_entity_type", ""),
            "entity_type": row.get("entity_type", ""),
            "scope": row.get("scope", ""),
            "description": row.get("description", ""),
        }
        for row in chunk
    ]
    return (
        f"Classify these {len(records)} institutions. "
        f"Return one entry per id:\n"
        + json.dumps(records, ensure_ascii=False)
    )


def _parse_results(response_obj: Any) -> dict | None:
    """Extract + parse the {'results': {...}} mapping; return the results dict or None.

    Returns the dict at payload["results"] if the response is well-formed JSON with
    a "results" key whose value is a dict, else None.
    """
    try:
        content = response_obj.choices[0].message.content or ""
        payload = json.loads(content)
        results = payload.get("results") if isinstance(payload, dict) else None
    except (AttributeError, IndexError, json.JSONDecodeError, TypeError):
        return None
    return results if isinstance(results, dict) else None


def parse_and_validate(
    response_obj: Any, chunk: list[dict]
) -> dict[str, str]:
    """Parse an LLM response object into a validated id -> leaf mapping.

    - Expects response_obj.choices[0].message.content to be JSON-mode text.
    - Parses the JSON and extracts {"results": {"<id>": {"sub_domain": ..., "secondary": ...}}}.
    - Any leaf NOT in INSTITUTION_DOMAIN_LEAVES (or missing) is coerced to
      DOMAIN_FALLBACK_LEAF.
    - Returns dict keyed by topic_id with values being the validated sub_domain leaf.
    - The secondary leaf is NOT validated here; it is handled by build_domain_rows.

    Returns a plain dict {topic_id: sub_domain_leaf}.
    """
    results = _parse_results(response_obj)
    validated: dict[str, str] = {}
    leaves_set = set(INSTITUTION_DOMAIN_LEAVES)

    if results is not None:
        for row in chunk:
            tid = row["topic_id"]
            entry = results.get(tid)
            if isinstance(entry, dict):
                leaf = entry.get("sub_domain", "")
            else:
                leaf = ""
            if leaf not in leaves_set:
                leaf = DOMAIN_FALLBACK_LEAF
            validated[tid] = leaf
    else:
        # Full fallback: entire response malformed
        for row in chunk:
            validated[row["topic_id"]] = DOMAIN_FALLBACK_LEAF

    return validated


def _extract_secondary(response_obj: Any, chunk: list[dict]) -> dict[str, str]:
    """Extract raw secondary leaves from the response (no validation beyond membership).

    Returns dict {topic_id: secondary_leaf_or_empty}.
    Secondary is left as "" if not in INSTITUTION_DOMAIN_LEAVES.
    """
    leaves_set = set(INSTITUTION_DOMAIN_LEAVES)
    secondary: dict[str, str] = {}
    results = _parse_results(response_obj)

    for row in chunk:
        tid = row["topic_id"]
        entry = results.get(tid) if results is not None else None
        sec = entry.get("secondary", "") if isinstance(entry, dict) else ""
        # Only accept valid leaves or empty string
        secondary[tid] = sec if sec in leaves_set else ""

    return secondary


def build_domain_rows(
    validated: dict[str, str],
    secondary: dict[str, str],
    context_rows: list[dict],
) -> list[dict]:
    """Map validated {id: leaf} + secondary + context rows into the output rows.

    Derives top_level from INSTITUTION_DOMAIN_PARENT (deterministic; never from the LLM).
    Output columns: topic_id, sub_domain, top_level, secondary.
    """
    id_order = [row["topic_id"] for row in context_rows]
    rows: list[dict] = []
    for tid in id_order:
        if tid not in validated:
            continue
        sub_domain = validated[tid]
        top_level = INSTITUTION_DOMAIN_PARENT.get(sub_domain, INSTITUTION_DOMAIN_PARENT[DOMAIN_FALLBACK_LEAF])
        sec = secondary.get(tid, "")
        # Drop secondary when it duplicates the primary sub_domain.
        if sec == sub_domain:
            sec = ""
        rows.append(
            {
                "topic_id": tid,
                "sub_domain": sub_domain,
                "top_level": top_level,
                "secondary": sec,
            }
        )
    return rows


def _classify_chunk_sync(client: Any, chunk: list[dict]) -> Any:
    """Make one synchronous chat.completions call for a chunk; return the raw response."""
    return client.chat.completions.create(
        model=DOMAIN_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_message(chunk)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )


def run_classify(
    client: Any,
    context_rows: list[dict],
    *,
    chunk_size: int = DOMAIN_CHUNK_SIZE,
    sleep_between_chunks: float = 0.3,
    workers: int = 1,
    out_path: pathlib.Path | str = TOPIC_DOMAINS_CSV,
) -> dict[str, Any]:
    """Classify all institutions and write TOPIC_DOMAINS_CSV.

    Sequential path (workers=1): classify one chunk at a time with
    sleep_between_chunks pacing.

    Concurrent path (workers>1): dispatch chunks via ThreadPoolExecutor; the
    shared OpenAI client is thread-safe; all result assembly happens on the
    main thread.  Output rows are sorted to match the original context_rows
    topic_id order so the artifact is deterministic regardless of worker count.

    Returns a summary dict with keys: total, classified, fallback_count.
    """
    out_path = pathlib.Path(out_path)
    chunks = chunk_records(context_rows, chunk_size)
    n_chunks = len(chunks)
    total = len(context_rows)

    # Inner worker: pure classify; no shared-state writes.
    def _process_chunk(chunk: list[dict]) -> tuple[list[dict], int]:
        """Classify one chunk; return (output_rows, fallback_count)."""
        try:
            response = _classify_chunk_sync(client, chunk)
        except Exception as exc:
            logger.warning(
                "classify_domains: chunk of %d raised %s; "
                "all %d institutions fall back to %s.",
                len(chunk), exc, len(chunk), DOMAIN_FALLBACK_LEAF,
            )
            validated = {row["topic_id"]: DOMAIN_FALLBACK_LEAF for row in chunk}
            secondary = {row["topic_id"]: "" for row in chunk}
            rows = build_domain_rows(validated, secondary, chunk)
            return rows, len(chunk)

        validated = parse_and_validate(response, chunk)
        secondary = _extract_secondary(response, chunk)
        rows = build_domain_rows(validated, secondary, chunk)
        fallbacks = sum(1 for v in validated.values() if v == DOMAIN_FALLBACK_LEAF)
        return rows, fallbacks

    all_rows: list[dict] = []
    total_fallbacks = 0

    if workers <= 1:
        for i, chunk in enumerate(chunks):
            rows, fallbacks = _process_chunk(chunk)
            all_rows.extend(rows)
            total_fallbacks += fallbacks

            if sleep_between_chunks > 0:
                time.sleep(sleep_between_chunks)

            if (i + 1) % 10 == 0:
                logger.info(
                    "classify_domains: chunk %d/%d done (%d rows so far).",
                    i + 1, n_chunks, len(all_rows),
                )
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_chunk = {
                executor.submit(_process_chunk, chunk): chunk
                for chunk in chunks
            }
            completed = 0
            for future in concurrent.futures.as_completed(future_to_chunk):
                rows, fallbacks = future.result()
                all_rows.extend(rows)
                total_fallbacks += fallbacks
                completed += 1
                if completed % 10 == 0:
                    logger.info(
                        "classify_domains: %d/%d chunks done.",
                        completed, n_chunks,
                    )

        # Sort to match original context_rows order (worker completion is non-deterministic)
        order_index = {row["topic_id"]: i for i, row in enumerate(context_rows)}
        all_rows.sort(key=lambda r: order_index.get(r["topic_id"], len(context_rows)))

    # Write output CSV (full overwrite)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=DOMAINS_HEADER)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"wrote {out_path} ({len(all_rows)} rows, {total_fallbacks} fallbacks).",
          flush=True)

    return {
        "total": total,
        "classified": len(all_rows),
        "fallback_count": total_fallbacks,
    }


# ---------------------------------------------------------------------------
# Client seam + CLI wiring
# ---------------------------------------------------------------------------

def make_client() -> Any:
    """Construct a real OpenAI client.  The ONLY place a key is read.

    Import-local so tests inject a stub and never call this function.
    """
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=6, timeout=60.0)


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI parser for classify_domains."""
    parser = argparse.ArgumentParser(
        description=(
            "Classify every monitored institution into a two-level domain taxonomy "
            "via gpt-4o-mini. Stage 1 fetches topic context; Stage 2 classifies. "
            "Use --context-only to stop after Stage 1. Use --sample N for a cheap "
            "dry run on N institutions only."
        )
    )
    parser.add_argument(
        "--context-only",
        action="store_true",
        default=False,
        help="Fetch and write the context CSV only (Stage 1); skip classification.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Limit classification to the first N institutions (for a cheap dry run). "
        "Does NOT write TOPIC_DOMAINS_CSV; prints results to stdout.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of concurrent worker threads for classification (default: 1). "
        "With N>1, chunks are dispatched to a ThreadPoolExecutor; the OpenAI client "
        "is thread-safe and shared.",
    )
    parser.add_argument(
        "--sync-full",
        action="store_true",
        default=False,
        help="Run the full sequential classification (equivalent to default; "
        "kept for parity with canonicalize_regulators CLI).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        metavar="URL",
        help=f"Carver API base URL (default: {CARVER_BASE_URL_DEFAULT}).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(ROOT, ".env"))

    base_url = args.base_url or os.environ.get("CARVER_BASE_URL", CARVER_BASE_URL_DEFAULT)

    # --- Stage 1: fetch + write context CSV ---------------------------------
    context_path = pathlib.Path(TOPIC_DOMAIN_CONTEXT_CSV)
    if context_path.exists():
        print(f"reading existing context CSV: {context_path}", flush=True)
        df = pd.read_csv(context_path, keep_default_na=False, na_values=[])
        context_rows = df.to_dict(orient="records")
        print(f"  loaded {len(context_rows)} institutions from cache", flush=True)
    else:
        context_rows = fetch_and_write_context(base_url=base_url)

    if args.context_only:
        print("--context-only: done.", flush=True)
        return

    # --- Stage 2: classify --------------------------------------------------
    sample = args.sample
    if sample is not None:
        classify_rows = context_rows[:sample]
        print(f"--sample {sample}: classifying {len(classify_rows)} institutions ...",
              flush=True)
        client = make_client()
        chunks = chunk_records(classify_rows, DOMAIN_CHUNK_SIZE)
        for chunk in chunks:
            response = _classify_chunk_sync(client, chunk)
            validated = parse_and_validate(response, chunk)
            secondary = _extract_secondary(response, chunk)
            for row in chunk:
                tid = row["topic_id"]
                leaf = validated.get(tid, DOMAIN_FALLBACK_LEAF)
                sec = secondary.get(tid, "")
                top = INSTITUTION_DOMAIN_PARENT.get(leaf, "")
                print(f"  {tid}  {row['name'][:40]:<40s}  -> {leaf}  ({top})"
                      + (f"  | also: {sec}" if sec else ""),
                      flush=True)
        return

    print(
        f"classifying {len(context_rows)} institutions "
        f"(workers={args.workers}) ...",
        flush=True,
    )
    client = make_client()
    summary = run_classify(
        client,
        context_rows,
        chunk_size=DOMAIN_CHUNK_SIZE,
        workers=args.workers,
        out_path=TOPIC_DOMAINS_CSV,
    )
    print(
        f"done: {summary['classified']} classified, "
        f"{summary['fallback_count']} fallbacks "
        f"(total {summary['total']}).",
        flush=True,
    )


if __name__ == "__main__":
    main()
