"""Normalize raw Carver annotation envelopes into flat analytics rows.

Two public functions:

* `normalize_record(raw)` — one envelope → one flat dict with exactly the
  columns declared in `schema.NORMALIZED_COLUMNS`.
* `normalize_frame(records, categories)` — many envelopes → DataFrame with
  exactly `NORMALIZED_COLUMNS`; left-joins the `category` column from the
  supplied topic→category mapping.

Design constraints
------------------
- Deterministic: no LLM, no network at import or normalize time.
- Empties-first: ``""``, whitespace-only, empty list/dict, and
  ``config.PLACEHOLDERS`` (case-insensitive) all become ``pd.NA`` / ``None``
  before any count or flag is derived.
- `richness_score` is always left as ``pd.NA``; it is materialized in Phase 4.
- `language` is a list (e.g. ``["en"]``) in the payload and is collapsed to its
  primary code; `regulator_other_agency` (also a list) is collapsed to a
  "; "-joined string, so both fit their scalar `string` columns.
- Date strings pass through as-is (with their paired ``*_calendar``); datetime
  parsing is deferred to the Phase 3 parquet build, so no value here can throw
  on a garbage date.
"""

from __future__ import annotations

import re
import warnings
from typing import Any, Iterable, Optional

import pandas as pd

from carver_showcase import schema
from carver_showcase.config import (
    ACTIONABLE_LANES,
    IMPACT_SUMMARY_PARTS,
    PLACEHOLDERS,
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _is_missing(value: Any) -> bool:
    """Return True if `value` should be treated as missing data.

    A value is missing when it is:
    - ``None`` / ``pd.NA`` / ``float('nan')``
    - An empty string or a whitespace-only string
    - A placeholder string in ``config.PLACEHOLDERS`` (case-insensitive)
    - An empty list or empty dict
    """
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped.lower() in PLACEHOLDERS
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _to_na(value: Any) -> Any:
    """Return ``pd.NA`` when the value is missing, otherwise return it unchanged."""
    return pd.NA if _is_missing(value) else value


def _get_nested(data: dict, dotted_path: str) -> Any:
    """Traverse a dotted key path through nested dicts; return None if any key is absent."""
    parts = dotted_path.split(".")
    node: Any = data
    for part in parts:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _extract_base_url(feed_url: Any) -> Any:
    """Derive the host (with any leading ``www.`` stripped) from a URL string.

    Not a full public-suffix parse — it returns the host minus a ``www`` prefix,
    so subdomains are preserved.

    Examples
    --------
    ``https://www.fca.org.uk/news/...`` → ``"fca.org.uk"``
    ``https://hcpf.colorado.gov/...``   → ``"hcpf.colorado.gov"``

    Returns ``pd.NA`` when feed_url is missing or unparseable.
    """
    if _is_missing(feed_url):
        return pd.NA
    url = str(feed_url).strip()
    # Strip scheme
    url = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    # Strip everything after the first /
    host = url.split("/")[0].split("?")[0].split("#")[0]
    if not host:
        return pd.NA
    # Strip www. or www2. prefix
    host = re.sub(r"^www\d*\.", "", host, flags=re.IGNORECASE)
    return host if host else pd.NA


def _count_non_empty_list(lst: Any) -> int:
    """Return the number of non-missing items in a list (or 0 for non-list/empty)."""
    if not isinstance(lst, list):
        return 0
    return sum(1 for item in lst if not _is_missing(item))


def _count_key_date_types(critical_dates: dict) -> int:
    """Count the number of populated key date types (not other_dates)."""
    key_date_fields = [
        "effective_date",
        "compliance_date",
        "comment_deadline",
        "early_adoption_date",
        "updated_date",
        "pub_date_content",
    ]
    return sum(
        1 for field in key_date_fields if not _is_missing(critical_dates.get(field))
    )


# ---------------------------------------------------------------------------
# Public: single record normalization
# ---------------------------------------------------------------------------


def normalize_record(raw: dict) -> dict:
    """Map one raw annotation envelope to one flat row dict.

    The returned dict has exactly the keys in ``schema.NORMALIZED_COLUMNS``.
    All missing/empty/placeholder values are represented as ``pd.NA``.
    ``richness_score`` is always ``pd.NA`` (Phase 4).

    Parameters
    ----------
    raw:
        A raw envelope dict as yielded by ``ingest.load_snapshot``.

    Returns
    -------
    dict
        Flat row with keys == ``schema.NORMALIZED_COLUMNS``.
    """
    row: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Step 1: apply FIELD_MAP — dotted paths → column values
    # ------------------------------------------------------------------
    for src_path, col in schema.FIELD_MAP.items():
        row[col] = _to_na(_get_nested(raw, src_path))

    # ------------------------------------------------------------------
    # Step 2: language is stored as a list (e.g. ["en"]) in the real payload;
    # collapse to the primary language code for a scalar column.
    # ------------------------------------------------------------------
    lang = row.get("language")
    if isinstance(lang, list):
        row["language"] = _to_na(lang[0] if lang else None)

    # regulator_other_agency is a list in the payload; collapse to a scalar.
    oa = row.get("regulator_other_agency")
    if isinstance(oa, list):
        row["regulator_other_agency"] = _to_na(
            "; ".join(str(x) for x in oa) if oa else None
        )

    # ------------------------------------------------------------------
    # Step 3: base_url — derived from feed_url
    # ------------------------------------------------------------------
    row["base_url"] = _extract_base_url(row.get("feed_url"))

    # ------------------------------------------------------------------
    # Step 4: has_jurisdiction_tier_legacy
    # True if the deprecated `jurisdiction_tier` key exists in
    # output_data.classification (regardless of its value).
    # ------------------------------------------------------------------
    classification = _get_nested(raw, "output_data.classification") or {}
    row["has_jurisdiction_tier_legacy"] = "jurisdiction_tier" in classification

    # ------------------------------------------------------------------
    # Step 5: richness counts and flags
    # All counts are computed AFTER the empties→NA pass.
    # ------------------------------------------------------------------
    metadata = _get_nested(raw, "output_data.metadata") or {}

    # --- tags and entities ---
    tags = metadata.get("tags")
    entities = metadata.get("entities")
    row["n_tags"] = _count_non_empty_list(tags) if isinstance(tags, list) else 0
    row["n_entities"] = _count_non_empty_list(entities) if isinstance(entities, list) else 0

    # --- actionable lanes (7) ---
    actionables = metadata.get("actionables") or {}
    n_actionable = 0
    for lane in ACTIONABLE_LANES:
        if not _is_missing(actionables.get(lane)):
            n_actionable += 1
    row["n_actionable_lanes"] = n_actionable

    # --- impact summary (5 parts) ---
    impact_summary = metadata.get("impact_summary") or {}
    part_flags: dict[str, bool] = {}
    for part in IMPACT_SUMMARY_PARTS:
        val = impact_summary.get(part)
        if part == "key_requirements":
            # key_requirements is a LIST — has content when non-empty
            populated = isinstance(val, list) and _count_non_empty_list(val) > 0
        else:
            populated = not _is_missing(val)
        part_flags[part] = populated

    row["has_objective"] = part_flags.get("objective", False)
    row["has_what_changed"] = part_flags.get("what_changed", False)
    row["has_why_it_matters"] = part_flags.get("why_it_matters", False)
    row["has_risk_impact"] = part_flags.get("risk_impact", False)
    row["has_impact_summary"] = any(part_flags.values())

    key_reqs = impact_summary.get("key_requirements")
    row["n_key_requirements"] = (
        _count_non_empty_list(key_reqs) if isinstance(key_reqs, list) else 0
    )

    # --- regulatory references (6 lanes) ---
    reg_refs = metadata.get("reg_references") or {}
    lane_col_map = {
        "rules": "n_reg_rules",
        "statutes": "n_reg_statutes",
        "other_ref": "n_reg_other_ref",
        "personnel": "n_reg_personnel",
        "precedents": "n_reg_precedents",
        "past_release": "n_reg_past_release",
    }
    total_refs = 0
    for lane, col in lane_col_map.items():
        lst = reg_refs.get(lane, [])
        count = _count_non_empty_list(lst) if isinstance(lst, list) else 0
        row[col] = count
        total_refs += count
    row["n_reg_refs_total"] = total_refs

    # --- impacted business ---
    impacted_business = metadata.get("impacted_business") or {}
    has_impacted = False
    if isinstance(impacted_business, dict):
        for v in impacted_business.values():
            if not _is_missing(v):
                has_impacted = True
                break
    row["has_impacted_business"] = has_impacted

    # --- impacted functions ---
    imp_funcs = metadata.get("impacted_functions")
    row["n_impacted_functions"] = (
        _count_non_empty_list(imp_funcs) if isinstance(imp_funcs, list) else 0
    )

    # --- penalties ---
    penalties = metadata.get("penalties_consequences")
    if isinstance(penalties, list):
        n_pen = _count_non_empty_list(penalties)
    elif isinstance(penalties, str) and not _is_missing(penalties):
        n_pen = 1
    else:
        n_pen = 0
    row["n_penalties"] = n_pen
    row["has_penalties"] = n_pen > 0

    # --- critical dates counts ---
    critical_dates = metadata.get("critical_dates") or {}
    n_key_dates = _count_key_date_types(critical_dates)
    other_dates = critical_dates.get("other_dates")
    n_other = (
        _count_non_empty_list(other_dates) if isinstance(other_dates, list) else 0
    )
    row["n_other_dates"] = n_other
    row["n_critical_dates"] = n_key_dates + n_other

    # ------------------------------------------------------------------
    # Step 6: category — placeholder; filled by normalize_frame join
    # ------------------------------------------------------------------
    row["category"] = pd.NA

    # ------------------------------------------------------------------
    # Step 7: richness_score — deferred to Phase 4
    # ------------------------------------------------------------------
    row["richness_score"] = pd.NA

    # ------------------------------------------------------------------
    # Step 8: min_prose_len (Phase 4 quality support column)
    # The minimum character length among PRESENT prose parts of impact_summary.
    # Considers: objective, what_changed, why_it_matters, risk_impact (text fields)
    # and key_requirements (joined as a single string if present).
    # Returns pd.NA when no prose part is present.
    # ------------------------------------------------------------------
    prose_lengths: list[int] = []
    for part in ("objective", "what_changed", "why_it_matters", "risk_impact"):
        val = impact_summary.get(part)
        if not _is_missing(val) and isinstance(val, str):
            prose_lengths.append(len(val))
    # key_requirements: join non-empty items into a single string for length check
    key_reqs_raw = impact_summary.get("key_requirements")
    if isinstance(key_reqs_raw, list):
        non_empty_reqs = [str(r) for r in key_reqs_raw if not _is_missing(r)]
        if non_empty_reqs:
            prose_lengths.append(len(" ".join(non_empty_reqs)))
    row["min_prose_len"] = min(prose_lengths) if prose_lengths else pd.NA

    # ------------------------------------------------------------------
    # Step 9: n_unparseable_dates (Phase 4 quality support column)
    # Count of critical date fields whose raw value was NON-empty but
    # does NOT parse to a valid date via pd.to_datetime(errors="coerce").
    # Only the 6 key date fields (not calendars, not other_dates) are checked.
    # ------------------------------------------------------------------
    _date_fields = [
        "effective_date",
        "compliance_date",
        "comment_deadline",
        "early_adoption_date",
        "updated_date",
        "pub_date_content",
    ]
    n_unparseable = 0
    for field in _date_fields:
        raw_val = critical_dates.get(field)
        # Only count when the raw value was non-empty (before empties→NA pass)
        if raw_val is not None and isinstance(raw_val, str) and raw_val.strip() != "":
            lower = raw_val.strip().lower()
            if lower not in PLACEHOLDERS:
                # Non-empty and not a placeholder → try to parse.
                # Suppress format-ambiguity UserWarnings (we coerce on failure,
                # the warnings are about ambiguous day/month order, not failures).
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    parsed = pd.to_datetime(raw_val, errors="coerce")
                if pd.isna(parsed):
                    n_unparseable += 1
    row["n_unparseable_dates"] = n_unparseable

    # ------------------------------------------------------------------
    # Step 10: ensure every NORMALIZED_COLUMN is present (fill any gaps)
    # ------------------------------------------------------------------
    for col in schema.NORMALIZED_COLUMNS:
        if col not in row:
            row[col] = pd.NA

    return row


# ---------------------------------------------------------------------------
# Public: batch normalization + category join
# ---------------------------------------------------------------------------


def normalize_frame(
    records: Iterable[dict],
    categories: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize many envelopes into a DataFrame with exactly NORMALIZED_COLUMNS.

    After normalization, `category` is filled by a left-join from `categories`
    on `topic_id`.  Topics absent from `categories` receive ``"Uncategorized"``.

    Parameters
    ----------
    records:
        Iterable of raw envelope dicts (e.g. from ``ingest.load_snapshot``).
    categories:
        DataFrame with at least two columns: ``topic_id`` and ``category``
        (as produced by ``tools/pull_stratified.py``).

    Returns
    -------
    pd.DataFrame
        Exactly ``schema.NORMALIZED_COLUMNS`` columns, one row per record.
    """
    rows = [normalize_record(raw) for raw in records]
    if not rows:
        df = pd.DataFrame(columns=schema.NORMALIZED_COLUMNS)
        return df

    df = pd.DataFrame(rows, columns=schema.NORMALIZED_COLUMNS)

    # Left-join category from the catalog mapping on topic_id.
    # The `category` column was set to pd.NA by normalize_record; drop it
    # and re-add from the join.
    if "topic_id" in df.columns and not categories.empty:
        cat_map = (
            categories[["topic_id", "category"]]
            .drop_duplicates(subset="topic_id")
            .set_index("topic_id")["category"]
        )
        df["category"] = df["topic_id"].map(cat_map).fillna("Uncategorized")
    else:
        df["category"] = "Uncategorized"

    # Restore column order (map may have moved category)
    df = df[schema.NORMALIZED_COLUMNS]

    return df
