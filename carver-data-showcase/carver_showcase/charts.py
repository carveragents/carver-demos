"""Shared Plotly figure builders — the single source of truth for every chart.

This module is the keystone that keeps the **downloadable deck in sync with the
website**: both ``apps/gallery.py`` and ``carver_showcase/deck.py`` build their
charts from these functions, so the deck can never silently drift from the
gallery.  Numbers still come from ``carver_showcase.metrics`` (the single source
of truth for aggregates); this module is the single source of truth for how
those aggregates are *drawn*.

Design constraints
------------------
- **No Streamlit, no kaleido** — pure ``pandas`` + ``plotly`` + ``config`` +
  ``metrics``.  Unit-testable in isolation; importable by the library layer.
- Every builder returns a ``plotly.graph_objects.Figure`` and is defensive: when
  the relevant column is missing or empty it returns a small valid "no data"
  figure rather than raising, so neither the gallery nor the deck crashes on a
  thin slice.
- Builders take the (already-filtered) DataFrame the caller wants drawn.  The
  gallery passes its filtered ``view``; the deck passes the full unfiltered
  frame.  "Match the website with no filters" therefore falls out for free.
- Chart type / title / palette / labels are copied verbatim from the gallery so
  the refactor is behaviour-preserving.

Prep helpers (``geo_country_counts``, ``inst_country_counts``,
``update_type_counts``) return the derived frames/Series the gallery also needs
for its captions, so the caption numbers and the chart can't disagree.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from carver_showcase.config import (
    AXIS_COLORS,
    CARVER_CHARCOAL,
    CARVER_GREEN_DEEP,
    CARVER_HONEYDEW,
    CARVER_LIME,
    CARVER_QUALITATIVE,
    ENTITY_LEADERBOARD_TOP_N,
    ENTITY_TYPE_COLORS,
    INSTITUTION_DOMAIN_TAXONOMY,
    ISO_COUNTRY,
    LABEL_BANDS,
    REGULATOR_LEADERBOARD_TOP_N,
    SCORE_AXES,
    TAG_LEADERBOARD_TOP_N,
)
from carver_showcase.metrics import (
    historical_depth,
    score_distributions,
    volume_over_time,
)

# Continuous palette used by every count-coloured chart (choropleths, sunburst).
# Carver-brand green ramp: pale honeydew → lime → deep green (monotonic in
# lightness, so it reads as a proper sequential scale).
SEQUENTIAL_SCALE = [
    [0.0, CARVER_HONEYDEW],
    [0.5, CARVER_LIME],
    [1.0, CARVER_GREEN_DEEP],
]

# Neutral fill for single-series "data" bars (volume, recency, leaderboards,
# update-types) — brand charcoal keeps lime free as the accent colour.
BAR_FILL = CARVER_CHARCOAL

# One fixed colour per top-level institution domain, assigned in taxonomy order
# from the brand qualitative palette (Finance, the largest, leads with lime).
# Shared by the domain sunburst AND the top-level domain bar so a domain reads
# as the same colour across both charts.
DOMAIN_COLOR_MAP: dict[str, str] = {
    top_level: CARVER_QUALITATIVE[i % len(CARVER_QUALITATIVE)]
    for i, top_level in enumerate(INSTITUTION_DOMAIN_TAXONOMY)
}

# Display labels for the volume-over-time frequency codes.
FREQ_LABELS: dict[str, str] = {
    "ME": "Monthly (ME)",
    "QE": "Quarterly (QE)",
    "YE": "Yearly (YE)",
}
# resample-code → period alias for START-of-bucket anchoring (fixes the
# off-by-one where resample labels a bucket by its end).
_PERIOD_ALIAS: dict[str, str] = {"ME": "M", "QE": "Q", "YE": "Y"}


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _empty_fig(message: str = "No data") -> go.Figure:
    """A valid, blank figure carrying a centered message (never raises)."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=16, color="#888"),
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


def rollup_country(code) -> str | None:
    """ISO-2 parent country for an institution ``jurisdiction_code``.

    Rolls subdivisions up to their parent country ("US-CA" → "US").  Returns
    ``None`` for placeholders ("-"), multi-country / EU-wide strings, and any
    code whose prefix is not a recognised ISO-2 country.
    """
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return None
    code = str(code)
    if code in ISO_COUNTRY:
        return code
    prefix = code.split("-")[0].strip()
    return prefix if prefix in ISO_COUNTRY else None


# ---------------------------------------------------------------------------
# Log-scaled choropleth (shared by both world maps)
#
# Country record/institution counts are extremely right-skewed — the US alone
# is ~40% of all records and ~300x the median country — so a *linear* colour
# ramp pins the US at full saturation and crushes every other country into the
# bottom decile of the palette (visually invisible).  Colouring on log10(count)
# spreads the long tail across the full palette while keeping the US darkest;
# the colorbar is relabelled in real counts so the legend stays readable.
# ---------------------------------------------------------------------------


def _human_count(n: float) -> str:
    """Compact human label for a count: 1000→"1K", 62984→"63K", 999999→"1M", 320→"320".

    The magnitude threshold is set just below each unit (999.5, 999_500) so a
    value never rounds *across* its unit — e.g. 999,999 reads "1M", not "1000K".
    """
    n = float(n)
    for threshold, divisor, suffix in ((999_500, 1_000_000, "M"), (999.5, 1_000, "K")):
        if n >= threshold:
            scaled = n / divisor
            text = f"{scaled:.1f}".rstrip("0").rstrip(".") if scaled < 10 else f"{scaled:.0f}"
            return text + suffix
    return f"{int(round(n))}"


def _log_ticks(min_count: float, max_count: float) -> tuple[list[float], list[str]]:
    """Colorbar ticks for a log10 scale: whole decades inside the data range,
    anchored by the real min/max counts.  Falls back to just the endpoints when
    the range is too narrow to contain a decade — so any real ``min < max`` range
    yields ≥2 ticks (a degenerate ``min == max`` input yields the single tick).

    Assumes integral, NaN-free counts (both callers feed ``value_counts``-derived
    frames).  Returns ``(tickvals_in_log_space, human_readable_labels)``.
    """
    min_count = max(float(min_count), 1.0)
    max_count = max(float(max_count), min_count)
    lo, hi = math.floor(math.log10(min_count)), math.ceil(math.log10(max_count))
    decades = [10**p for p in range(int(lo), int(hi) + 1) if min_count <= 10**p <= max_count]
    values = sorted({min_count, max_count, *decades})
    tickvals = [math.log10(v) for v in values]
    ticktext = [_human_count(v) for v in values]
    return tickvals, ticktext


def _log_choropleth(
    frame: pd.DataFrame, value_col: str, value_label: str, title: str
) -> go.Figure:
    """World choropleth coloured on ``log10(value_col)`` with a real-count
    colorbar.  ``frame`` must carry ``iso3``, ``iso2``, ``name`` and ``value_col``.
    """
    f = frame.copy()
    f["_log_value"] = np.log10(f[value_col].astype(float).clip(lower=1))
    fig = px.choropleth(
        f,
        locations="iso3",
        color="_log_value",
        hover_name="name",
        hover_data={"_log_value": False, "iso2": True, value_col: True},
        color_continuous_scale=SEQUENTIAL_SCALE,
        title=title,
    )
    tickvals, ticktext = _log_ticks(f[value_col].min(), f[value_col].max())
    fig.update_layout(
        geo=dict(showframe=False, showcoastlines=True),
        margin=dict(l=0, r=0, t=40, b=0),
        height=420,
        coloraxis_colorbar=dict(title=value_label, tickvals=tickvals, ticktext=ticktext),
    )
    return fig


# ===========================================================================
# Geography (gallery tab: Geography)
# ===========================================================================


def geo_country_counts(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Records per ``jurisdiction_country`` with ISO-3 / name, plus the count of
    distinct country-code values that could not be mapped to ISO-3.

    Returns ``(counts_df, n_not_mappable)`` where ``counts_df`` has columns
    ``iso2, count, iso3, name`` ordered by descending count.
    """
    if "jurisdiction_country" not in df.columns:
        return pd.DataFrame(columns=["iso2", "count", "iso3", "name"]), 0

    counts = df["jurisdiction_country"].dropna().value_counts().reset_index()
    counts.columns = ["iso2", "count"]
    counts["iso3"] = counts["iso2"].map(lambda x: ISO_COUNTRY.get(x, {}).get("iso3"))
    counts["name"] = counts["iso2"].map(lambda x: ISO_COUNTRY.get(x, {}).get("name", x))
    n_not_mappable = int(counts["iso3"].isna().sum())
    return counts, n_not_mappable


def fig_geo_choropleth(df: pd.DataFrame) -> go.Figure:
    """World choropleth of record count by mapped country (Geography tab hero)."""
    counts, _ = geo_country_counts(df)
    mappable = counts.dropna(subset=["iso3"])
    if mappable.empty:
        return _empty_fig("No mappable country codes")
    return _log_choropleth(
        mappable, "count", "Records", "Records by country (mapped jurisdictions only)"
    )


def fig_geo_top_countries(df: pd.DataFrame, n: int = 20) -> go.Figure:
    """Top-N countries by record count (horizontal bar)."""
    counts, _ = geo_country_counts(df)
    top = counts.nlargest(n, "count")
    if top.empty:
        return _empty_fig("No country data")
    fig = px.bar(
        top,
        x="count",
        y="name",
        orientation="h",
        labels={"count": "Records", "name": "Country"},
        title=f"Top {n} countries",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=420)
    return fig


def fig_jurisdiction_bloc(df: pd.DataFrame, n: int = 15) -> go.Figure:
    """Top jurisdiction blocs by record count (horizontal bar)."""
    if "jurisdiction_bloc" not in df.columns:
        return _empty_fig("No bloc data")
    series = df["jurisdiction_bloc"].dropna()
    bloc_counts = series.value_counts().head(n).reset_index()
    bloc_counts.columns = ["bloc", "count"]
    if bloc_counts.empty:
        return _empty_fig("No bloc data")
    fig = px.bar(
        bloc_counts,
        x="count",
        y="bloc",
        orientation="h",
        labels={"count": "Records", "bloc": "Bloc"},
        title=f"Top blocs (of {series.nunique()} total)",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=350)
    return fig


def fig_jurisdiction_scope(df: pd.DataFrame) -> go.Figure:
    """Records by jurisdiction scope (vertical bar)."""
    if "jurisdiction_scope" not in df.columns:
        return _empty_fig("No scope data")
    scope_counts = df["jurisdiction_scope"].dropna().value_counts().reset_index()
    scope_counts.columns = ["scope", "count"]
    if scope_counts.empty:
        return _empty_fig("No scope data")
    fig = px.bar(
        scope_counts,
        x="scope",
        y="count",
        labels={"count": "Records", "scope": "Scope"},
        title="Records by jurisdiction scope",
        color_discrete_sequence=[BAR_FILL],
    )
    return fig


# ===========================================================================
# Institutions (gallery tab: Institutions) — these read the catalog directly
# ===========================================================================


def fig_inst_top_countries(catalog_df: pd.DataFrame, n: int = 20) -> go.Figure:
    """Top-N countries by monitored-institution count (horizontal bar)."""
    if catalog_df is None or catalog_df.empty or "jurisdiction_code" not in catalog_df.columns:
        return _empty_fig("No institution country data")
    by_country = catalog_df["jurisdiction_code"].dropna().value_counts().head(n).reset_index()
    by_country.columns = ["country", "institutions"]
    if by_country.empty:
        return _empty_fig("No institution country data")
    fig = px.bar(
        by_country,
        x="institutions",
        y="country",
        orientation="h",
        labels={"institutions": "Institutions", "country": "Country"},
        title=f"Top {n} countries by institution count",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=380)
    return fig


def fig_inst_regulator_types(catalog_df: pd.DataFrame, n: int = 15) -> go.Figure:
    """Top regulator (entity) types (horizontal bar).

    ``entity_type`` can be a semicolon-separated list, so values are split and
    counted individually — matching the gallery.
    """
    if catalog_df is None or catalog_df.empty or "entity_type" not in catalog_df.columns:
        return _empty_fig("No regulator-type data")
    all_types: list[str] = []
    for val in catalog_df["entity_type"].dropna():
        all_types.extend([t.strip() for t in str(val).split(";") if t.strip()])
    if not all_types:
        return _empty_fig("No regulator-type data")
    type_counts = pd.Series(all_types).value_counts().head(n).reset_index()
    type_counts.columns = ["entity_type", "count"]
    fig = px.bar(
        type_counts,
        x="count",
        y="entity_type",
        orientation="h",
        labels={"count": "Institutions", "entity_type": "Regulator type"},
        title="Top regulator types",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=380)
    return fig


def fig_inst_by_scope(catalog_df: pd.DataFrame) -> go.Figure:
    """Monitored institutions by scope (vertical bar)."""
    if catalog_df is None or catalog_df.empty or "scope" not in catalog_df.columns:
        return _empty_fig("No institution scope data")
    by_scope = catalog_df["scope"].dropna().value_counts().reset_index()
    by_scope.columns = ["scope", "count"]
    if by_scope.empty:
        return _empty_fig("No institution scope data")
    fig = px.bar(
        by_scope,
        x="scope",
        y="count",
        labels={"count": "Institutions", "scope": "Scope"},
        title="Institutions by scope",
        color_discrete_sequence=[BAR_FILL],
    )
    return fig


def inst_country_counts(catalog_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Monitored institutions per parent country (subdivisions rolled up).

    Returns ``(counts_df, n_excluded)`` where ``counts_df`` has columns
    ``iso2, institutions, iso3, name`` and ``n_excluded`` is the number of
    catalog rows with no single ISO country (placeholder / multi-country /
    unrecognised / missing code).
    """
    if catalog_df is None or catalog_df.empty or "jurisdiction_code" not in catalog_df.columns:
        return pd.DataFrame(columns=["iso2", "institutions", "iso3", "name"]), 0

    rolled = catalog_df["jurisdiction_code"].dropna().map(rollup_country)
    n_excluded = int(rolled.isna().sum()) + int(catalog_df["jurisdiction_code"].isna().sum())
    counts = rolled.dropna().value_counts().rename_axis("iso2").reset_index(name="institutions")
    counts["iso3"] = counts["iso2"].map(lambda x: ISO_COUNTRY[x]["iso3"])
    counts["name"] = counts["iso2"].map(lambda x: ISO_COUNTRY[x]["name"])
    return counts, n_excluded


def fig_inst_choropleth(catalog_df: pd.DataFrame) -> go.Figure:
    """World choropleth of monitored institutions by country (Institutions hero)."""
    counts, _ = inst_country_counts(catalog_df)
    if counts.empty:
        return _empty_fig("No mappable institution country codes")
    return _log_choropleth(
        counts, "institutions", "Institutions", "Monitored institutions by country"
    )


# ===========================================================================
# Category structure (gallery tab: Category Structure)
# ===========================================================================


def fig_category_sunburst(df: pd.DataFrame) -> go.Figure:
    """Category → institution sunburst, sized by record count."""
    if df.empty or not {"category", "topic_id"}.issubset(df.columns):
        return _empty_fig("No category data")
    cat_topic = df.groupby(["category", "topic_id"]).size().reset_index(name="count")
    if cat_topic.empty:
        return _empty_fig("No category data")
    fig = px.sunburst(
        cat_topic,
        path=["category", "topic_id"],
        values="count",
        title="Records by category → institution (sunburst)",
        color="count",
        color_continuous_scale=SEQUENTIAL_SCALE,
    )
    fig.update_layout(height=520)
    return fig


def fig_top_institutions(df: pd.DataFrame, catalog_df: pd.DataFrame | None = None, n: int = 30) -> go.Figure:
    """Top-N institutions by record count (horizontal bar), labelled by catalog name."""
    if "topic_id" not in df.columns:
        return _empty_fig("No institution data")
    topic_bar = df["topic_id"].dropna().value_counts().head(n).reset_index()
    topic_bar.columns = ["topic_id", "count"]
    if topic_bar.empty:
        return _empty_fig("No institution data")
    if catalog_df is not None and not catalog_df.empty and "topic_id" in catalog_df.columns:
        name_map = catalog_df.set_index("topic_id")["name"].to_dict()
        topic_bar["label"] = topic_bar["topic_id"].map(lambda x: name_map.get(x, x))
    else:
        topic_bar["label"] = topic_bar["topic_id"]
    fig = px.bar(
        topic_bar,
        x="count",
        y="label",
        orientation="h",
        labels={"count": "Records", "label": "Institution"},
        title=f"Top {n} institutions by record count",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=520)
    return fig


# ===========================================================================
# Update types (gallery tab: Update Types)
# ===========================================================================


def update_type_counts(df: pd.DataFrame) -> pd.Series:
    """Value counts of ``update_type`` (descending). Empty Series if absent."""
    if "update_type" not in df.columns:
        return pd.Series(dtype="int64")
    return df["update_type"].dropna().value_counts()


def fig_update_types(df: pd.DataFrame, top_n: int = 25) -> go.Figure:
    """Top-N update types by record count (horizontal bar)."""
    counts = update_type_counts(df)
    if counts.empty:
        return _empty_fig("No update-type data")
    top = counts.head(top_n).reset_index()
    top.columns = ["update_type", "count"]
    fig = px.bar(
        top,
        x="count",
        y="update_type",
        orientation="h",
        labels={"count": "Records", "update_type": "Update type"},
        title=f"Top {top_n} update types by record count",
        color_discrete_sequence=[BAR_FILL],
    )
    # tickmode="linear"/dtick=1 forces a label for EVERY category — without it
    # Plotly thins alternate y-axis labels when the chart is rendered short (e.g.
    # in the deck), so half the update-type names go missing.
    fig.update_layout(
        yaxis=dict(autorange="reversed", tickmode="linear", dtick=1),
        height=520,
    )
    return fig


# ===========================================================================
# Volume over time (gallery tab: Volume Over Time)
# ===========================================================================


def volume_frame(
    df: pd.DataFrame,
    freq_code: str = "YE",
    floor: bool = True,
    include_implausible: bool = False,
) -> tuple[pd.DataFrame, object]:
    """Prepared volume-over-time frame, shared by the chart and the caption.

    Buckets by ``reconciled_published_date``; ``floor`` trims to the 1%
    historical-depth date floor (the gallery default); each ``period`` is
    anchored to the START of its bucket to avoid the resample off-by-one.
    ``include_implausible`` shows out-of-window outliers and disables the floor,
    mirroring the gallery checkbox.

    Returns ``(vol_df, vol_floor)`` where ``vol_df`` has columns
    ``period, count`` and ``vol_floor`` is the floor date applied (or ``None``).
    """
    vol_df = volume_over_time(df, freq=freq_code, exclude_implausible=not include_implausible)
    vol_floor = None
    if vol_df.empty:
        return vol_df, vol_floor

    if floor and not include_implausible:
        vol_floor = historical_depth(df).get("earliest_date")
        if vol_floor is not None:
            # Filter on the END-anchored period (as the gallery has always done): a
            # bucket is kept when its end is >= the floor. For a yearly chart the
            # floor's bucket (e.g. 2008) is then shown at its start (2008-01-01), so
            # the first bar sits at the start of the floor's year. Behaviour copied
            # verbatim from the pre-shared-builder gallery so the deck matches the site.
            vol_df = vol_df[vol_df["period"] >= pd.Timestamp(vol_floor, tz="UTC")]
    if vol_df.empty:
        return vol_df, vol_floor

    vol_df = vol_df.copy()
    alias = _PERIOD_ALIAS.get(freq_code, "Y")
    vol_df["period"] = vol_df["period"].dt.tz_localize(None).dt.to_period(alias).dt.start_time
    return vol_df, vol_floor


def fig_volume(
    df: pd.DataFrame,
    freq_code: str = "YE",
    floor: bool = True,
    include_implausible: bool = False,
) -> go.Figure:
    """Annotations per period (bar), matching the gallery's default view."""
    vol_df, _ = volume_frame(df, freq_code, floor=floor, include_implausible=include_implausible)
    if vol_df.empty:
        return _empty_fig("No dated records in range")

    freq_label = FREQ_LABELS.get(freq_code, freq_code)
    fig = px.bar(
        vol_df,
        x="period",
        y="count",
        labels={"period": "Period", "count": "Annotations"},
        title=f"Annotations per period ({freq_label})",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(height=400)
    return fig


# ===========================================================================
# Score distributions (gallery tab: Score Distributions)
# ===========================================================================


def fig_score_histogram(df: pd.DataFrame, axis: str) -> go.Figure:
    """Histogram of a score axis (0–10) coloured by the canonical axis colour."""
    dists = score_distributions(df)
    scores = dists.get(axis, {}).get("scores", [])
    if not scores:
        return _empty_fig(f"No {axis} score data")
    fig = px.histogram(
        x=scores,
        nbins=20,
        labels={"x": f"{axis.capitalize()} score"},
        title=f"{axis.capitalize()} score distribution",
        color_discrete_sequence=[AXIS_COLORS.get(axis, CARVER_CHARCOAL)],
    )
    fig.update_layout(showlegend=False, height=280)
    return fig


def fig_confidence_histogram(df: pd.DataFrame, axis: str) -> go.Figure:
    """Histogram of a score axis's confidence (0–1)."""
    dists = score_distributions(df)
    confs = dists.get(axis, {}).get("confidence", [])
    if not confs:
        return _empty_fig(f"No {axis} confidence data")
    fig = px.histogram(
        x=confs,
        nbins=20,
        labels={"x": f"{axis.capitalize()} confidence"},
        title=f"{axis.capitalize()} confidence",
        color_discrete_sequence=[AXIS_COLORS.get(axis, CARVER_CHARCOAL)],
    )
    fig.update_layout(showlegend=False, height=280)
    return fig


def fig_label_mix(df: pd.DataFrame, axis: str) -> go.Figure:
    """Pie of the low/medium/high label mix for a score axis."""
    dists = score_distributions(df)
    label_counts = dists.get(axis, {}).get("label_counts", {})
    if not label_counts:
        return _empty_fig(f"No {axis} label data")
    ldf = pd.DataFrame(list(label_counts.items()), columns=["label", "count"])
    fig = px.pie(
        ldf,
        names="label",
        values="count",
        title=f"{axis.capitalize()} label mix",
        color_discrete_sequence=CARVER_QUALITATIVE,
    )
    fig.update_layout(height=260)
    return fig


# ===========================================================================
# Urgency basis (gallery tab: Urgency Basis)
# ===========================================================================


def _urgency_basis_counts(df: pd.DataFrame) -> pd.DataFrame:
    if "urgency_basis" not in df.columns:
        return pd.DataFrame(columns=["urgency_basis", "count"])
    counts = df["urgency_basis"].dropna().value_counts().reset_index()
    counts.columns = ["urgency_basis", "count"]
    return counts


def fig_urgency_basis_bar(df: pd.DataFrame) -> go.Figure:
    """Urgency-basis distribution (vertical bar)."""
    counts = _urgency_basis_counts(df)
    if counts.empty:
        return _empty_fig("No urgency-basis data")
    fig = px.bar(
        counts,
        x="urgency_basis",
        y="count",
        labels={"urgency_basis": "Urgency basis", "count": "Records"},
        title="Urgency basis distribution",
        color="urgency_basis",
        color_discrete_sequence=CARVER_QUALITATIVE,
    )
    fig.update_layout(showlegend=False, height=350)
    return fig


def fig_urgency_basis_pie(df: pd.DataFrame) -> go.Figure:
    """Urgency-basis share (pie)."""
    counts = _urgency_basis_counts(df)
    if counts.empty:
        return _empty_fig("No urgency-basis data")
    fig = px.pie(
        counts,
        names="urgency_basis",
        values="count",
        title="Basis share",
        color_discrete_sequence=CARVER_QUALITATIVE,
    )
    fig.update_layout(height=350)
    return fig


# ===========================================================================
# Deck-only composition charts (visualise metrics the Overview tab states)
# ===========================================================================


def fig_recency_bar(historical_depth_result: dict) -> go.Figure:
    """Small bar of the share of dated records within the last 1 / 3 / 7 years.

    Visualises the recency percentages the Overview tab states as KPIs, for the
    Overview slide of the deck.
    """
    rec = (historical_depth_result or {}).get("recency") or {}
    rows = [
        ("Within 1 year", rec.get("pct_1y", 0.0)),
        ("Within 2 years", rec.get("pct_2y", 0.0)),
        ("Within 3 years", rec.get("pct_3y", 0.0)),
        ("Within 5 years", rec.get("pct_5y", 0.0)),
        ("Within 10 years", rec.get("pct_10y", 0.0)),
    ]
    rdf = pd.DataFrame(rows, columns=["window", "pct"])
    if rdf["pct"].fillna(0).eq(0).all():
        return _empty_fig("No dated records")
    fig = px.bar(
        rdf,
        x="pct",
        y="window",
        orientation="h",
        labels={"pct": "Share of dated records", "window": ""},
        title="Recency of dated records",
        color_discrete_sequence=[BAR_FILL],
        text=rdf["pct"].map(lambda p: f"{p:.0%}"),
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        height=340,
        # Extend the x range past 1.0 so the outside-positioned "%" labels (up to
        # the ~94% bar) aren't clipped at the plot edge.
        xaxis=dict(tickformat=".0%", range=[0, 1.15]),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


def fig_category_composition(df: pd.DataFrame) -> go.Figure:
    """Records per category (horizontal bar) — the deck's Overview composition visual."""
    if "category" not in df.columns:
        return _empty_fig("No category data")
    counts = df["category"].dropna().value_counts().reset_index()
    counts.columns = ["category", "count"]
    if counts.empty:
        return _empty_fig("No category data")
    fig = px.bar(
        counts,
        x="count",
        y="category",
        orientation="h",
        labels={"count": "Records", "category": "Category"},
        title="Records by category",
        color="count",
        color_continuous_scale=SEQUENTIAL_SCALE,
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=320, coloraxis_showscale=False)
    return fig


# ===========================================================================
# Tags & Entities (gallery tab)
# ===========================================================================


def fig_entity_type_breakdown(breakdown_df: pd.DataFrame | None) -> go.Figure:
    """Pie chart of the 6 entity-type buckets by share of mentions.

    With only 6 buckets a pie reads the composition (each type's share of total
    mentions) more directly than bars. ``breakdown_df`` must have columns
    ``type, mentions, distinct_entities``. Slices are coloured by
    ``ENTITY_TYPE_COLORS`` (matching the leaderboard); the raw mention count and
    ``distinct_entities`` are surfaced in hover.
    """
    required = {"type", "mentions", "distinct_entities"}
    if breakdown_df is None or breakdown_df.empty or not required.issubset(breakdown_df.columns):
        return _empty_fig("No entity-type breakdown data")

    df = breakdown_df.sort_values("mentions", ascending=False).reset_index(drop=True)
    fig = go.Figure(
        go.Pie(
            labels=df["type"],
            values=df["mentions"],
            sort=False,  # preserve the mentions-descending slice order
            marker=dict(
                colors=[ENTITY_TYPE_COLORS.get(t, "#888888") for t in df["type"]]
            ),
            customdata=df[["distinct_entities"]].values,
            textinfo="percent",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Mentions: %{value:,} (%{percent})<br>"
                "Distinct entities: %{customdata[0]:,}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="Entity types by mentions",
        height=380,
        margin=dict(l=10, r=20, t=40, b=20),
    )
    return fig


def fig_entity_leaderboard(
    leaderboard_df: pd.DataFrame | None,
    n: int = ENTITY_LEADERBOARD_TOP_N,
) -> go.Figure:
    """Top-n canonical entities by mentions, coloured by type using ENTITY_TYPE_COLORS.

    ``leaderboard_df`` must have columns ``canonical_name, type, mentions``.
    One ``go.Bar`` trace per entity-type bucket, with a discrete colour legend.
    A stored top-50 CSV can render any ``n ≤ 50`` via ``nlargest``.
    """
    required = {"canonical_name", "type", "mentions"}
    if leaderboard_df is None or leaderboard_df.empty or not required.issubset(leaderboard_df.columns):
        return _empty_fig("No entity leaderboard data")

    top = leaderboard_df.nlargest(n, "mentions").reset_index(drop=True)
    if top.empty:
        return _empty_fig("No entity leaderboard data")

    # One trace per type so the legend differentiates buckets.
    traces = []
    for entity_type, group in top.groupby("type", sort=False):
        color = ENTITY_TYPE_COLORS.get(entity_type, "#888888")
        traces.append(
            go.Bar(
                name=entity_type,
                x=group["mentions"],
                y=group["canonical_name"],
                orientation="h",
                marker_color=color,
                hovertemplate="<b>%{y}</b><br>Mentions: %{x:,}<extra></extra>",
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=f"Most-referenced bodies (top {n})",
        xaxis_title="Mentions",
        yaxis=dict(
            autorange="reversed",
            # categoryarray pins the y-axis to the GLOBAL mentions-desc order from
            # `top`, overriding Plotly's default first-encounter ordering across
            # the overlaid per-type traces (which would cluster by type instead).
            categoryorder="array",
            categoryarray=list(top["canonical_name"]),
        ),
        barmode="overlay",
        showlegend=True,
        height=max(380, 20 * n),
        margin=dict(l=10, r=20, t=40, b=40),
    )
    return fig


def fig_tag_leaderboard(
    tag_df: pd.DataFrame | None,
    n: int = TAG_LEADERBOARD_TOP_N,
) -> go.Figure:
    """Top-n tags by count (horizontal bar, descending).

    ``tag_df`` must have columns ``tag, count``.
    """
    required = {"tag", "count"}
    if tag_df is None or tag_df.empty or not required.issubset(tag_df.columns):
        return _empty_fig("No tag data")

    top = tag_df.nlargest(n, "count").reset_index(drop=True)
    if top.empty:
        return _empty_fig("No tag data")

    fig = px.bar(
        top,
        x="count",
        y="tag",
        orientation="h",
        labels={"count": "Annotations", "tag": "Tag"},
        title="Top tags",
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        height=max(380, 20 * n),
        margin=dict(l=10, r=20, t=40, b=40),
    )
    return fig


# ===========================================================================
# Regulators (gallery tab: Regulators)
# ===========================================================================


def fig_regulator_leaderboard(
    leaderboard_df: pd.DataFrame | None,
    n: int = REGULATOR_LEADERBOARD_TOP_N,
) -> go.Figure:
    """Top-n regulator bodies by mention count (horizontal bar, descending).

    Mirrors ``fig_tag_leaderboard``.  ``leaderboard_df`` must have columns
    ``name, mentions``.  The optional ``country`` column is surfaced in hover
    when present.
    """
    required = {"name", "mentions"}
    if leaderboard_df is None or leaderboard_df.empty or not required.issubset(leaderboard_df.columns):
        return _empty_fig("No regulator data")

    # leaderboard_df is pre-sorted descending by (mentions, name); use head(n) to
    # preserve the secondary name tiebreak (nlargest is unstable on the secondary key).
    top = leaderboard_df.head(n).reset_index(drop=True)
    if top.empty:
        return _empty_fig("No regulator data")

    hover_data = {}
    if "country" in top.columns:
        hover_data["country"] = True

    fig = px.bar(
        top,
        x="mentions",
        y="name",
        orientation="h",
        labels={"mentions": "Mentions", "name": "Regulator"},
        title="Top regulators by mentions",
        hover_data=hover_data if hover_data else None,
        color_discrete_sequence=[BAR_FILL],
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        height=max(380, 20 * n),
        margin=dict(l=10, r=20, t=40, b=40),
    )
    return fig


def fig_regulator_choropleth(by_country_df: pd.DataFrame | None) -> go.Figure:
    """World choropleth of distinct regulator bodies by country (log10 colour scale).

    ``by_country_df`` must have columns ``iso3, iso2, name, n_regulators``.
    Colour and colorbar come from the shared ``_log_choropleth`` helper.
    """
    required = {"iso3", "iso2", "name", "n_regulators"}
    if (
        by_country_df is None
        or by_country_df.empty
        or not required.issubset(by_country_df.columns)
    ):
        return _empty_fig("No regulator country data")
    return _log_choropleth(
        by_country_df, "n_regulators", "Regulators", "Distinct regulators by country"
    )


def fig_inst_domain_sunburst(catalog_df: pd.DataFrame | None) -> go.Figure:
    """Two-ring sunburst donut showing the domain-wise breakup of monitored institutions.

    Inner ring = top-level domain; outer ring = sub-domain leaf.
    One row per institution; ``catalog_df`` must already be merged with domain
    columns so it has at least ``top_level`` and ``sub_domain``.

    Parameters
    ----------
    catalog_df:
        Institutions catalog merged with topic_domains, one row per institution.
        Required columns: ``top_level``, ``sub_domain``.

    Returns
    -------
    go.Figure
        A ``px.sunburst`` figure with ``branchvalues="total"`` so the inner ring
        value equals the sum of its leaf children.  Returns ``_empty_fig(...)``
        when input is None/empty or missing the required columns.
    """
    required = {"top_level", "sub_domain"}
    if (
        catalog_df is None
        or catalog_df.empty
        or not required.issubset(catalog_df.columns)
    ):
        return _empty_fig("No institution domain data")

    # Drop rows where either hierarchy column is null or blank
    clean = catalog_df.dropna(subset=["top_level", "sub_domain"])
    clean = clean[
        (clean["top_level"].astype(str).str.strip() != "")
        & (clean["sub_domain"].astype(str).str.strip() != "")
    ]
    if clean.empty:
        return _empty_fig("No institution domain data")

    # Count institutions per (top_level, sub_domain)
    counts = (
        clean.groupby(["top_level", "sub_domain"], sort=False)
        .size()
        .reset_index(name="count")
    )

    fig = px.sunburst(
        counts,
        path=["top_level", "sub_domain"],
        values="count",
        color="top_level",
        # Shared per-domain colour map so a domain matches the top-level bar chart.
        color_discrete_map=DOMAIN_COLOR_MAP,
        title="Monitored institutions by domain",
        hover_data={"count": True},
    )
    fig.update_traces(
        branchvalues="total",
        hovertemplate="<b>%{label}</b><br>Institutions: %{value}<extra></extra>",
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        height=460,
    )
    return fig


def fig_inst_domain_bar(catalog_df: pd.DataFrame | None) -> go.Figure:
    """Horizontal bar of monitored institutions per TOP-LEVEL domain (descending).

    The "main tier" companion to ``fig_inst_domain_sunburst`` — an at-a-glance
    ranking of the 11 top-level domains.  ``catalog_df`` is the per-institution
    frame already merged with domains (needs a ``top_level`` column).  Colours
    come from the shared ``DOMAIN_COLOR_MAP`` so bars match the sunburst.
    """
    if (
        catalog_df is None
        or catalog_df.empty
        or "top_level" not in catalog_df.columns
    ):
        return _empty_fig("No institution domain data")

    top = catalog_df["top_level"].dropna()
    top = top[top.astype(str).str.strip() != ""]
    if top.empty:
        return _empty_fig("No institution domain data")

    counts = top.value_counts().rename_axis("top_level").reset_index(name="institutions")

    fig = px.bar(
        counts,
        x="institutions",
        y="top_level",
        orientation="h",
        color="top_level",
        color_discrete_map=DOMAIN_COLOR_MAP,
        labels={"institutions": "Institutions", "top_level": "Domain"},
        title="Monitored institutions by top-level domain",
        text="institutions",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        # Rank largest domain at the top. `categoryorder` is used (not
        # autorange="reversed") because color="top_level" splits the bars into one
        # trace per domain, which otherwise leaves the axis in data order.
        yaxis=dict(categoryorder="total ascending"),
        showlegend=False,                  # redundant with the y-axis labels
        height=460,
        margin=dict(l=10, r=30, t=40, b=40),
    )
    return fig


# Re-exported so callers needing the band convention for captions share it.
__all__ = [
    "LABEL_BANDS",
    "SCORE_AXES",
    "AXIS_COLORS",
    "rollup_country",
    "geo_country_counts",
    "fig_geo_choropleth",
    "fig_geo_top_countries",
    "fig_jurisdiction_bloc",
    "fig_jurisdiction_scope",
    "fig_inst_top_countries",
    "fig_inst_regulator_types",
    "fig_inst_by_scope",
    "inst_country_counts",
    "fig_inst_choropleth",
    "fig_category_sunburst",
    "fig_top_institutions",
    "update_type_counts",
    "fig_update_types",
    "volume_frame",
    "fig_volume",
    "fig_score_histogram",
    "fig_confidence_histogram",
    "fig_label_mix",
    "fig_urgency_basis_bar",
    "fig_urgency_basis_pie",
    "fig_recency_bar",
    "fig_category_composition",
    "fig_entity_type_breakdown",
    "fig_entity_leaderboard",
    "fig_tag_leaderboard",
    "fig_regulator_leaderboard",
    "fig_regulator_choropleth",
    "fig_inst_domain_sunburst",
    "fig_inst_domain_bar",
]
