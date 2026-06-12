"""Extract entity and tag mention counts from the annotations JSONL snapshot.

Streams the JSONL once (memory-bounded) and counts per-occurrence occurrences
of each entity / tag string.  Writes two CSVs:

  data/entity_mentions.csv  — columns: entity, count
  data/tag_mentions.csv     — columns: tag, count

Both files are sorted by count descending, then term ascending (lexical).
This deterministic order makes downstream LLM-chunking reproducible.

No API key required — this tool is a pure offline computation over the local
snapshot produced by tools/pull_full.py.

Run:
    .venv/bin/python tools/extract_terms.py
"""
from __future__ import annotations

import csv
import os
import pathlib
import sys
from collections import Counter
from typing import Iterable

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def count_terms(records: Iterable[dict]) -> tuple[Counter, Counter]:
    """Count per-occurrence entity and tag mentions across annotation records.

    Iterates each record, reads ``output_data.metadata.entities`` and
    ``output_data.metadata.tags`` (each a flat ``list[str]``), trims
    whitespace, and drops empty strings.  Missing, ``None``, or non-list
    values are silently skipped.

    Parameters
    ----------
    records:
        Iterable of raw annotation envelope dicts (as yielded by
        ``carver_showcase.ingest.load_snapshot``).

    Returns
    -------
    tuple[Counter, Counter]
        ``(entity_counter, tag_counter)`` — per-occurrence counts.
    """
    entity_ctr: Counter = Counter()
    tag_ctr: Counter = Counter()

    for record in records:
        metadata = (
            record
            .get("output_data", {})
            .get("metadata", {})
        )
        if not isinstance(metadata, dict):
            continue

        entities = metadata.get("entities")
        if isinstance(entities, list):
            for raw in entities:
                term = raw.strip() if isinstance(raw, str) else ""
                if term:
                    entity_ctr[term] += 1

        tags = metadata.get("tags")
        if isinstance(tags, list):
            for raw in tags:
                term = raw.strip() if isinstance(raw, str) else ""
                if term:
                    tag_ctr[term] += 1

    return entity_ctr, tag_ctr


def sorted_rows(counter: Counter) -> list[tuple[str, int]]:
    """Return counter entries sorted by count descending, then term ascending.

    The deterministic tie-breaking order (term ascending) makes the output
    reproducible for downstream LLM chunking.

    Parameters
    ----------
    counter:
        A ``collections.Counter`` mapping term strings to integer counts.

    Returns
    -------
    list[tuple[str, int]]
        List of ``(term, count)`` pairs in the specified order.
    """
    return sorted(counter.items(), key=lambda x: (-x[1], x[0]))


def write_csv(
    rows: list[tuple[str, int]],
    path: pathlib.Path,
    *,
    term_col: str,
) -> None:
    """Write sorted (term, count) rows to a CSV file.

    Parameters
    ----------
    rows:
        Ordered list of ``(term, count)`` pairs as returned by
        :func:`sorted_rows`.
    path:
        Destination file path.  Parent directory must already exist.
    term_col:
        Header name for the term column (``"entity"`` or ``"tag"``).
    """
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([term_col, "count"])
        writer.writerows(rows)


def main() -> None:
    from carver_showcase.config import (
        ANNOTATIONS_JSONL,
        ENTITY_MENTIONS_CSV,
        TAG_MENTIONS_CSV,
    )
    from carver_showcase.ingest import load_snapshot

    if not ANNOTATIONS_JSONL.exists():
        print(
            f"ERROR: snapshot not found at {ANNOTATIONS_JSONL}\n"
            "Run tools/pull_full.py first.",
            flush=True,
        )
        sys.exit(1)

    print(f"streaming {ANNOTATIONS_JSONL} ...", flush=True)
    entity_ctr, tag_ctr = count_terms(load_snapshot(ANNOTATIONS_JSONL))

    entity_rows = sorted_rows(entity_ctr)
    tag_rows = sorted_rows(tag_ctr)

    write_csv(entity_rows, ENTITY_MENTIONS_CSV, term_col="entity")
    print(
        f"wrote {ENTITY_MENTIONS_CSV}  ({len(entity_rows):,} distinct entities, "
        f"{sum(entity_ctr.values()):,} total mentions)",
        flush=True,
    )

    write_csv(tag_rows, TAG_MENTIONS_CSV, term_col="tag")
    print(
        f"wrote {TAG_MENTIONS_CSV}  ({len(tag_rows):,} distinct tags, "
        f"{sum(tag_ctr.values()):,} total mentions)",
        flush=True,
    )


if __name__ == "__main__":
    main()
