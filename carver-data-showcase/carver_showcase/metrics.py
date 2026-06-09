"""Audience-neutral aggregation metrics for the Carver Annotation Data Showcase.

All functions operate on the normalized DataFrame produced by load.load_normalized.
This is the SINGLE SOURCE OF TRUTH for all coverage %, score distributions, breadth
counts, and temporal metrics. Both apps (gallery and cockpit) MUST read from here so
the two can never disagree.

Public functions
----------------
coverage_matrix(df, slice_by=None) -> DataFrame
score_distributions(df) -> dict
breadth_summary(df) -> dict
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

import datetime
from typing import Optional

import pandas as pd

from carver_showcase.config import PLAUSIBLE_DATE_WINDOW


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


def breadth_summary(df: pd.DataFrame) -> dict:
    """Compute distinct-count breadth metrics and per-category record counts.

    Returns
    -------
    dict with keys:
        n_topics, n_countries, n_blocs, n_scopes, n_regulators, n_update_types,
        category_counts (dict of category → count)
    """
    def _nunique(col: str) -> int:
        if col not in df.columns:
            return 0
        return int(df[col].dropna().nunique())

    category_counts: dict = {}
    if "category" in df.columns:
        category_counts = df["category"].dropna().value_counts().to_dict()

    return {
        "n_topics": _nunique("topic_id"),
        "n_countries": _nunique("jurisdiction_country"),
        "n_blocs": _nunique("jurisdiction_bloc"),
        "n_scopes": _nunique("jurisdiction_scope"),
        "n_regulators": _nunique("regulator_name"),
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
    """Compute earliest/latest plausible date, span, and recency distribution.

    Implausible dates (outside config.PLAUSIBLE_DATE_WINDOW) are EXCLUDED from all
    computations — including the earliest date, latest date, and span. The garbage
    extremes (1947-12-25 / 2105-07-01 observed in the real snapshot) must NEVER define
    the advertised historical depth.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.

    Returns
    -------
    dict with keys:
        earliest_date  (datetime.date or None)
        latest_date    (datetime.date or None)
        span_days      (int or None)
        n_plausible    (int — records with plausible dates)
        n_implausible  (int — records with dates outside the window)
        recency        (dict with pct_1y, pct_3y, pct_7y as float 0–1)

    Notes
    -----
    Recency percentages are computed as fractions of all PLAUSIBLE records (rows
    with implausible or NA dates are excluded from the denominator).
    """
    date_col = "reconciled_published_date"
    if date_col not in df.columns:
        return {
            "earliest_date": None,
            "latest_date": None,
            "span_days": None,
            "n_plausible": 0,
            "n_implausible": 0,
            "recency": {"pct_1y": 0.0, "pct_3y": 0.0, "pct_7y": 0.0},
        }

    dates = _ensure_utc(df[date_col].copy())

    plausible_mask = _plausible_mask(dates)
    plausible_dates = dates[plausible_mask]
    n_plausible = int(plausible_mask.sum())
    n_implausible = int(dates.notna().sum()) - n_plausible

    if n_plausible == 0:
        return {
            "earliest_date": None,
            "latest_date": None,
            "span_days": None,
            "n_plausible": 0,
            "n_implausible": n_implausible,
            "recency": {"pct_1y": 0.0, "pct_3y": 0.0, "pct_7y": 0.0},
        }

    earliest_ts = plausible_dates.min()
    latest_ts = plausible_dates.max()
    earliest_date = earliest_ts.date()
    latest_date = latest_ts.date()
    span_days = (latest_ts - earliest_ts).days

    # Recency buckets relative to today
    today = pd.Timestamp(datetime.date.today(), tz="UTC")
    cutoff_1y = today - pd.DateOffset(years=1)
    cutoff_3y = today - pd.DateOffset(years=3)
    cutoff_7y = today - pd.DateOffset(years=7)

    pct_1y = float((plausible_dates >= cutoff_1y).sum()) / n_plausible
    pct_3y = float((plausible_dates >= cutoff_3y).sum()) / n_plausible
    pct_7y = float((plausible_dates >= cutoff_7y).sum()) / n_plausible

    return {
        "earliest_date": earliest_date,
        "latest_date": latest_date,
        "span_days": span_days,
        "n_plausible": n_plausible,
        "n_implausible": n_implausible,
        "recency": {
            "pct_1y": pct_1y,
            "pct_3y": pct_3y,
            "pct_7y": pct_7y,
        },
    }
