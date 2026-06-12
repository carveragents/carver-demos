"""App-facing cached loader for the Carver Annotation Data Showcase.

Five public functions
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

load_term_stats(...) -> dict | None
    Read the three rollup CSVs and term_stats_meta.json produced by
    tools/build_term_stats.py.  Returns a dict of DataFrames + meta when the core
    artifacts (breakdown CSV and meta JSON) are present; returns None gracefully
    when they are absent (e.g. a fresh checkout with no enrichment run yet).

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

import datetime
import json
import logging
import pathlib
from typing import Optional

import pandas as pd

from carver_showcase.config import (
    ANNOTATIONS_JSONL,
    ANNOTATIONS_PARQUET,
    DOMAIN_FALLBACK_LEAF,
    ENTITY_LEADERBOARD_CSV,
    ENTITY_TYPE_BREAKDOWN_CSV,
    INSTITUTION_DOMAIN_PARENT,
    REGULATOR_CANONICAL_CSV,
    REGULATOR_CONTEXT_CSV,
    SNAPSHOT_META_JSON,
    TAG_LEADERBOARD_CSV,
    TERM_STATS_META_JSON,
    TOPIC_CATEGORIES_CSV,
    TOPIC_CATALOG_CSV,
    TOPIC_DOMAINS_CSV,
)
from carver_showcase import schema
from carver_showcase.curate import drop_noise_update_types
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


def _regulator_merge_key(name: str) -> str:
    """Light dedup key for canonical regulator names: lowercase, strip
    punctuation, collapse whitespace.  Deliberately does NOT strip
    institution-type nouns (commission/board/authority/…) — unlike
    quality.canonicalize_regulator (which is tuned for the Cockpit's
    near-duplicate *anomaly* heuristic) — so genuinely distinct bodies like
    'Financial Services Agency' vs 'Financial Services Authority' keep separate
    keys, while punctuation/case/hyphenation variants still collapse.
    """
    import re

    s = str(name).lower().strip()
    s = re.sub(r"[^\w\s]", "", s)      # strip punctuation (no space substitution)
    s = re.sub(r"\s+", " ", s).strip()
    return s


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
# Public: load_topic_domains
# ---------------------------------------------------------------------------


def load_topic_domains(
    path: pathlib.Path = TOPIC_DOMAINS_CSV,
) -> pd.DataFrame:
    """Read the LLM-assigned institution domain CSV and return a clean frame.

    The CSV is produced by ``tools/classify_domains.py`` and contains one row per
    monitored institution (topic), mapping it to a leaf in the fixed two-level
    taxonomy defined in ``carver_showcase.config``.

    The loader is the **authority on the hierarchy**: it coerces any ``sub_domain``
    not found in ``INSTITUTION_DOMAIN_PARENT`` to ``DOMAIN_FALLBACK_LEAF`` and
    always re-derives ``top_level`` from the config map — so the returned frame
    is guaranteed to be a valid 2-level hierarchy regardless of what the CSV
    actually contains.

    Parameters
    ----------
    path:
        Path to ``topic_domains.csv``.  Expected columns: ``topic_id``,
        ``sub_domain``, ``top_level`` (required), plus an optional ``secondary``.

    Returns
    -------
    pd.DataFrame
        Columns: ``topic_id``, ``sub_domain``, ``top_level`` (plus ``secondary``
        if present in the CSV).  Rows with blank ``topic_id`` are dropped.
        If the file does not exist, returns an empty ``pd.DataFrame()`` with a
        warning (never raises).
    """
    path = pathlib.Path(path)

    if not path.exists():
        logger.warning(
            "topic_domains.csv not found at %s; returning empty DataFrame", path
        )
        return pd.DataFrame()

    df = pd.read_csv(path, keep_default_na=False, na_values=[], dtype=str)
    logger.info("Loaded topic domains: %s rows from %s", len(df), path)

    # Drop rows with blank topic_id
    df = df[df["topic_id"].str.strip() != ""].reset_index(drop=True)

    # Coerce sub_domain: any value not in the taxonomy → DOMAIN_FALLBACK_LEAF
    df["sub_domain"] = df["sub_domain"].apply(
        lambda v: v if v in INSTITUTION_DOMAIN_PARENT else DOMAIN_FALLBACK_LEAF
    )

    # Always re-derive top_level from the config (ignore/overwrite CSV value)
    df["top_level"] = df["sub_domain"].map(INSTITUTION_DOMAIN_PARENT)

    # Determine which columns to return (secondary is optional passthrough)
    keep_cols = ["topic_id", "sub_domain", "top_level"]
    if "secondary" in df.columns:
        keep_cols.append("secondary")

    return df[keep_cols]


# ---------------------------------------------------------------------------
# Public: load_term_stats
# ---------------------------------------------------------------------------


def load_term_stats(
    breakdown_path: pathlib.Path = ENTITY_TYPE_BREAKDOWN_CSV,
    entity_leaderboard_path: pathlib.Path = ENTITY_LEADERBOARD_CSV,
    tag_leaderboard_path: pathlib.Path = TAG_LEADERBOARD_CSV,
    meta_path: pathlib.Path = TERM_STATS_META_JSON,
) -> Optional[dict]:
    """Read the rollup artifacts produced by tools/build_term_stats.py.

    Reads the **three rollup CSVs** (entity type breakdown, entity leaderboard,
    tag leaderboard) and the term_stats_meta.json provenance file.  Does NOT
    read the tool-internal entity_types.csv, entity_mentions.csv, or
    tag_mentions.csv — those are build-time intermediates.

    Core-absent rule
    ----------------
    Returns ``None`` (no exception) when either the breakdown CSV *or* the meta
    JSON is missing.  Both must be present for a successful load — they are the
    primary outputs of the enrichment run.  If the leaderboard CSVs are absent
    they are returned as empty DataFrames so the gallery can still render a
    partial result.

    Parameters
    ----------
    breakdown_path:
        Path to ``entity_type_breakdown.csv``.  Columns: ``type``, ``mentions``,
        ``distinct_entities``.
    entity_leaderboard_path:
        Path to ``entity_leaderboard.csv``.  Columns: ``canonical_name``,
        ``type``, ``mentions``.
    tag_leaderboard_path:
        Path to ``tag_leaderboard.csv``.  Columns: ``tag``, ``count``.
    meta_path:
        Path to ``term_stats_meta.json``.

    Returns
    -------
    dict | None
        ``{"breakdown": DataFrame, "entity_leaderboard": DataFrame,
        "tag_leaderboard": DataFrame, "meta": dict}`` when core artifacts are
        present, else ``None``.

    Notes
    -----
    Wrap this in ``st.cache_data`` at the app edge — it is intentionally kept
    framework-agnostic so it is testable without Streamlit.
    """
    breakdown_path = pathlib.Path(breakdown_path)
    entity_leaderboard_path = pathlib.Path(entity_leaderboard_path)
    tag_leaderboard_path = pathlib.Path(tag_leaderboard_path)
    meta_path = pathlib.Path(meta_path)

    # Core-absent check: both the breakdown CSV and meta JSON must be present.
    if not breakdown_path.exists() or not meta_path.exists():
        logger.warning(
            "term_stats core artifacts absent (breakdown=%s, meta=%s); "
            "run tools/build_term_stats.py first",
            breakdown_path,
            meta_path,
        )
        return None

    # Read the breakdown CSV (core artifact — already confirmed it exists).
    # keep_default_na=False so text values like "NA" or "null" stay as strings,
    # not float NaN.  Numeric columns are cast explicitly after reading.
    breakdown = pd.read_csv(breakdown_path, keep_default_na=False, na_values=[])
    breakdown["mentions"] = breakdown["mentions"].astype(int)
    breakdown["distinct_entities"] = breakdown["distinct_entities"].astype(int)
    logger.info("Loaded entity type breakdown: %d rows from %s", len(breakdown), breakdown_path)

    # Read the entity leaderboard (optional — empty DataFrame if missing)
    if entity_leaderboard_path.exists():
        entity_leaderboard = pd.read_csv(
            entity_leaderboard_path, keep_default_na=False, na_values=[]
        )
        entity_leaderboard["mentions"] = entity_leaderboard["mentions"].astype(int)
        logger.info(
            "Loaded entity leaderboard: %d rows from %s",
            len(entity_leaderboard),
            entity_leaderboard_path,
        )
    else:
        logger.warning(
            "entity_leaderboard.csv not found at %s; returning empty DataFrame",
            entity_leaderboard_path,
        )
        entity_leaderboard = pd.DataFrame(columns=["canonical_name", "type", "mentions"])

    # Read the tag leaderboard (optional — empty DataFrame if missing)
    if tag_leaderboard_path.exists():
        tag_leaderboard = pd.read_csv(
            tag_leaderboard_path, keep_default_na=False, na_values=[]
        )
        tag_leaderboard["count"] = tag_leaderboard["count"].astype(int)
        logger.info(
            "Loaded tag leaderboard: %d rows from %s",
            len(tag_leaderboard),
            tag_leaderboard_path,
        )
    else:
        logger.warning(
            "tag_leaderboard.csv not found at %s; returning empty DataFrame",
            tag_leaderboard_path,
        )
        tag_leaderboard = pd.DataFrame(columns=["tag", "count"])

    # Read the meta JSON (core artifact — already confirmed it exists)
    try:
        meta: dict = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read term_stats meta %s: %s", meta_path, exc)
        meta = {}

    return {
        "breakdown": breakdown,
        "entity_leaderboard": entity_leaderboard,
        "tag_leaderboard": tag_leaderboard,
        "meta": meta,
    }


# ---------------------------------------------------------------------------
# Public: load_regulator_canonical
# ---------------------------------------------------------------------------


def load_regulator_canonical(
    path: pathlib.Path = REGULATOR_CANONICAL_CSV,
) -> Optional[dict]:
    """Read the regulator-canonicalization artifact produced by tools/canonicalize_regulators.py.

    Returns a dict mapping each raw ``regulator_name`` → a small record::

        {
            "canonical": <canonical_regulator str>,
            "is_regulator": <bool>,
            "key": <_regulator_merge_key(canonical_regulator) str>,
        }

    The ``key`` is computed by applying ``_regulator_merge_key`` to the
    *canonical* name (not the raw name), so punctuation / case / whitespace
    variants of the same body collapse to the same merge key while genuinely
    distinct bodies (e.g. "Financial Services Agency" vs "Financial Services
    Authority") remain separate.  When the canonical normalises to blank, the
    key falls back to ``_regulator_merge_key(regulator_name)`` and finally to
    the raw name verbatim so the key is never an empty string.

    Absent-file rule
    ----------------
    Returns ``None`` when the file does not exist (the batch run has not been done
    yet).  Callers should fall back to raw-name behaviour in that case.

    Defensive absent/empty rules
    ----------------------------
    Returns ``None`` when the file exists but is empty or missing required
    columns (``regulator_name``, ``canonical_regulator``, ``is_regulator``).

    Notes
    -----
    ``keep_default_na=False, na_values=[]`` is critical: a regulator literally
    named ``"NA"`` must survive as the string ``"NA"``, not become a float NaN.
    ``is_regulator`` is serialised by ``csv.DictWriter`` as the string ``"True"``
    or ``"False"``; it is parsed case-insensitively (``"true"``/``"1"`` → True,
    anything else → False).
    """
    path = pathlib.Path(path)

    if not path.exists():
        logger.warning(
            "regulator_canonical.csv not found at %s; "
            "run tools/canonicalize_regulators.py first",
            path,
        )
        return None

    try:
        df = pd.read_csv(path, keep_default_na=False, na_values=[])
    except Exception as exc:  # e.g. EmptyDataError for a completely empty file
        logger.warning(
            "Could not read regulator_canonical.csv at %s: %s; returning None",
            path,
            exc,
        )
        return None

    required_cols = {"regulator_name", "canonical_regulator", "is_regulator"}
    if df.empty or not required_cols.issubset(df.columns):
        logger.warning(
            "regulator_canonical.csv at %s is empty or missing required columns "
            "(need %s, got %s); returning None",
            path,
            required_cols,
            set(df.columns),
        )
        return None

    # Cast mentions to int when present (not required for the return dict, but
    # mirrors load_term_stats' explicit int-casting convention).
    # Use pd.to_numeric with errors="coerce" so malformed values (e.g. "250.0",
    # "", or a stray word) become NaN → 0 instead of raising ValueError.
    if "mentions" in df.columns:
        df["mentions"] = pd.to_numeric(df["mentions"], errors="coerce").fillna(0).astype(int)

    result: dict = {}
    for _, row in df.iterrows():
        raw_name = row["regulator_name"]
        canonical = row["canonical_regulator"]

        # Parse is_regulator: "True" / "true" / "1" → True, anything else → False.
        is_reg_raw = str(row["is_regulator"]).strip().lower()
        is_reg = is_reg_raw in ("true", "1")

        # Merge key: apply light normalization (punctuation/case/whitespace only)
        # to the *canonical* name; fall back to the lightly-normalized raw name,
        # then to the raw name verbatim so key is never an empty string.
        key = _regulator_merge_key(canonical) or _regulator_merge_key(raw_name) or raw_name

        result[raw_name] = {
            "canonical": canonical,
            "is_regulator": is_reg,
            "key": key,
        }

    logger.info(
        "Loaded regulator canonical map: %d entries from %s", len(result), path
    )
    return result


# ---------------------------------------------------------------------------
# Internal: curated mention counts from parquet
# ---------------------------------------------------------------------------


def _curated_regulator_mentions(
    parquet_path: pathlib.Path = ANNOTATIONS_PARQUET,
) -> dict:
    """Return per-raw-regulator-name mention counts from the curated parquet.

    Reads only the ``regulator_name`` and ``update_type`` columns from the
    annotations parquet, applies ``drop_noise_update_types`` to strip the same
    crawl-junk rows that the gallery/deck curate away, then counts rows per
    regulator_name.  The result is the authoritative curated mention source for
    ``load_regulator_stats``.

    Parameters
    ----------
    parquet_path:
        Path to the annotations parquet (defaults to ``ANNOTATIONS_PARQUET``).

    Returns
    -------
    dict
        Mapping ``regulator_name`` (str) → curated mention count (int).
        Names with zero curated mentions are absent from the dict.
    """
    df = pd.read_parquet(parquet_path, columns=["regulator_name", "update_type"])
    df = drop_noise_update_types(df)
    return df["regulator_name"].dropna().value_counts().to_dict()


# ---------------------------------------------------------------------------
# Public: load_regulator_stats
# ---------------------------------------------------------------------------


def load_regulator_stats(
    canonical_path: pathlib.Path = REGULATOR_CANONICAL_CSV,
    context_path: pathlib.Path = REGULATOR_CONTEXT_CSV,
    mentions_by_name: Optional[dict] = None,
) -> Optional[dict]:
    """Read the regulator canonicalization CSVs and return aggregated stats.

    Reads ``regulator_canonical.csv`` (raw → canonical + is_regulator +
    mentions) and ``regulator_context.csv`` (raw → countries JSON list) and
    delegates to ``regulator_stats.build_regulator_stats`` to produce the
    three outputs needed by the gallery's Regulators tab.

    By default, curated mention counts are derived from the annotations parquet
    (noise update_types dropped via ``drop_noise_update_types``) so the
    Regulators tab is consistent with the Overview KPI which counts over the
    same curated frame.  Pass ``mentions_by_name`` explicitly to override this
    (useful in tests to avoid reading the full parquet).

    Absent-file rules
    -----------------
    Returns ``None`` when ``regulator_canonical.csv`` is absent (the
    canonicalization run has not been done yet).  Mirrors ``load_term_stats``.

    When ``regulator_context.csv`` is absent, passes an empty DataFrame so
    the build function still returns a valid dict (by_country will be empty
    since no countries are available, but leaderboard and meta are correct).

    Parameters
    ----------
    canonical_path:
        Path to ``regulator_canonical.csv``.
    context_path:
        Path to ``regulator_context.csv``.
    mentions_by_name:
        Optional mapping of raw ``regulator_name`` → curated mention count.
        When ``None`` (default), computed via ``_curated_regulator_mentions()``.

    Returns
    -------
    dict | None
        ``{"leaderboard": DataFrame, "by_country": DataFrame, "meta": dict}``
        when canonical CSV is present, else ``None``.

    Notes
    -----
    Wrap this in ``st.cache_data`` at the app edge — intentionally kept
    framework-agnostic for testability.
    """
    from carver_showcase import regulator_stats as _rs

    canonical_path = pathlib.Path(canonical_path)
    context_path = pathlib.Path(context_path)

    if not canonical_path.exists():
        logger.warning(
            "regulator_canonical.csv not found at %s; "
            "run tools/canonicalize_regulators.py first",
            canonical_path,
        )
        return None

    canonical_df = pd.read_csv(canonical_path, keep_default_na=False, na_values=[])
    # Note: build_regulator_stats casts mentions defensively (pd.to_numeric + fillna + astype(int)),
    # so no need to cast here.

    if context_path.exists():
        context_df = pd.read_csv(context_path, keep_default_na=False, na_values=[])
        logger.info("Loaded regulator context: %d rows from %s", len(context_df), context_path)
    else:
        logger.warning(
            "regulator_context.csv not found at %s; "
            "by_country will be empty (no country data)",
            context_path,
        )
        context_df = pd.DataFrame(columns=["regulator_name", "countries"])

    if mentions_by_name is None:
        mentions_by_name = _curated_regulator_mentions()

    return _rs.build_regulator_stats(canonical_df, context_df, mentions_by_name=mentions_by_name)


# ---------------------------------------------------------------------------
# Public: load_snapshot_meta
# ---------------------------------------------------------------------------


def load_snapshot_meta(
    meta_path: pathlib.Path = SNAPSHOT_META_JSON,
    parquet_path: pathlib.Path = ANNOTATIONS_PARQUET,
    jsonl_path: pathlib.Path = ANNOTATIONS_JSONL,
) -> dict:
    """Read the snapshot provenance written at pull time.

    The pull tool writes ``snapshot_meta.json`` recording when the snapshot was
    pulled, its scope (``"full"`` vs ``"stratified"``), and per-category counts.
    The apps use this to show an honest "point-in-time as of <date>" note so a
    viewer never mistakes the snapshot for a live feed.

    Always returns a dict.  When the metadata file is absent (e.g. an old
    snapshot), ``snapshot_date`` falls back to the snapshot file's modification
    date so the date note still renders something truthful.

    Returns
    -------
    dict
        Keys (best-effort): ``snapshot_date`` (ISO ``YYYY-MM-DD`` str),
        ``scope`` (str), ``total_records`` (int), ``category_counts`` (dict).
    """
    meta_path = pathlib.Path(meta_path)
    data: dict = {}
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read snapshot meta %s: %s", meta_path, exc)
            data = {}

    if not data.get("snapshot_date"):
        for candidate in (parquet_path, jsonl_path):
            candidate = pathlib.Path(candidate)
            if candidate.exists():
                mtime = datetime.datetime.fromtimestamp(
                    candidate.stat().st_mtime, tz=datetime.timezone.utc
                )
                data["snapshot_date"] = mtime.date().isoformat()
                data.setdefault("snapshot_date_source", "file_mtime")
                break

    return data


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
