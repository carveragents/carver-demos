"""Cockpit logic: per-record quality predicates, anomaly rules, and cleanup queue.

Public functions
----------------
predicate_flags(df) -> pd.DataFrame
    Boolean column per quality predicate (9 predicates, spec §5.3).

anomaly_report(df) -> dict
    Per anomaly rule (11 rules) → {rule: {"count": int, "records": DataFrame}}.

cleanup_queue(df, predicates=None) -> pd.DataFrame
    Rows failing ≥1 predicate; includes artifact_id, failed_predicates list,
    key offending fields, and feed_url for triage.

Design notes
------------
- Deterministic: NO LLM, no randomness, no network.
- Regulator canonicalization: pure string ops (lowercase, strip punctuation/
  whitespace, drop common legal suffixes) — fuzzy/semantic dedup is v2 (§10).
- Cross-row anomalies (duplicate_entry_id, regulator_near_duplicate) are computed
  over the FULL supplied frame, not per-filter subsets (spec R8).
- Label/score band check treats high as inclusive of 10 (spec A2).
- Date order check: comment_deadline > effective_date OR
  compliance_date < effective_date (when both dates are present and parseable).
"""

from __future__ import annotations

import re
import warnings
from typing import Optional

import pandas as pd

from carver_showcase.config import (
    CONFIDENCE_RANGE,
    ISO_COUNTRY,
    LABEL_BANDS,
    MIN_PROSE_CHARS,
    PLAUSIBLE_DATE_WINDOW,
    RARE_UPDATE_TYPE_CUTOFF,
    SCORE_RANGE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_na(val) -> bool:
    """Return True if val is None, pd.NA, NaN, or an NA-typed scalar."""
    if val is None:
        return True
    try:
        return bool(pd.isna(val))
    except (TypeError, ValueError):
        return False


def _canonicalize_regulator(name: str) -> str:
    """Deterministic canonicalization for regulator near-duplicate detection.

    Steps:
    1. Lowercase
    2. Remove all punctuation (dots, commas, hyphens, apostrophes, etc.)
       so abbreviation dots are stripped rather than replaced with spaces
       (e.g. "U.S." → "us", not "u s")
    3. Strip common legal-suffix tokens (inc, ltd, limited, authority, plc, llp,
       llc, corp, corporation, company, co, association, board, commission,
       office, bureau, agency, department, ministry, service, services)
    4. Collapse whitespace
    """
    if _is_na(name):
        return ""
    s = str(name).lower().strip()

    # Remove all punctuation characters (replace with nothing, not space)
    # so that "U.S." → "us" and not "u s"
    s = re.sub(r"[^\w\s]", "", s)

    # Remove legal/institutional suffixes (word-boundary)
    legal_suffixes = (
        r"\b(inc|ltd|limited|llp|llc|plc|corp|corporation|"
        r"company|co|association|board|commission|office|bureau|"
        r"agency|department|ministry|authority|service|services|"
        r"committee|council|division)\b"
    )
    s = re.sub(legal_suffixes, "", s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Public alias — stable API for app-layer consumers (cockpit 7.4 field-health),
# so apps don't reach into the underscore-private helper.
canonicalize_regulator = _canonicalize_regulator


def _parse_date_col(series: pd.Series) -> pd.Series:
    """Try to parse a string column as dates; return a datetime Series (NaT for failures).

    UserWarnings about ambiguous date formats are suppressed — errors="coerce" handles
    unparseable values; format ambiguity warnings are not actionable here.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(series, errors="coerce", utc=True)


# ---------------------------------------------------------------------------
# Public: predicate_flags
# ---------------------------------------------------------------------------

# The 9 predicate names in the order they appear in the output DataFrame
PREDICATE_COLUMNS = [
    "missing_core_score",
    "missing_join_key",
    "missing_feed_url",
    "missing_jurisdiction_country",
    "missing_update_type",
    "no_impact_summary",
    "short_prose",
    "no_actionables",
    "empty_but_expected",
]


def predicate_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Compute one boolean column per quality predicate.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.

    Returns
    -------
    pd.DataFrame
        Boolean DataFrame with exactly the 9 PREDICATE_COLUMNS, same row index as df.
    """
    flags: dict[str, pd.Series] = {}

    # 1. missing_core_score: any of the 9 score/label/confidence fields is NA
    score_fields = [
        "impact_label", "impact_score", "impact_confidence",
        "urgency_label", "urgency_score", "urgency_confidence",
        "relevance_label", "relevance_score", "relevance_confidence",
    ]
    missing_core = pd.Series(False, index=df.index)
    for col in score_fields:
        if col in df.columns:
            missing_core = missing_core | df[col].isna()
    flags["missing_core_score"] = missing_core

    # 2. missing_join_key: topic_id or entry_id is NA
    flags["missing_join_key"] = df["topic_id"].isna() | df["entry_id"].isna()

    # 3. missing_feed_url: feed_url is NA
    flags["missing_feed_url"] = df["feed_url"].isna()

    # 4. missing_jurisdiction_country: jurisdiction_country is NA
    flags["missing_jurisdiction_country"] = df["jurisdiction_country"].isna()

    # 5. missing_update_type: update_type is NA
    flags["missing_update_type"] = df["update_type"].isna()

    # 6. no_impact_summary: has_impact_summary is False (all 5 parts missing)
    flags["no_impact_summary"] = ~df["has_impact_summary"].fillna(False).astype(bool)

    # 7. short_prose: has_impact_summary AND min_prose_len < MIN_PROSE_CHARS
    has_summary = df["has_impact_summary"].fillna(False).astype(bool)
    if "min_prose_len" in df.columns:
        min_len = pd.to_numeric(df["min_prose_len"], errors="coerce")
        short = has_summary & min_len.notna() & (min_len < MIN_PROSE_CHARS)
    else:
        short = pd.Series(False, index=df.index)
    flags["short_prose"] = short

    # 8. no_actionables: n_actionable_lanes == 0
    flags["no_actionables"] = (df["n_actionable_lanes"].fillna(0) == 0)

    # 9. empty_but_expected: high impact OR high relevance label,
    #    but no_impact_summary OR no_actionables
    high_impact_or_relevance = (
        (df["impact_label"].fillna("").str.lower() == "high")
        | (df["relevance_label"].fillna("").str.lower() == "high")
    )
    no_summary = flags["no_impact_summary"]
    no_action = flags["no_actionables"]
    flags["empty_but_expected"] = high_impact_or_relevance & (no_summary | no_action)

    result = pd.DataFrame(flags, index=df.index)
    # Ensure all predicate columns are boolean dtype
    for col in PREDICATE_COLUMNS:
        result[col] = result[col].astype(bool)

    return result[PREDICATE_COLUMNS]


# ---------------------------------------------------------------------------
# Public: anomaly_report
# ---------------------------------------------------------------------------


def anomaly_report(df: pd.DataFrame) -> dict[str, dict]:
    """Compute all 11 anomaly/consistency rules over the full frame.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame. Cross-row rules (duplicate_entry_id,
        regulator_near_duplicate) are computed over this full frame.

    Returns
    -------
    dict
        Keys are rule names (11 total). Values are dicts with:
        - ``"count"``: int — number of offending rows
        - ``"records"``: pd.DataFrame — the offending rows (or empty DataFrame)
    """
    report: dict[str, dict] = {}

    def _result(mask: pd.Series) -> dict:
        records = df[mask]
        return {"count": int(mask.sum()), "records": records}

    # ------------------------------------------------------------------
    # 1. score_out_of_range: any score ∉ [0,10] or confidence ∉ [0,1]
    # ------------------------------------------------------------------
    out_of_range = pd.Series(False, index=df.index)
    for score_col in ["impact_score", "urgency_score", "relevance_score"]:
        if score_col in df.columns:
            s = pd.to_numeric(df[score_col], errors="coerce")
            out_of_range |= s.notna() & ~((s >= SCORE_RANGE[0]) & (s <= SCORE_RANGE[1]))
    for conf_col in ["impact_confidence", "urgency_confidence", "relevance_confidence"]:
        if conf_col in df.columns:
            c = pd.to_numeric(df[conf_col], errors="coerce")
            out_of_range |= c.notna() & ~((c >= CONFIDENCE_RANGE[0]) & (c <= CONFIDENCE_RANGE[1]))
    report["score_out_of_range"] = _result(out_of_range)

    # ------------------------------------------------------------------
    # 2. label_score_mismatch: a score's label disagrees with its band (A2)
    #    high-inclusive treatment: band_for_score uses inclusive [7,10] for high
    # ------------------------------------------------------------------
    low_lo, low_hi = LABEL_BANDS["low"]
    med_lo, med_hi = LABEL_BANDS["medium"]
    high_lo, high_hi = LABEL_BANDS["high"]
    mismatch = pd.Series(False, index=df.index)
    for axis in ["impact", "urgency", "relevance"]:
        label_col = f"{axis}_label"
        score_col = f"{axis}_score"
        if label_col not in df.columns or score_col not in df.columns:
            continue
        labels = df[label_col].fillna("").str.lower()
        scores = pd.to_numeric(df[score_col], errors="coerce")
        # Vectorized band assignment (NA where the score is NA or out of range;
        # high is inclusive of its upper bound — spec A2).
        band = pd.Series(pd.NA, index=df.index, dtype="object")
        band[(scores >= low_lo) & (scores < low_hi)] = "low"
        band[(scores >= med_lo) & (scores < med_hi)] = "medium"
        band[(scores >= high_lo) & (scores <= high_hi)] = "high"
        # Mismatch only where both label and score are present AND the in-range
        # band disagrees with the stored label (out-of-range → score_out_of_range).
        both_present = (labels.str.len() > 0) & scores.notna()
        axis_mismatch = both_present & band.notna() & (labels != band)
        mismatch |= axis_mismatch.fillna(False).astype(bool)
    report["label_score_mismatch"] = _result(mismatch)

    # ------------------------------------------------------------------
    # 3. date_order_inconsistency:
    #    comment_deadline > effective_date (deadline after effective) — illogical
    #    compliance_date < effective_date (compliance before effective) — illogical
    # ------------------------------------------------------------------
    date_inconsistent = pd.Series(False, index=df.index)
    if "comment_deadline" in df.columns and "effective_date" in df.columns:
        cd = _parse_date_col(df["comment_deadline"])
        ed = _parse_date_col(df["effective_date"])
        both = cd.notna() & ed.notna()
        date_inconsistent |= both & (cd > ed)
    if "compliance_date" in df.columns and "effective_date" in df.columns:
        comp = _parse_date_col(df["compliance_date"])
        ed = _parse_date_col(df["effective_date"])
        both = comp.notna() & ed.notna()
        date_inconsistent |= both & (comp < ed)
    report["date_order_inconsistency"] = _result(date_inconsistent)

    # ------------------------------------------------------------------
    # 4. implausible_pub_date: reconciled_published_date ∉ PLAUSIBLE_DATE_WINDOW
    # ------------------------------------------------------------------
    if "reconciled_published_date" in df.columns:
        rpd = pd.to_datetime(df["reconciled_published_date"], errors="coerce", utc=True)
        start = pd.Timestamp(PLAUSIBLE_DATE_WINDOW[0], tz="UTC")
        end = pd.Timestamp(PLAUSIBLE_DATE_WINDOW[1], tz="UTC")
        implausible = rpd.notna() & ~((rpd >= start) & (rpd <= end))
    else:
        implausible = pd.Series(False, index=df.index)
    report["implausible_pub_date"] = _result(implausible)

    # ------------------------------------------------------------------
    # 5. invalid_reconciled_date: reconciled_pub_valid == False
    # ------------------------------------------------------------------
    if "reconciled_pub_valid" in df.columns:
        valid_col = df["reconciled_pub_valid"]
        # reconciled_pub_valid is boolean; NA means unknown → not flagged
        invalid_rdate = valid_col.notna() & (valid_col == False)  # noqa: E712
    else:
        invalid_rdate = pd.Series(False, index=df.index)
    report["invalid_reconciled_date"] = _result(invalid_rdate)

    # ------------------------------------------------------------------
    # 6. duplicate_entry_id: entry_id occurs >1× in the full frame
    # ------------------------------------------------------------------
    if "entry_id" in df.columns:
        dup_mask = df["entry_id"].notna() & df["entry_id"].duplicated(keep=False)
    else:
        dup_mask = pd.Series(False, index=df.index)
    report["duplicate_entry_id"] = _result(dup_mask)

    # ------------------------------------------------------------------
    # 7. invalid_jurisdiction_country: non-NA country not in ISO_COUNTRY
    # ------------------------------------------------------------------
    if "jurisdiction_country" in df.columns:
        country = df["jurisdiction_country"]
        non_na = country.notna()
        not_in_iso = ~country.isin(set(ISO_COUNTRY.keys()))
        invalid_country = non_na & not_in_iso
    else:
        invalid_country = pd.Series(False, index=df.index)
    report["invalid_jurisdiction_country"] = _result(invalid_country)

    # ------------------------------------------------------------------
    # 8. residual_legacy_field: has_jurisdiction_tier_legacy == True
    # ------------------------------------------------------------------
    if "has_jurisdiction_tier_legacy" in df.columns:
        legacy = df["has_jurisdiction_tier_legacy"].fillna(False).astype(bool)
    else:
        legacy = pd.Series(False, index=df.index)
    report["residual_legacy_field"] = _result(legacy)

    # ------------------------------------------------------------------
    # 9. update_type_rare: snapshot freq < RARE_UPDATE_TYPE_CUTOFF
    # ------------------------------------------------------------------
    if "update_type" in df.columns:
        type_counts = df["update_type"].value_counts()
        rare_types = type_counts[type_counts < RARE_UPDATE_TYPE_CUTOFF].index
        rare_mask = df["update_type"].isin(rare_types)
    else:
        rare_mask = pd.Series(False, index=df.index)
    report["update_type_rare"] = _result(rare_mask)

    # ------------------------------------------------------------------
    # 10. regulator_near_duplicate: regulator_name rows whose canonical form
    #     collapses with ≥1 other distinct raw name
    # ------------------------------------------------------------------
    if "regulator_name" in df.columns:
        non_na_mask = df["regulator_name"].notna()
        non_na_df = df[non_na_mask]

        if non_na_df.empty:
            near_dup_mask = pd.Series(False, index=df.index)
        else:
            canonical = non_na_df["regulator_name"].apply(_canonicalize_regulator)
            # For each canonical form, collect the set of distinct raw names
            # A canonical form triggers near-dup only when ≥2 distinct raw names map to it
            canon_to_raw: dict[str, set] = {}
            for idx, (raw_name, canon_name) in enumerate(
                zip(non_na_df["regulator_name"], canonical)
            ):
                if canon_name not in canon_to_raw:
                    canon_to_raw[canon_name] = set()
                canon_to_raw[canon_name].add(raw_name)

            # A canonical form is a near-dup group when it has ≥2 distinct raw names
            near_dup_canons = {
                c for c, raws in canon_to_raw.items() if len(raws) >= 2
            }
            near_dup_mask_non_na = canonical.isin(near_dup_canons)
            near_dup_mask = pd.Series(False, index=df.index)
            near_dup_mask.loc[non_na_df.index] = near_dup_mask_non_na.values
    else:
        near_dup_mask = pd.Series(False, index=df.index)
    report["regulator_near_duplicate"] = _result(near_dup_mask)

    # ------------------------------------------------------------------
    # 11. unparseable_date: n_unparseable_dates > 0
    # ------------------------------------------------------------------
    if "n_unparseable_dates" in df.columns:
        n_unparseable = pd.to_numeric(df["n_unparseable_dates"], errors="coerce").fillna(0)
        unparseable_mask = n_unparseable > 0
    else:
        unparseable_mask = pd.Series(False, index=df.index)
    report["unparseable_date"] = _result(unparseable_mask)

    return report


# ---------------------------------------------------------------------------
# Public: cleanup_queue
# ---------------------------------------------------------------------------


def cleanup_queue(
    df: pd.DataFrame,
    predicates: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Return rows failing ≥1 quality predicate, with triage metadata.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.
    predicates:
        Optional list of predicate names to filter by. If None, all 9 predicates
        are used. Rows must fail ≥1 of the specified predicates to appear.

    Returns
    -------
    pd.DataFrame
        Columns: ``artifact_id``, ``failed_predicates`` (list of str),
        plus key offending fields and ``feed_url``.
        Rows are ordered by artifact_id for deterministic output.
    """
    flags = predicate_flags(df)

    if predicates is not None:
        # Filter to specified predicates (ignore unknown names)
        active = [p for p in predicates if p in flags.columns]
        if not active:
            return pd.DataFrame(columns=["artifact_id", "failed_predicates", "feed_url"])
        flags = flags[active]

    # A row is in the queue when it fails ≥1 predicate
    any_fail = flags.any(axis=1)
    failing_df = df[any_fail].copy()

    if failing_df.empty:
        return pd.DataFrame(columns=["artifact_id", "failed_predicates", "feed_url"])

    failing_flags = flags[any_fail]

    # Build the failed_predicates list for each row
    def _failed_list(row: pd.Series) -> list[str]:
        return [col for col in row.index if row[col]]

    failed_predicates = failing_flags.apply(_failed_list, axis=1)

    # Key offending fields for triage context
    key_fields = [
        col for col in [
            "artifact_id",
            "entry_id",
            "topic_id",
            "feed_url",
            "jurisdiction_country",
            "update_type",
            "regulator_name",
            "impact_label",
            "impact_score",
            "has_impact_summary",
            "n_actionable_lanes",
            "min_prose_len",
            "n_unparseable_dates",
        ]
        if col in df.columns
    ]

    result = failing_df[key_fields].copy()
    result.insert(
        result.columns.get_loc("artifact_id") + 1,
        "failed_predicates",
        failed_predicates.values,
    )

    return result.sort_values("artifact_id").reset_index(drop=True)
