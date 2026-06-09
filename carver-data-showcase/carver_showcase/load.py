"""App-facing cached loader for the Carver Annotation Data Showcase.

Four public functions
---------------------
load_normalized(parquet_path, jsonl_path, categories_path, rebuild) -> DataFrame
    Build-or-load the normalized annotations parquet.
    - If parquet is missing OR rebuild=True: stream the JSONL via ingest.load_snapshot,
      build the frame via normalize.normalize_frame, apply schema.DTYPES (coercing bad
      dates to NaT), persist to parquet (pyarrow), and return.
    - Otherwise: read the parquet directly.
    Memory-safe: the raw JSONL is never fully loaded; it is streamed line-by-line.

load_catalog(catalog_path) -> DataFrame
    Read topic_catalog.csv (the 1,071-institution catalog) and return it.

build_record_index(jsonl_path) -> dict[str, int]
    One-pass over the JSONL recording each record's artifact_id (envelope ``id``)
    → byte offset.  The app wraps this in st.cache_data.

get_raw_record(artifact_id, jsonl_path, index) -> dict | None
    Seek to the byte offset (build the index if not supplied), read that line,
    return the parsed envelope.  Returns None if the artifact_id is not found.

Design constraints
------------------
- NO streamlit import — this module is framework-agnostic. The app wraps these
  functions in st.cache_data at the app edge.
- Streaming build (Risk R1): ingest.load_snapshot yields one envelope at a time;
  normalize_frame accumulates only the ~70 scalar/flag/count columns and discards
  the raw nested payload, so the persisted parquet is small (~MB, not 423 MB).
- Parquet datetime cast uses errors="coerce" so garbage dates (e.g. 2105-07-01,
  1947-12-25) become NaT instead of throwing.
- build_record_index / get_raw_record operate on the raw JSONL so the drill-down
  can serve the full nested annotation payload without loading the full 423 MB file
  into memory — it seeks directly to the relevant line.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Optional

import pandas as pd

from carver_showcase.config import (
    ANNOTATIONS_JSONL,
    ANNOTATIONS_PARQUET,
    TOPIC_CATEGORIES_CSV,
    TOPIC_CATALOG_CSV,
)
from carver_showcase import schema
from carver_showcase.ingest import load_snapshot
from carver_showcase.normalize import normalize_frame
from carver_showcase.richness import richness_scores

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Cast each column to its declared dtype from schema.DTYPES.

    Datetime columns are parsed with errors="coerce" so garbage dates become NaT
    rather than raising an exception.  All other dtypes use the pandas default
    coercion path.

    Parameters
    ----------
    df:
        DataFrame with columns matching schema.NORMALIZED_COLUMNS.

    Returns
    -------
    pd.DataFrame
        Same DataFrame with dtypes applied (in-place mutation avoided).
    """
    result = df.copy()

    for col, dtype in schema.DTYPES.items():
        if col not in result.columns:
            continue

        if "datetime64" in dtype:
            # Coerce to UTC datetime; bad strings/values become NaT
            result[col] = pd.to_datetime(result[col], utc=True, errors="coerce")
        else:
            try:
                result[col] = result[col].astype(dtype)
            except (TypeError, ValueError) as exc:
                logger.warning("Could not cast column %s to %s: %s", col, dtype, exc)

    return result


# ---------------------------------------------------------------------------
# Public: load_normalized
# ---------------------------------------------------------------------------


def load_normalized(
    parquet_path: pathlib.Path = ANNOTATIONS_PARQUET,
    jsonl_path: pathlib.Path = ANNOTATIONS_JSONL,
    categories_path: pathlib.Path = TOPIC_CATEGORIES_CSV,
    rebuild: bool = False,
) -> pd.DataFrame:
    """Load the normalized annotations DataFrame, building from JSONL if needed.

    Parameters
    ----------
    parquet_path:
        Path to the cached parquet file.  Created on first call (or when
        ``rebuild=True``).
    jsonl_path:
        Path to the raw annotations JSONL snapshot.  Only read when building.
    categories_path:
        Path to ``topic_categories.csv`` (topic_id → category map).  Only read
        when building.
    rebuild:
        If True, re-build the parquet even if it already exists.

    Returns
    -------
    pd.DataFrame
        Normalized annotations with exactly ``schema.NORMALIZED_COLUMNS`` columns.

    Notes
    -----
    Build path is memory-safe: ``ingest.load_snapshot`` streams envelopes one at a
    time; only the flattened scalar rows (≈70 columns) are accumulated, never the
    423 MB raw JSONL payload.
    """
    parquet_path = pathlib.Path(parquet_path)
    jsonl_path = pathlib.Path(jsonl_path)
    categories_path = pathlib.Path(categories_path)

    if parquet_path.exists() and not rebuild:
        logger.info("Loading annotations from parquet: %s", parquet_path)
        df = pd.read_parquet(parquet_path)
        return df

    # Build path: stream JSONL → normalize → apply dtypes → persist
    logger.info(
        "Building annotations parquet from JSONL: %s → %s",
        jsonl_path,
        parquet_path,
    )

    # Load the category map (small CSV, safe to fully load)
    if categories_path.exists():
        categories = pd.read_csv(categories_path, dtype=str)
    else:
        logger.warning("topic_categories.csv not found at %s; category will be Uncategorized", categories_path)
        categories = pd.DataFrame(columns=["topic_id", "category"])

    # Stream the JSONL and normalize (memory-safe)
    records = load_snapshot(jsonl_path)
    df = normalize_frame(records, categories)

    # Apply typed dtypes (datetime coercion with errors="coerce")
    df = _apply_dtypes(df)

    # Materialize richness_score (spec §4.2 / Phase 4)
    # normalize_record leaves richness_score as NA; compute it here before persisting.
    df["richness_score"] = richness_scores(df)
    logger.info("richness_score computed: min=%.0f max=%.0f mean=%.1f",
                float(df["richness_score"].min()),
                float(df["richness_score"].max()),
                float(df["richness_score"].mean()))

    # Persist to parquet
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, engine="pyarrow", index=False)
    logger.info(
        "Parquet written: %s (shape=%s)", parquet_path, df.shape
    )

    return df


# ---------------------------------------------------------------------------
# Public: load_catalog
# ---------------------------------------------------------------------------


def load_catalog(
    catalog_path: pathlib.Path = TOPIC_CATALOG_CSV,
) -> pd.DataFrame:
    """Read the topics catalog CSV (all monitored institutions).

    Parameters
    ----------
    catalog_path:
        Path to ``topic_catalog.csv``.  Expected columns include at least
        ``topic_id``, ``name``, ``acronym``, ``category``, ``jurisdiction_code``.

    Returns
    -------
    pd.DataFrame
        The topics catalog.  If the file does not exist, returns an empty
        DataFrame with a warning.
    """
    catalog_path = pathlib.Path(catalog_path)

    if not catalog_path.exists():
        logger.warning("topic_catalog.csv not found at %s; returning empty DataFrame", catalog_path)
        return pd.DataFrame()

    df = pd.read_csv(catalog_path, dtype=str)
    logger.info("Loaded topic catalog: %s rows from %s", len(df), catalog_path)
    return df


# ---------------------------------------------------------------------------
# Public: build_record_index
# ---------------------------------------------------------------------------


def build_record_index(
    jsonl_path: pathlib.Path = ANNOTATIONS_JSONL,
) -> dict[str, int]:
    """Build a mapping from artifact_id → byte offset in the JSONL file.

    One pass over the JSONL; reads only enough bytes per line to extract the
    ``id`` field from the JSON envelope.  The index lets ``get_raw_record``
    seek directly to any record without loading the full file into memory.

    Parameters
    ----------
    jsonl_path:
        Path to the JSONL annotations file.

    Returns
    -------
    dict[str, int]
        Mapping from ``artifact_id`` (envelope ``id`` field) to the byte offset
        of the start of that line.

    Notes
    -----
    Wrap this in ``st.cache_data`` at the app edge — it is intentionally kept
    framework-agnostic so it is testable without Streamlit.
    """
    jsonl_path = pathlib.Path(jsonl_path)
    index: dict[str, int] = {}

    with jsonl_path.open("rb") as fh:
        while True:
            offset = fh.tell()
            line = fh.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSONL line at offset %d", offset)
                continue
            artifact_id = record.get("id")
            if artifact_id:
                index[artifact_id] = offset

    logger.info("Built record index: %d entries from %s", len(index), jsonl_path)
    return index


# ---------------------------------------------------------------------------
# Public: get_raw_record
# ---------------------------------------------------------------------------


def get_raw_record(
    artifact_id: str,
    jsonl_path: pathlib.Path = ANNOTATIONS_JSONL,
    index: Optional[dict[str, int]] = None,
) -> Optional[dict]:
    """Retrieve the raw envelope for a single artifact_id from the JSONL.

    Parameters
    ----------
    artifact_id:
        The envelope ``id`` to look up.
    jsonl_path:
        Path to the JSONL annotations file.
    index:
        Pre-built index from ``build_record_index``.  If not supplied, a
        temporary index is built for this call (less efficient but correct).

    Returns
    -------
    dict | None
        The parsed envelope dict, or None if the artifact_id is not found.

    Notes
    -----
    The caller uses ``result["output_data"]`` to access the full annotation
    payload for the drill-down render.
    """
    jsonl_path = pathlib.Path(jsonl_path)

    if index is None:
        index = build_record_index(jsonl_path)

    offset = index.get(artifact_id)
    if offset is None:
        return None

    with jsonl_path.open("rb") as fh:
        fh.seek(offset)
        line = fh.readline()

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSONL line at offset %d for artifact_id %s", offset, artifact_id)
        return None
