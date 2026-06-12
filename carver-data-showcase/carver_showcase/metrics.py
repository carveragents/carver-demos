"""Audience-neutral aggregation metrics for the Carver Annotation Data Showcase.

All functions operate on the normalized DataFrame produced by load.load_normalized.
This is the SINGLE SOURCE OF TRUTH for all coverage %, score distributions, breadth
counts, and temporal metrics. Both apps (gallery and cockpit) MUST read from here so
the two can never disagree.

Public functions
----------------
coverage_matrix(df, slice_by=None) -> DataFrame
score_distributions(df) -> dict
breadth_summary(df, regulator_canon=None) -> dict
volume_over_time(df, freq, exclude_implausible) -> DataFrame
historical_depth(df) -> dict

Design notes
------------
- Deterministic: no LLM, no randomness, no network.
- "Honest" coverage: a value is present only when notna() — an empty string turned
  into pd.NA during normalize already counts as missing here.
- Implausible dates are handled via config.PLAUSIBLE_DATE_WINDOW throughout.
"""

from __future__ import annotations

import collections
import datetime
from typing import Optional

import pandas as pd

from carver_showcase.config import (
    HISTORICAL_DEPTH_FLOOR_QUANTILE,
    PLAUSIBLE_DATE_WINDOW,
    RECENCY_WINDOWS_YEARS,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _plausible_mask(series: pd.Series) -> pd.Series:
    """Return a boolean mask of rows whose datetime value is within PLAUSIBLE_DATE_WINDOW."""
    low = pd.Timestamp(PLAUSIBLE_DATE_WINDOW[0], tz="UTC")
    high = pd.Timestamp(PLAUSIBLE_DATE_WINDOW[1], tz="UTC")
    return series.notna() & (series >= low) & (series <= high)


def _ensure_utc(series: pd.Series) -> pd.Series:
    """Ensure a datetime Series has UTC timezone (coerce to UTC if naive or tz-aware)."""
    if series.isna().all():
        return series
    if hasattr(series.dtype, "tz") and series.dtype.tz is not None:
        return series.dt.tz_convert("UTC")
    try:
        return pd.to_datetime(series, utc=True, errors="coerce")
    except Exception:
        return series


# Public aliases — stable date helpers for app-layer consumers (e.g. cockpit 7.6),
# so apps don't reach into underscore-private internals.
plausible_date_mask = _plausible_mask
ensure_utc = _ensure_utc


# ---------------------------------------------------------------------------
# coverage_matrix
# ---------------------------------------------------------------------------


def coverage_matrix(df: pd.DataFrame, slice_by: Optional[str] = None) -> pd.DataFrame:
    """Compute field population percentage overall and (optionally) sliced.

    Parameters
    ----------
    df:
        The normalized annotations DataFrame.
    slice_by:
        If given, also compute per-slice coverage for the unique values of this
        column (e.g. ``"category"``, ``"update_type"``, ``"jurisdiction_country"``).
        The overall column is always included.

    Returns
    -------
    pd.DataFrame
        Rows = fields, with at least a ``pct`` column (float, 0–1) for the
        overall population rate.  If ``slice_by`` is given, additional columns
        are added for each slice value.

    Notes
    -----
    - A field is "populated" only when ``notna()`` after the empties→NA pass
      already applied during normalize.
    - Fields that are boolean flags are included; constant-True flags (e.g.
      has_jurisdiction_tier_legacy = False for all) can still show real coverage.
    """
    n = len(df)
    if n == 0:
        return pd.DataFrame(columns=["field", "pct"])

    def _population_pct(frame: pd.DataFrame) -> pd.Series:
        """Per-column population rate.

        For boolean-dtype columns (``has_*`` flags), the "population" is the
        rate of True values — a False flag means the underlying data is absent,
        so it correctly counts as missing.  For all other columns, population is
        the rate of non-NA values (the standard empties→NA coverage rule).
        """
        pcts = {}
        for col in frame.columns:
            col_series = frame[col]
            if str(col_series.dtype) in ("boolean", "bool"):
                # Boolean flag: population = fraction of True rows
                n_total = len(col_series)
                pcts[col] = float(col_series.eq(True).sum()) / n_total if n_total > 0 else 0.0
            else:
                pcts[col] = float(col_series.notna().mean())
        return pd.Series(pcts)

    overall_pct = _population_pct(df)

    result = pd.DataFrame({"field": overall_pct.index, "pct": overall_pct.values})
    result = result.set_index("field")

    if slice_by is not None and slice_by in df.columns:
        slice_values = df[slice_by].dropna().unique()
        for val in sorted(slice_values):
            subset = df[df[slice_by] == val]
            if len(subset) == 0:
                result[str(val)] = 0.0
            else:
                result[str(val)] = _population_pct(subset)

    return result


# ---------------------------------------------------------------------------
# score_distributions
# ---------------------------------------------------------------------------


def score_distributions(df: pd.DataFrame) -> dict:
    """Compute histogram / bucket data for impact, urgency, and relevance scores.

    Returns
    -------
    dict
        Keys: ``"impact"``, ``"urgency"``, ``"relevance"``.
        Each value is a dict containing:
        - ``"scores"``: list of score values (non-NA)
        - ``"confidence"``: list of confidence values (non-NA)
        - ``"confidence_values"``: alias for "confidence" (for test compatibility)
        - ``"label_counts"``: dict of label → count (non-NA labels)
        - ``"labels"``: alias for "label_counts"
    """
    axes = ("impact", "urgency", "relevance")
    result: dict = {}

    for axis in axes:
        score_col = f"{axis}_score"
        conf_col = f"{axis}_confidence"
        label_col = f"{axis}_label"

        scores = df[score_col].dropna().tolist() if score_col in df.columns else []
        confidences = df[conf_col].dropna().tolist() if conf_col in df.columns else []
        label_counts: dict = {}
        if label_col in df.columns:
            label_counts = df[label_col].dropna().value_counts().to_dict()

        result[axis] = {
            "scores": scores,
            "confidence": confidences,
            "confidence_values": confidences,  # alias
            "label_counts": label_counts,
            "labels": label_counts,  # alias
        }

    return result


# ---------------------------------------------------------------------------
# breadth_summary
# ---------------------------------------------------------------------------


def breadth_summary(
    df: pd.DataFrame,
    regulator_canon: dict | None = None,
    min_regulator_mentions: int = 1,
) -> dict:
    """Compute distinct-count breadth metrics and per-category record counts.

    Parameters
    ----------
    df:
        The normalized annotations DataFrame.
    regulator_canon:
        Optional canonicalization mapping returned by
        ``load.load_regulator_canonical`` — shaped
        ``{raw_name: {"canonical": str, "is_regulator": bool, "key": str}}``.

        When ``None`` (default): ``n_regulators`` is computed as the plain
        distinct-count of ``regulator_name`` values, identical to previous
        behavior (``min_regulator_mentions`` is ignored in this path).

        When provided: ``n_regulators`` is the number of **distinct merge-keys
        among genuine regulators** in the DataFrame whose total row-count in
        ``df`` (summed across all raw name variants that share the same merge
        key) meets ``min_regulator_mentions``.  For each distinct non-null
        ``regulator_name`` value:

        - If the name is in the mapping and ``is_regulator`` is True: its
          ``key`` accumulates the name's row-count from ``df`` into a
          ``collections.Counter``.
        - If the name is in the mapping and ``is_regulator`` is False: it is
          **excluded** from the count (non-regulator entities are dropped).
        - If the name is **not** in the mapping (e.g. added after the last
          batch run): it is counted conservatively by using the raw name
          itself as the key, so no unmapped name is ever silently dropped;
          its row-count accumulates under the raw name.

        Only keys whose accumulated mention-count is ``>= min_regulator_mentions``
        are included in the final ``n_regulators`` tally.

        Because this operates on whatever ``df`` is passed in (the filtered
        view in the Gallery), the deduplicated count is automatically
        filter-aware with no extra work.

    min_regulator_mentions:
        Minimum number of row-count mentions a deduped body must have in ``df``
        to be counted in ``n_regulators``.  Defaults to ``1`` (no cutoff), which
        preserves the previous behaviour so all existing tests remain valid.
        Mentions are the ROW COUNT of each raw ``regulator_name`` variant in the
        passed ``df`` (filter-aware), summed across all variants that merge to
        the same canonical key.
        Ignored when ``regulator_canon`` is ``None``.

    Returns
    -------
    dict with keys:
        n_topics, n_countries, n_blocs, n_scopes, n_regulators, n_update_types,
        category_counts (dict of category → count), per_category (alias for
        category_counts)
    """
    def _nunique(col: str) -> int:
        if col not in df.columns:
            return 0
        return int(df[col].dropna().nunique())

    def _n_regulators_dedup(canon: dict, min_mentions: int) -> int:
        if "regulator_name" not in df.columns:
            return 0
        # Count how many times each raw name appears in df (row-count, not nunique).
        raw_counts = df["regulator_name"].dropna().value_counts()
        # Accumulate mention-counts per merge-key.
        counts: collections.Counter = collections.Counter()
        for raw, n in raw_counts.items():
            rec = canon.get(raw)
            if rec is None:
                # Unmapped name: conservative over-count — accumulate under the raw
                # name rather than dropping it, since we can't confirm it's a
                # non-regulator.
                counts[raw] += n
            elif rec.get("is_regulator", True):
                counts[rec["key"]] += n
            # else: is_regulator is False — skip (non-regulator entity).
        return sum(1 for c in counts.values() if c >= min_mentions)

    n_regulators = (
        _n_regulators_dedup(regulator_canon, min_regulator_mentions)
        if regulator_canon is not None
        else _nunique("regulator_name")
    )

    category_counts: dict = {}
    if "category" in df.columns:
        category_counts = df["category"].dropna().value_counts().to_dict()

    return {
        "n_topics": _nunique("topic_id"),
        "n_countries": _nunique("jurisdiction_country"),
        "n_blocs": _nunique("jurisdiction_bloc"),
        "n_scopes": _nunique("jurisdiction_scope"),
        "n_regulators": n_regulators,
        "n_update_types": _nunique("update_type"),
        "category_counts": category_counts,
        "per_category": category_counts,  # alias
    }


# ---------------------------------------------------------------------------
# volume_over_time
# ---------------------------------------------------------------------------


def volume_over_time(
    df: pd.DataFrame,
    freq: str = "ME",
    exclude_implausible: bool = True,
) -> pd.DataFrame:
    """Count annotations per time period bucketed by reconciled_published_date.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.
    freq:
        Pandas resample frequency string (default ``"ME"`` for month-end).
        Common values: ``"ME"`` (month-end), ``"QE"`` (quarter-end).
    exclude_implausible:
        If True (default), rows whose date falls outside
        ``config.PLAUSIBLE_DATE_WINDOW`` are excluded.

    Returns
    -------
    pd.DataFrame
        Columns: ``period`` (datetime), ``count`` (int).
    """
    date_col = "reconciled_published_date"
    if date_col not in df.columns:
        return pd.DataFrame(columns=["period", "count"])

    dates = _ensure_utc(df[date_col].copy())

    if exclude_implausible:
        mask = _plausible_mask(dates)
        dates = dates[mask]

    if dates.empty:
        return pd.DataFrame(columns=["period", "count"])

    series = pd.Series(1, index=dates, name="count")
    resampled = series.resample(freq).sum().reset_index()
    resampled.columns = ["period", "count"]
    # Drop periods with zero records (sparse months not in the data)
    resampled = resampled[resampled["count"] > 0].reset_index(drop=True)
    return resampled


# ---------------------------------------------------------------------------
# historical_depth
# ---------------------------------------------------------------------------


def historical_depth(df: pd.DataFrame) -> dict:
    """Compute the displayed earliest/latest date, span, and recency distribution.

    Two layers of date handling, kept deliberately separate:

    1. **Anomaly window** (``config.PLAUSIBLE_DATE_WINDOW``): garbage extremes outside
       it (e.g. 1442-07-01 / 2569-04-30 observed in the real corpus) are excluded from
       every computation here and counted as ``n_implausible``.
    2. **Display floor** (``config.HISTORICAL_DEPTH_FLOOR_QUANTILE``, default 1%): the
       advertised ``earliest_date`` is the low quantile of the in-window dates, NOT the
       hard minimum, so an ultra-sparse tail of very old (but in-window) records doesn't
       define the headline span. The true minimum is still reported as
       ``true_earliest_date`` for honesty, and the records below the floor are counted in
       ``n_below_floor``. ``latest_date`` remains the true in-window maximum.

    A robust quantile (not mean±σ) is used because the date distribution is a heavily
    right-loaded spike (median ≈ now, skew ≈ -4), where moments are not meaningful and a
    σ-based floor would both drift on every refresh and mis-trim a skewed tail.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.

    Returns
    -------
    dict with keys:
        earliest_date       (datetime.date or None — the display floor, low quantile)
        true_earliest_date  (datetime.date or None — the actual in-window minimum)
        latest_date         (datetime.date or None — the in-window maximum)
        span_days           (int or None — latest_date − earliest_date)
        floor_quantile      (float — the quantile used for earliest_date)
        n_plausible         (int — records with in-window dates)
        n_below_floor       (int — in-window records older than the display floor)
        n_implausible       (int — records with dates outside the window)
        recency             (dict with pct_<N>y for each N in
                             config.RECENCY_WINDOWS_YEARS, as float 0–1)

    Notes
    -----
    Recency percentages are computed as fractions of all PLAUSIBLE (in-window) records;
    rows with implausible or NA dates are excluded from the denominator. They are not
    affected by the display floor.
    """
    empty = {
        "earliest_date": None,
        "true_earliest_date": None,
        "latest_date": None,
        "span_days": None,
        "floor_quantile": HISTORICAL_DEPTH_FLOOR_QUANTILE,
        "n_plausible": 0,
        "n_below_floor": 0,
        "n_implausible": 0,
        "recency": {f"pct_{y}y": 0.0 for y in RECENCY_WINDOWS_YEARS},
    }

    date_col = "reconciled_published_date"
    if date_col not in df.columns:
        return dict(empty)

    dates = _ensure_utc(df[date_col].copy())

    plausible_mask = _plausible_mask(dates)
    plausible_dates = dates[plausible_mask]
    n_plausible = int(plausible_mask.sum())
    n_implausible = int(dates.notna().sum()) - n_plausible

    if n_plausible == 0:
        return {**empty, "n_implausible": n_implausible}

    # Display floor: low quantile of in-window dates (robust to the sparse old tail).
    floor_ts = plausible_dates.quantile(HISTORICAL_DEPTH_FLOOR_QUANTILE)
    true_earliest_ts = plausible_dates.min()
    latest_ts = plausible_dates.max()

    earliest_date = floor_ts.date()
    true_earliest_date = true_earliest_ts.date()
    latest_date = latest_ts.date()
    span_days = (latest_ts - floor_ts).days
    n_below_floor = int((plausible_dates < floor_ts).sum())

    # Recency buckets relative to today (over ALL plausible records; floor-independent).
    # Share of dated records within the last N years for each configured window.
    today = pd.Timestamp(datetime.date.today(), tz="UTC")
    recency = {
        f"pct_{years}y": float(
            (plausible_dates >= today - pd.DateOffset(years=years)).sum()
        )
        / n_plausible
        for years in RECENCY_WINDOWS_YEARS
    }

    return {
        "earliest_date": earliest_date,
        "true_earliest_date": true_earliest_date,
        "latest_date": latest_date,
        "span_days": span_days,
        "floor_quantile": HISTORICAL_DEPTH_FLOOR_QUANTILE,
        "n_plausible": n_plausible,
        "n_below_floor": n_below_floor,
        "n_implausible": n_implausible,
        "recency": recency,
    }
