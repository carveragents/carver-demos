"""Deterministic rollup of entity and tag mention stats.

Reads three input CSVs produced by tools/extract_terms.py and
tools/classify_entities.py, then writes four output files:

  data/entity_type_breakdown.csv   — mentions + distinct entities per type
  data/entity_leaderboard.csv      — alias-merged top-50 entities
  data/tag_leaderboard.csv         — top-50 tags by frequency
  data/term_stats_meta.json        — provenance metadata

No API key required — pure offline computation.

Run:
    .venv/bin/python tools/build_term_stats.py
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys
from typing import Optional

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from carver_showcase.config import (
    ENTITY_LEADERBOARD_TOP_N,
    ENTITY_MENTIONS_CSV,
    ENTITY_TYPE_BREAKDOWN_CSV,
    ENTITY_TYPES,
    ENTITY_TYPES_CSV,
    ENTITY_LEADERBOARD_CSV,
    OPENAI_MODEL,
    TAG_LEADERBOARD_CSV,
    TAG_LEADERBOARD_TOP_N,
    TAG_MENTIONS_CSV,
    TERM_STATS_META_JSON,
)

# Hard cap for leaderboards — callers may pass a smaller top_n, never larger.
_LEADERBOARD_HARD_CAP = 50

# Store count for leaderboard CSVs — how many rows we persist to disk.
# The chart display top-N (ENTITY_LEADERBOARD_TOP_N / TAG_LEADERBOARD_TOP_N) is
# applied later by the chart builders, not here.
LEADERBOARD_STORE_N = 50


# ---------------------------------------------------------------------------
# Canonical-name cleaning (alias merge key)
# ---------------------------------------------------------------------------

def _clean_canonical(name: str) -> str:
    """Return a normalised merge key for *name* (display value is not changed).

    Transformations applied to the KEY only (never to the display string):
    1. Strip a leading ``"U.S. "`` prefix (exactly — includes the trailing space).
    2. Strip surrounding double-quote characters.
    3. Drop a trailing period.
    4. Collapse any run of internal whitespace to a single space and trim.
    5. Casefold.

    Parameters
    ----------
    name:
        Raw canonical_name string from entity_types.csv.

    Returns
    -------
    str
        Normalised key suitable for equality comparisons.
    """
    # Belt-and-suspenders: guard against non-string inputs (e.g. float NaN from
    # a stray pd.read_csv that did not use keep_default_na=False).
    if not isinstance(name, str):
        return ""

    key = name

    # 1. Strip leading "U.S. " (with trailing space — exact prefix only)
    if key.startswith("U.S. "):
        key = key[5:]

    # 2. Strip surrounding double quotes
    if len(key) >= 2 and key[0] == '"' and key[-1] == '"':
        key = key[1:-1]

    # 3. Drop trailing period
    if key.endswith("."):
        key = key[:-1]

    # 4. Collapse internal whitespace and trim
    key = re.sub(r"\s+", " ", key).strip()

    # 5. Casefold
    return key.casefold()


# ---------------------------------------------------------------------------
# Output 1 — Entity type breakdown
# ---------------------------------------------------------------------------

def build_entity_type_breakdown(
    entity_mentions_df: pd.DataFrame,
    entity_types_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-type mention totals and distinct-entity counts.

    Entities present in *entity_mentions_df* but absent from *entity_types_df*
    are assigned to the ``"Other"`` bucket.

    The breakdown is computed INDEPENDENT of any alias merge — every distinct
    entity string counts once.

    Parameters
    ----------
    entity_mentions_df:
        DataFrame with columns ``entity`` (str) and ``count`` (int).
    entity_types_df:
        DataFrame with columns ``entity``, ``type``, ``canonical_name``.

    Returns
    -------
    pd.DataFrame
        Columns: ``type``, ``mentions``, ``distinct_entities``.
        All six ``ENTITY_TYPES`` buckets are present (zero-filled if empty).
        Rows are ordered by ``mentions`` descending.
    """
    # Left-join mentions onto types so unclassified entities are preserved.
    merged = entity_mentions_df.merge(
        entity_types_df[["entity", "type"]],
        on="entity",
        how="left",
    )
    # Fill missing type with "Other"
    merged["type"] = merged["type"].fillna("Other")

    # Group: sum counts, count distinct entity strings
    grouped = (
        merged
        .groupby("type", as_index=False)
        .agg(
            mentions=("count", "sum"),
            distinct_entities=("entity", "nunique"),
        )
    )

    # Ensure all 6 buckets are present (zero-fill missing ones)
    all_types = pd.DataFrame({"type": list(ENTITY_TYPES)})
    result = all_types.merge(grouped, on="type", how="left").fillna(0)
    result["mentions"] = result["mentions"].astype(int)
    result["distinct_entities"] = result["distinct_entities"].astype(int)

    # Sort by mentions descending
    result = result.sort_values("mentions", ascending=False, kind="stable").reset_index(drop=True)
    return result


# ---------------------------------------------------------------------------
# Output 2 — Entity leaderboard (alias-merged)
# ---------------------------------------------------------------------------

def build_entity_leaderboard(
    entity_mentions_df: pd.DataFrame,
    entity_types_df: pd.DataFrame,
    top_n: int = 50,
) -> pd.DataFrame:
    """Build the alias-merged entity leaderboard.

    Entities sharing the same ``_clean_canonical`` key are collapsed into a
    single row.  The display ``canonical_name`` and ``type`` come from the
    highest-mention member; ties are broken by ``canonical_name`` ascending.

    Only entities present in *entity_types_df* appear in the leaderboard.
    Unclassified entities (those missing from *entity_types_df*) are excluded
    — they appear in the breakdown under ``"Other"`` instead.

    Parameters
    ----------
    entity_mentions_df:
        DataFrame with columns ``entity`` (str) and ``count`` (int).
    entity_types_df:
        DataFrame with columns ``entity``, ``type``, ``canonical_name``.
    top_n:
        Maximum rows to return.  Hard-capped at :data:`_LEADERBOARD_HARD_CAP`.

    Returns
    -------
    pd.DataFrame
        Columns: ``canonical_name``, ``type``, ``mentions``.
        Sorted by ``mentions`` descending.
    """
    effective_n = min(top_n, _LEADERBOARD_HARD_CAP)

    # Inner-join: only classified entities appear in the leaderboard
    joined = entity_mentions_df.merge(
        entity_types_df[["entity", "type", "canonical_name"]],
        on="entity",
        how="inner",
    )

    if joined.empty:
        return pd.DataFrame(columns=["canonical_name", "type", "mentions"])

    # Compute merge key
    joined = joined.copy()
    joined["merge_key"] = joined["canonical_name"].apply(_clean_canonical)

    # For each (entity row), we have: merge_key, count, type, canonical_name.
    # Within each merge_key group we need the highest-mention member.
    # Sort so the winner (highest count, then name asc) is first in each group.
    joined_sorted = joined.sort_values(
        ["count", "canonical_name"],
        ascending=[False, True],
        kind="stable",
    )

    # Pick the representative (winner) row per merge_key
    representative = (
        joined_sorted
        .groupby("merge_key", as_index=False)
        .first()[["merge_key", "canonical_name", "type"]]
    )

    # Sum mention counts across all members of each merge group
    group_mentions = (
        joined
        .groupby("merge_key", as_index=False)["count"]
        .sum()
        .rename(columns={"count": "mentions"})
    )

    # Combine representative metadata with summed mentions
    result = representative.merge(group_mentions, on="merge_key")
    result = (
        result[["canonical_name", "type", "mentions"]]
        .sort_values("mentions", ascending=False, kind="stable")
        .head(effective_n)
        .reset_index(drop=True)
    )
    return result


# ---------------------------------------------------------------------------
# Output 3 — Tag leaderboard
# ---------------------------------------------------------------------------

def build_tag_leaderboard(
    tag_mentions_df: pd.DataFrame,
    top_n: int = 50,
) -> pd.DataFrame:
    """Return the top-N tags by raw frequency count.

    No merging, no casefolding — tags are returned exactly as stored.
    Ties are broken by tag name ascending.

    Parameters
    ----------
    tag_mentions_df:
        DataFrame with columns ``tag`` (str) and ``count`` (int).
    top_n:
        Maximum rows to return.  Hard-capped at :data:`_LEADERBOARD_HARD_CAP`.

    Returns
    -------
    pd.DataFrame
        Columns: ``tag``, ``count``.  Sorted by ``count`` descending.
    """
    effective_n = min(top_n, _LEADERBOARD_HARD_CAP)

    result = (
        tag_mentions_df
        .sort_values(["count", "tag"], ascending=[False, True], kind="stable")
        .head(effective_n)
        .reset_index(drop=True)
    )
    return result[["tag", "count"]]


# ---------------------------------------------------------------------------
# Output 4 — Metadata JSON
# ---------------------------------------------------------------------------

def build_term_stats_meta(
    entity_mentions_df: pd.DataFrame,
    tag_mentions_df: pd.DataFrame,
    entity_types_df: pd.DataFrame,
    *,
    enriched_at: Optional[str] = None,
) -> dict:
    """Build the term-stats provenance metadata dictionary.

    Parameters
    ----------
    entity_mentions_df:
        DataFrame with columns ``entity`` and ``count``.
    tag_mentions_df:
        DataFrame with columns ``tag`` and ``count``.
    entity_types_df:
        DataFrame with columns ``entity``, ``type``, ``canonical_name``.
    enriched_at:
        Optional ISO-8601 UTC timestamp string.  If ``None``, the current UTC
        time is used.  Inject a fixed value in tests for determinism.

    Returns
    -------
    dict
        Keys: ``n_distinct_entities``, ``n_entity_mentions``,
        ``n_distinct_tags``, ``n_tag_mentions``, ``model``,
        ``enriched_at``, ``n_classified``.
    """
    if enriched_at is None:
        enriched_at = (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
        )

    return {
        "n_distinct_entities": len(entity_mentions_df),
        "n_entity_mentions": int(entity_mentions_df["count"].sum()),
        "n_distinct_tags": len(tag_mentions_df),
        "n_tag_mentions": int(tag_mentions_df["count"].sum()),
        "model": OPENAI_MODEL,
        "enriched_at": enriched_at,
        "n_classified": len(entity_types_df),
    }


# ---------------------------------------------------------------------------
# Write all outputs
# ---------------------------------------------------------------------------

def write_outputs(
    *,
    entity_mentions_df: pd.DataFrame,
    entity_types_df: pd.DataFrame,
    tag_mentions_df: pd.DataFrame,
    breakdown_path: pathlib.Path,
    entity_leaderboard_path: pathlib.Path,
    tag_leaderboard_path: pathlib.Path,
    meta_path: pathlib.Path,
    entity_leaderboard_top_n: int = 50,
    tag_leaderboard_top_n: int = 50,
    enriched_at: Optional[str] = None,
) -> dict:
    """Compute and write all four output artifacts.

    Returns a summary dict for logging.
    """
    # Breakdown (computed pre-merge — independent of alias collapse)
    breakdown = build_entity_type_breakdown(entity_mentions_df, entity_types_df)
    breakdown.to_csv(breakdown_path, index=False)

    # Entity leaderboard (alias-merged)
    entity_lb = build_entity_leaderboard(
        entity_mentions_df, entity_types_df, top_n=entity_leaderboard_top_n
    )
    entity_lb.to_csv(entity_leaderboard_path, index=False)

    # Tag leaderboard (pure frequency)
    tag_lb = build_tag_leaderboard(tag_mentions_df, top_n=tag_leaderboard_top_n)
    tag_lb.to_csv(tag_leaderboard_path, index=False)

    # Metadata JSON
    meta = build_term_stats_meta(
        entity_mentions_df, tag_mentions_df, entity_types_df,
        enriched_at=enriched_at,
    )
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    return {
        "breakdown_rows": len(breakdown),
        "entity_lb_rows": len(entity_lb),
        "tag_lb_rows": len(tag_lb),
        "meta": meta,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Read the three input CSVs and write all four output files."""
    for path, label in [
        (ENTITY_MENTIONS_CSV, "entity_mentions.csv"),
        (TAG_MENTIONS_CSV, "tag_mentions.csv"),
        (ENTITY_TYPES_CSV, "entity_types.csv"),
    ]:
        if not path.exists():
            print(
                f"ERROR: required input not found: {path}\n"
                f"Run tools/extract_terms.py (and tools/classify_entities.py for "
                f"entity_types.csv) first.",
                flush=True,
            )
            sys.exit(1)

    print(f"reading {ENTITY_MENTIONS_CSV} ...", flush=True)
    entity_mentions = pd.read_csv(ENTITY_MENTIONS_CSV, keep_default_na=False, na_values=[])
    entity_mentions["count"] = entity_mentions["count"].astype(int)

    print(f"reading {TAG_MENTIONS_CSV} ...", flush=True)
    tag_mentions = pd.read_csv(TAG_MENTIONS_CSV, keep_default_na=False, na_values=[])
    tag_mentions["count"] = tag_mentions["count"].astype(int)

    print(f"reading {ENTITY_TYPES_CSV} ...", flush=True)
    entity_types = pd.read_csv(ENTITY_TYPES_CSV, keep_default_na=False, na_values=[])

    summary = write_outputs(
        entity_mentions_df=entity_mentions,
        entity_types_df=entity_types,
        tag_mentions_df=tag_mentions,
        breakdown_path=ENTITY_TYPE_BREAKDOWN_CSV,
        entity_leaderboard_path=ENTITY_LEADERBOARD_CSV,
        tag_leaderboard_path=TAG_LEADERBOARD_CSV,
        meta_path=TERM_STATS_META_JSON,
        entity_leaderboard_top_n=LEADERBOARD_STORE_N,
        tag_leaderboard_top_n=LEADERBOARD_STORE_N,
    )

    meta = summary["meta"]
    print(
        f"wrote {ENTITY_TYPE_BREAKDOWN_CSV}  "
        f"({summary['breakdown_rows']} type buckets)",
        flush=True,
    )
    print(
        f"wrote {ENTITY_LEADERBOARD_CSV}  "
        f"({summary['entity_lb_rows']} entities, "
        f"{meta['n_entity_mentions']:,} total mentions)",
        flush=True,
    )
    print(
        f"wrote {TAG_LEADERBOARD_CSV}  "
        f"({summary['tag_lb_rows']} tags, "
        f"{meta['n_tag_mentions']:,} total tag mentions)",
        flush=True,
    )
    print(f"wrote {TERM_STATS_META_JSON}", flush=True)


if __name__ == "__main__":
    main()
