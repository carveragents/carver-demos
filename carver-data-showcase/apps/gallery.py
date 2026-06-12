"""Carver Annotation Data Showcase — External Gallery (spec §6).

Entry point:  streamlit run apps/gallery.py

Views (spec §6.2; external-facing tab labels carry no internal version prefix):
  Overview            headline KPIs + historical depth (above the fold) + explainer
  Geography           jurisdiction & geography breadth (choropleth + bloc/scope bars)
  Institutions        monitored institutions from topic_catalog.csv
  Update Types        update-type mix (top-N bar + long-tail count)
  Volume Over Time    volume over time (line/bar by reconciled_published_date)
  Score Distributions impact score histogram + confidence + label mix (impact-only)
  Record Drill-Down   single-record richness drill-down
  Highlight Reel      top-N by richness_score

Relevance is a deprecated weighted sum of impact and urgency and is shown nowhere.
Categories are an internal concept and are not surfaced externally: urgency-score
detail (score / confidence / basis distributions) and the category/institution
structure (sunburst + top-institutions) live in the Data-Quality Cockpit, not
this external gallery.

Design rules:
  - Cache all data loads with st.cache_data / st.cache_resource.
  - Never call the live API; read cached snapshot only.
  - All views drive from the sidebar-filtered 'view' DataFrame.
  - No per-row Python over the full corpus — use vectorized metrics functions.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — allow running from the repo root without installing the package
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from carver_showcase import charts
from carver_showcase.config import (
    ANNOTATIONS_JSONL,
    ANNOTATIONS_PARQUET,
    LABEL_BANDS,
    PLAUSIBLE_DATE_WINDOW,
    PUBLIC_KEEP_COLUMNS,
    TOPIC_CATALOG_CSV,
    TOPIC_CATEGORIES_CSV,
)

from carver_showcase.curate import drop_noise_update_types
from carver_showcase.load import (
    build_record_index,
    get_raw_record,
    load_catalog,
    load_normalized,
    load_snapshot_meta,
    load_term_stats,
    load_topic_domains,
)
from carver_showcase.metrics import (
    breadth_summary,
    historical_depth,
    score_distributions,
)
from carver_showcase.richness import highlight_reel
from apps.components.filters import FilterState, apply_filters, sidebar_filters
from apps.components.render import (
    deck_download,
    kpi_cards,
    record_drilldown,
    richness_definition,
    scope_banner,
    snapshot_note,
)

# ---------------------------------------------------------------------------
# Public-build flag — set CARVER_PUBLIC_BUILD=1 to enable aggregate-only mode.
# When true: slim data load (15-col allowlist), record-level tabs omitted, and
# build_record_index / get_raw_record are never called (no JSONL access).
# ---------------------------------------------------------------------------
PUBLIC_BUILD = os.environ.get("CARVER_PUBLIC_BUILD") == "1"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Carver Annotation Data Showcase",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Brand polish (gallery only — the Cockpit is unaffected).
# The colours come from .streamlit/config.toml (global theme); this adds the
# Carver typeface (Poppins) and the site's pill-shaped buttons + a lime active-
# tab underline, which the native theme options can't express.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"], .stMarkdown, .stMetric,
    button, input, textarea, select { font-family: 'Poppins', sans-serif !important; }
    h1, h2, h3, h4 { font-family: 'Poppins', sans-serif !important; font-weight: 600 !important; }

    /* Pill-shaped buttons + download button, matching the site's CTAs */
    .stButton > button, .stDownloadButton > button {
        border-radius: 999px !important;
        font-weight: 600 !important;
    }
    /* Primary action buttons (lime): dark ink, like the site's lime CTAs. */
    .stButton > button[kind="primary"], .stButton > button[kind="primary"] * {
        color: #1f2124 !important;
        fill: #1f2124 !important;
    }
    /* The deck download CTA uses the site's DARK button variant: charcoal fill,
       off-white text. The :not(#_) id-bump raises specificity above Streamlit's
       own primary-button background rule. */
    .stDownloadButton button[data-testid="stBaseButton-primary"]:not(#_) {
        background-color: #1f2124 !important;
        border-color: #1f2124 !important;
    }
    .stDownloadButton button[data-testid="stBaseButton-primary"]:not(#_):hover,
    .stDownloadButton button[data-testid="stBaseButton-primary"]:not(#_):focus,
    .stDownloadButton button[data-testid="stBaseButton-primary"]:not(#_):active {
        background-color: #2d3138 !important;
        border-color: #2d3138 !important;
    }
    .stDownloadButton button[data-testid="stBaseButton-primary"]:not(#_),
    .stDownloadButton button[data-testid="stBaseButton-primary"]:not(#_) * {
        color: #fbf7f3 !important;
        fill: #fbf7f3 !important;
    }

    /* Sidebar score sliders → charcoal (override the lime primary). The thumb,
       value bubble and tick labels recolour directly; the filled track is a
       lime gradient whose fill-% lives in a dynamic class, so it's colour-shifted
       to charcoal with a saturate/brightness filter (keeps the fill indicator). */
    section[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {
        background: #1f2124 !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="slider"] div[style*="height: 0.25rem"] {
        filter: saturate(0) brightness(0.16) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="slider"] [data-testid="stSliderThumbValue"],
    section[data-testid="stSidebar"] [data-baseweb="slider"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-baseweb="slider"] [data-testid="stMarkdownContainer"] p {
        color: #1f2124 !important;
    }

    /* Lime underline under the active tab */
    .stTabs [data-baseweb="tab-highlight"] { background-color: #bae424 !important; }
    .stTabs [aria-selected="true"] { color: #1f2124 !important; font-weight: 600 !important; }

    /* KPI metric values in charcoal with a touch more weight */
    [data-testid="stMetricValue"] { color: #1f2124 !important; font-weight: 700 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cached data loaders (app edge — spec §9.1)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading annotation snapshot…")
def _load_df() -> pd.DataFrame:
    # In public mode, restrict to the 15-column allowlist as a belt-and-suspenders
    # structural guard — the app physically cannot surface a content column even
    # if a misconfigured bundle were deployed.
    keep = list(PUBLIC_KEEP_COLUMNS) if PUBLIC_BUILD else None
    df = load_normalized(
        parquet_path=ANNOTATIONS_PARQUET,
        jsonl_path=ANNOTATIONS_JSONL,
        categories_path=TOPIC_CATEGORIES_CSV,
        keep_columns=keep,
    )
    # External gallery: drop update_type noise (the sub-0.01% long tail + named
    # crawl-junk like "website error") so it never appears in the dataset, KPIs,
    # charts, or filters. The Cockpit loads the same parquet WITHOUT this step.
    return drop_noise_update_types(df)


@st.cache_data(show_spinner="Loading institutions catalog…")
def _load_catalog() -> pd.DataFrame:
    return load_catalog(catalog_path=TOPIC_CATALOG_CSV)


@st.cache_resource(show_spinner="Building record index…")
def _build_index() -> dict[str, int]:
    return build_record_index(jsonl_path=ANNOTATIONS_JSONL)


@st.cache_data(show_spinner=False)
def _load_meta() -> dict:
    return load_snapshot_meta()


@st.cache_data(show_spinner=False)
def _load_term_stats() -> dict | None:
    return load_term_stats()


@st.cache_data(show_spinner=False)
def _load_topic_domains() -> pd.DataFrame:
    return load_topic_domains()


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_full = _load_df()
catalog_df = _load_catalog()
meta = _load_meta()
term_stats = _load_term_stats()
topic_domains = _load_topic_domains()

# ---------------------------------------------------------------------------
# App header — live counts, plus the always-visible point-in-time note
# (rendered above the tabs so it shows on every page).
# ---------------------------------------------------------------------------
st.title("Carver Annotation Data Showcase")
st.markdown(
    f"**Range · Quality · Richness** — explore **{len(df_full):,}** AI-generated regulatory "
    "annotations spanning regulators and jurisdictions worldwide."
)
# Prominent, always-visible download of the point-in-time "State of Carver Data"
# deck (one slide per view, filter-free) — placed at the top of the header.
deck_download(meta)
snapshot_note(meta)
# Scope / composition banner — persistent context directly under the snapshot note,
# computed over the full (unfiltered) snapshot, so it shows on every page.
scope_banner(df_full, catalog_df, meta, show_categories=False)

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
state: FilterState = sidebar_filters(
    df_full, include_category=False, include_regulator=False, catalog_df=catalog_df
)
view: pd.DataFrame = apply_filters(df_full, state)

n_filtered = len(view)
if n_filtered < len(df_full):
    st.sidebar.caption(f"{n_filtered:,} of {len(df_full):,} records match current filters.")

# ---------------------------------------------------------------------------
# View tabs
# ---------------------------------------------------------------------------
TABS = [
    "Overview",
    "Geography",
    "Institutions",
]
# Tags & Entities sits after Institutions, and only when the enrichment
# artifacts exist (graceful absence otherwise).
if term_stats is not None:
    TABS = TABS + ["Tags & Entities"]
TABS = TABS + [
    "Update Types",
    "Volume Over Time",
    "Score Distributions",
]
# Record-level tabs are omitted in public mode — they require raw JSONL access
# and expose per-record content that must not appear in the public bundle.
if not PUBLIC_BUILD:
    TABS = TABS + ["Record Drill-Down", "Highlight Reel"]

tabs = st.tabs(TABS)
# Address tab bodies by name (not position) so the conditional Tags & Entities
# insertion can never desync the indices.
TAB = {name: i for i, name in enumerate(TABS)}


# ===========================================================================
# v0 — Overview + explainer + KPIs + historical-depth + sampling banner
# ===========================================================================
with tabs[TAB["Overview"]]:
    # -----------------------------------------------------------------------
    # Headline KPIs — placed first, above the fold (spec §6.2 v0, G5)
    # -----------------------------------------------------------------------
    bs = breadth_summary(view)
    total_records = len(view)

    richness_series = (
        view["richness_score"].dropna() if "richness_score" in view.columns else None
    )
    richness_median = (
        int(richness_series.median())
        if richness_series is not None and not richness_series.empty
        else "—"
    )
    # % fully scored on the two independent axes (relevance is deprecated, excluded).
    pct_full_score = (
        view[["impact_score", "urgency_score"]].notna().all(axis=1).mean()
        if all(c in view.columns for c in ["impact_score", "urgency_score"])
        else 0.0
    )
    filter_suffix = " (current filter)" if total_records < len(df_full) else ""

    st.markdown(f"### Headline KPIs{filter_suffix}")
    kpi_cards(
        {
            "Records": f"{total_records:,}",
            "Institutions": f"{bs['n_topics']:,}",
            "Countries": f"{bs['n_countries']:,}",
        }
    )
    kpi_cards(
        {
            "Median richness score": f"{richness_median}/100",
            "% fully scored (impact + urgency)": f"{pct_full_score:.1%}",
        }
    )
    richness_definition()

    st.divider()

    # -----------------------------------------------------------------------
    # Historical depth block (spec §6.2 v0, G5)
    # -----------------------------------------------------------------------
    st.markdown("### Historical Depth")
    plausible_lo, plausible_hi = PLAUSIBLE_DATE_WINDOW
    hd = historical_depth(view)
    if hd["earliest_date"] is not None:
        floor_pct = f"{hd['floor_quantile']:.0%}"
        st.caption(
            f"**Earliest record** is the **{floor_pct} quantile** of publication dates — the "
            "start of the range covering the most-recent 99% of records — so an ultra-sparse "
            "tail of very old entries doesn't overstate the span. **Latest record** is the true "
            f"maximum. Out-of-window dates (outside {plausible_lo.year}–{plausible_hi.year}) are "
            "treated as data-entry errors, excluded here, and tracked as anomalies in the "
            "Data-Quality Cockpit."
        )
        span_years = round((hd["span_days"] or 0) / 365.25, 1)
        kpi_cards(
            {
                f"Earliest record ({floor_pct} floor)": str(hd["earliest_date"]),
                "Latest record": str(hd["latest_date"]),
                "Data span": f"{span_years} years",
                "Dated records": f"{hd['n_plausible']:,}",
                "Implausible (excluded)": f"{hd['n_implausible']:,}",
            }
        )
        rec = hd["recency"]
        st.markdown("**Records within the last…**")
        kpi_cards(
            {
                "1 year": f"{rec['pct_1y']:.1%}",
                "2 years": f"{rec['pct_2y']:.1%}",
                "3 years": f"{rec['pct_3y']:.1%}",
                "5 years": f"{rec['pct_5y']:.1%}",
                "10 years": f"{rec['pct_10y']:.1%}",
            }
        )
        st.info(
            f"**Recency note:** the dataset is strongly recency-weighted — "
            f"**{rec['pct_3y']:.0%}** of dated records fall within the last 3 years. The "
            f"earliest date shown is the {floor_pct} floor; **{hd['n_below_floor']:,}** record(s) "
            f"(~{floor_pct}) predate it, with a genuine tail back to {hd['true_earliest_date']}. "
            f"A further **{hd['n_implausible']:,}** record(s) carry out-of-window dates "
            f"(outside {plausible_lo.year}–{plausible_hi.year} — data-entry artefacts, not real "
            "coverage), excluded above and tracked as anomalies in the Cockpit.",
            icon="ℹ️",
        )
    else:
        st.info("No plausible dates in the current filter selection.")

    st.divider()

    # -----------------------------------------------------------------------
    # "What is an annotation" explainer (scope banner now lives in the header)
    # -----------------------------------------------------------------------
    st.markdown("## What is a Carver Annotation?")
    st.markdown(
        """
Carver attaches a rich, AI-generated **annotation** to every raw regulatory feed entry.
A raw feed entry is little more than a title, a link, and a date. The annotation turns
it into a machine-readable compliance object with:

| Component | What it captures |
|---|---|
| **Scored axes** | Impact · Urgency — each with a label, numeric score, and confidence |
| **Impact narrative** | Objective · What changed · Why it matters · Risk/impact · Key requirements |
| **Seven actionable lanes** | Policy / Status / Process / Training / Reporting / Tech-data / Other changes |
| **Critical dates** | Effective, compliance, comment-deadline, and other calendar dates |
| **Entities & tags** | Named organisations, officials, and free-text topic tags |
| **Regulatory references** | Rules, statutes, precedents, personnel, past releases |
| **Jurisdiction classification** | Country, bloc, scope — with explicit reasoning |
| **Impacted business & functions** | Industry, business type, and functions affected |
| **Penalties & consequences** | Enforcement implications |

Every figure in this showcase is **computed live** over the loaded snapshot — nothing is hard-coded.
"""
    )


# ===========================================================================
# v1 — Jurisdiction & geography breadth
# ===========================================================================
with tabs[TAB["Geography"]]:
    st.markdown("## Jurisdiction & Geography Breadth")
    st.markdown(
        "Shows the global reach of the annotation dataset. "
        "Each dot on the map and each bar reflects records in the **current filter**."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        # --- Choropleth (shared builder — same figure the deck renders) ---
        st.markdown("### Country-level record count")

        _country_counts, n_not_mappable = charts.geo_country_counts(view)
        if not _country_counts.dropna(subset=["iso3"]).empty:
            st.plotly_chart(charts.fig_geo_choropleth(view), width="stretch")
        else:
            st.info("No mappable country codes in the current filter.")

        if n_not_mappable > 0:
            st.caption(
                f"Note: {n_not_mappable} distinct country-code value(s) could not be "
                "mapped to ISO-3 and are excluded from the choropleth. "
                "They may represent blocs, non-standard codes, or empty values."
            )

        # --- Top countries bar ---
        st.markdown("### Top 20 countries by record count")
        if not _country_counts.empty:
            st.plotly_chart(charts.fig_geo_top_countries(view, n=20), width="stretch")

        col1, col2 = st.columns(2)

        # --- Bloc bar ---
        with col1:
            st.markdown("### Jurisdiction bloc")
            if not view["jurisdiction_bloc"].dropna().empty:
                st.plotly_chart(charts.fig_jurisdiction_bloc(view, n=15), width="stretch")
            else:
                st.info("No bloc data in current filter.")

        # --- Scope bar ---
        with col2:
            st.markdown("### Jurisdiction scope")
            if not view["jurisdiction_scope"].dropna().empty:
                st.plotly_chart(charts.fig_jurisdiction_scope(view), width="stretch")
            else:
                st.info("No scope data in current filter.")


# ===========================================================================
# v1a — Monitored institutions (G4)
# ===========================================================================
with tabs[TAB["Institutions"]]:
    st.markdown("## Monitored Institutions")

    if catalog_df.empty:
        st.warning(
            "topic_catalog.csv not found. "
            "Run `tools/pull_topic_catalog.py` to generate it."
        )
    else:
        # Join sample record counts per topic_id (from UNFILTERED full frame)
        topic_counts = (
            df_full["topic_id"]
            .value_counts()
            .rename("records_in_sample")
            .reset_index()
        )
        topic_counts.columns = ["topic_id", "records_in_sample"]

        inst_df = catalog_df.merge(topic_counts, on="topic_id", how="left")
        inst_df["records_in_sample"] = (
            inst_df["records_in_sample"].fillna(0).astype(int)
        )

        # Search / filter
        col_search, col_scope_filter = st.columns([3, 1])
        with col_search:
            search_query = st.text_input(
                "Search institutions (name, acronym, country)",
                value="",
                key="inst_search",
            )
        with col_scope_filter:
            scope_options = ["All"] + sorted(
                catalog_df["scope"].dropna().unique().tolist()
            )
            scope_filter = st.selectbox(
                "Filter by scope", scope_options, key="inst_scope"
            )

        display_cols = [
            "name", "acronym", "jurisdiction_code", "entity_type",
            "scope", "records_in_sample",
        ]
        # Keep only columns that exist
        display_cols = [c for c in display_cols if c in inst_df.columns]
        inst_display = inst_df[display_cols].copy()

        # Apply search
        if search_query.strip():
            q = search_query.strip().lower()
            mask = pd.Series(False, index=inst_display.index)
            for col in ["name", "acronym", "jurisdiction_code"]:
                if col in inst_display.columns:
                    mask |= inst_display[col].fillna("").str.lower().str.contains(q, regex=False)
            inst_display = inst_display[mask]

        # Apply scope filter
        if scope_filter != "All" and "scope" in inst_display.columns:
            inst_display = inst_display[inst_display["scope"] == scope_filter]

        st.markdown(
            f"Showing **{len(inst_display):,}** of **{len(inst_df):,}** institutions "
            f"({inst_display['records_in_sample'].gt(0).sum():,} with records in sample)"
        )

        # Sortable table
        sort_col = st.selectbox(
            "Sort by",
            ["records_in_sample", "name", "jurisdiction_code"],
            key="inst_sort",
        )
        inst_sorted = inst_display.sort_values(
            sort_col, ascending=(sort_col == "name")
        )
        st.dataframe(inst_sorted, width="stretch", height=350)

        # CSV download
        csv_bytes = inst_df[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download full institutions table (CSV)",
            data=csv_bytes,
            file_name="carver_monitored_institutions.csv",
            mime="text/csv",
        )

        st.divider()
        st.markdown("### Breakdown charts")
        col_c, col_t, col_s = st.columns(3)

        # All three breakdown charts come from the shared builders (same figures
        # the deck renders). They count the full monitored universe, independent
        # of the table's search/scope filter.
        with col_c:
            if not inst_df["jurisdiction_code"].dropna().empty:
                st.plotly_chart(charts.fig_inst_top_countries(inst_df, n=20), width="stretch")

        with col_t:
            if not inst_df["entity_type"].dropna().empty:
                st.plotly_chart(charts.fig_inst_regulator_types(inst_df, n=15), width="stretch")

        with col_s:
            if not inst_df["scope"].dropna().empty:
                st.plotly_chart(charts.fig_inst_by_scope(inst_df), width="stretch")

        # --- Institutions by domain (sunburst donut) ---
        # Inserted between the 3-up breakdown charts and the choropleth section.
        # Counts the FULL monitored universe (not affected by the table's search/scope
        # filter), consistent with the other breakdown charts above.
        st.divider()
        st.markdown("### Institutions by domain")
        if not topic_domains.empty and {"top_level", "sub_domain"}.issubset(topic_domains.columns):
            inst_domains = inst_df.merge(
                topic_domains[["topic_id", "top_level", "sub_domain"]],
                on="topic_id",
                how="left",
            )
            # Main-tier ranking (left) + full two-level drill-down donut (right).
            # Shared colours mean a domain reads the same across both charts.
            col_bar, col_sun = st.columns(2)
            with col_bar:
                st.plotly_chart(charts.fig_inst_domain_bar(inst_domains), width="stretch")
            with col_sun:
                st.plotly_chart(charts.fig_inst_domain_sunburst(inst_domains), width="stretch")
            n_classified = int(inst_domains["top_level"].notna().sum())
            st.caption(
                f"Domain classification covers the **full monitored universe** "
                f"({n_classified:,} of {len(inst_df):,} institutions classified), "
                "independent of the table's search/scope filter above. "
                "Classification is LLM-derived and static — run `tools/classify_domains.py` "
                "to refresh."
            )
        else:
            st.info(
                "Domain classification not available yet. "
                "Run `tools/classify_domains.py` to generate `data/topic_domains.csv`."
            )

        # --- Geographic distribution of monitored institutions (choropleth) ---
        # Last object on the tab. Counts ALL monitored institutions per country
        # (independent of the table's search/scope filter) — the global footprint of
        # the universe. Mirrors the Geography tab, which maps annotation counts; here
        # each unit is an institution. Subdivision codes (e.g. "US-CA") roll up to their
        # parent country ("US"); placeholders ("-") and multi-country / EU-wide strings
        # have no single ISO country and are excluded (counted honestly in the caption).
        st.divider()
        st.markdown("### Geographic distribution of monitored institutions")

        if "jurisdiction_code" in inst_df.columns:
            geo_counts, n_geo_excluded = charts.inst_country_counts(inst_df)
            if not geo_counts.empty:
                st.plotly_chart(charts.fig_inst_choropleth(inst_df), width="stretch")
                n_mapped = int(geo_counts["institutions"].sum())
                caption = (
                    f"**{len(geo_counts):,}** countries shown, covering **{n_mapped:,}** of "
                    f"**{len(inst_df):,}** monitored institutions."
                )
                if n_geo_excluded > 0:
                    caption += (
                        f" {n_geo_excluded:,} carry no single ISO country (placeholder, "
                        "multi-country / EU-wide, or unrecognized code) and are excluded."
                    )
                st.caption(caption)
            else:
                st.info("No mappable country codes in the institutions catalog.")
        else:
            st.info("No `jurisdiction_code` column in the institutions catalog.")


# ===========================================================================
# v3 — Update-type mix
# ===========================================================================
with tabs[TAB["Update Types"]]:
    st.markdown("## Update-Type Mix")
    n_ut_full = (
        int(df_full["update_type"].dropna().nunique())
        if "update_type" in df_full.columns else 0
    )
    st.markdown(
        f"Distribution of `update_type` in the current filter ({n_ut_full} distinct types). "
        "Rare types (below 0.01% of volume) and crawl-error types are excluded from "
        "this external view; the full long tail is tracked in the Data-Quality Cockpit."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        TOP_N = 25
        ut_counts = charts.update_type_counts(view)
        longtail_n = max(0, len(ut_counts) - TOP_N)
        longtail_count = int(ut_counts.iloc[TOP_N:].sum()) if longtail_n > 0 else 0

        # Shared builder — same figure the deck renders.
        st.plotly_chart(charts.fig_update_types(view, top_n=TOP_N), width="stretch")

        if longtail_n > 0:
            st.info(
                f"Long tail: **{longtail_n}** additional update-type values "
                f"(combined **{longtail_count:,}** records) not shown in the chart. "
                f"This cardinality sprawl ({n_ut_full} distinct values across the full snapshot) "
                "is a known data-quality story tracked in the Cockpit.",
                icon="ℹ️",
            )

        # Table of all values
        with st.expander("Show all update types"):
            all_ut = ut_counts.reset_index()
            all_ut.columns = ["update_type", "count"]
            st.dataframe(all_ut, width="stretch")


# ===========================================================================
# v4 — Volume over time
# ===========================================================================
with tabs[TAB["Volume Over Time"]]:
    st.markdown("## Volume Over Time")
    st.markdown(
        "Annotations per period by `reconciled_published_date`. The time axis starts at the "
        "**1% date floor** (matching the Historical Depth headline) so a sparse older tail "
        "doesn't stretch it; tick **Include implausible dates** to show the full range "
        "including out-of-window outliers."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        col_freq, col_implausible = st.columns(2)
        with col_freq:
            freq = st.selectbox(
                "Frequency",
                ["Yearly (YE)", "Quarterly (QE)", "Monthly (ME)"],
                key="vol_freq",
            )
        freq_map = {
            "Monthly (ME)": "ME",
            "Quarterly (QE)": "QE",
            "Yearly (YE)": "YE",
        }
        freq_code = freq_map[freq]

        with col_implausible:
            include_implausible = st.checkbox(
                "Include implausible dates", value=False, key="vol_implausible"
            )

        # Shared builder + frame helper — same figure the deck renders; the
        # caption reads from the same prepared frame so it can't disagree.
        vol_df, vol_floor = charts.volume_frame(
            view, freq_code, floor=True, include_implausible=include_implausible
        )

        if vol_df.empty:
            st.info("No records with plausible dates in the current filter.")
        else:
            st.plotly_chart(
                charts.fig_volume(view, freq_code, floor=True, include_implausible=include_implausible),
                width="stretch",
            )
            floor_note = (
                f" · axis starts at the 1% floor ({vol_floor})" if vol_floor is not None else ""
            )
            st.caption(
                f"Showing {len(vol_df):,} non-empty periods · "
                f"{int(vol_df['count'].sum()):,} records in range{floor_note}."
            )


# ===========================================================================
# v5 — Score distributions
# ===========================================================================
with tabs[TAB["Score Distributions"]]:
    st.markdown("## Score Distributions")
    st.markdown(
        "Distribution of the **impact** score (0–10) — its histogram, confidence, and label "
        "mix. Scores are AI-generated, proving the dataset is scored, not just labelled."
    )
    st.caption(
        "Showing the impact axis. Relevance is a deprecated weighted sum of impact and "
        "urgency and isn't charted; urgency-score detail lives in the Data-Quality Cockpit."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        # Impact-only on the external gallery (urgency detail lives in the Cockpit).
        # Figures via shared builders; the dist dict only drives the "no data" guards.
        dists = score_distributions(view)
        axes = ["impact"]

        # Score histograms — one column per axis
        score_cols = st.columns(len(axes))
        for i, axis in enumerate(axes):
            with score_cols[i]:
                if dists[axis]["scores"]:
                    st.plotly_chart(charts.fig_score_histogram(view, axis), width="stretch")
                else:
                    st.info(f"No {axis} score data.")

        st.divider()

        # Confidence histograms — one column per axis
        st.markdown("### Confidence (0–1)")
        conf_cols = st.columns(len(axes))
        for i, axis in enumerate(axes):
            with conf_cols[i]:
                if dists[axis]["confidence"]:
                    st.plotly_chart(charts.fig_confidence_histogram(view, axis), width="stretch")

        st.divider()

        # Label mix pie / bar — one column per axis
        st.markdown("### Label mix")
        st.caption(
            f"Labels follow the band convention: **low** = score in "
            f"[{LABEL_BANDS['low'][0]:g}, {LABEL_BANDS['low'][1]:g}), "
            f"**medium** = [{LABEL_BANDS['medium'][0]:g}, {LABEL_BANDS['medium'][1]:g}), "
            f"**high** = [{LABEL_BANDS['high'][0]:g}, {LABEL_BANDS['high'][1]:g}]."
        )
        # Render each label-mix pie in a constrained, roughly-square column so a
        # single pie isn't stranded tiny in a full-width container (impact-only → one).
        for axis in axes:
            if dists[axis]["label_counts"]:
                fig_lbl = charts.fig_label_mix(view, axis)
                fig_lbl.update_layout(height=360)
                col_pie, _ = st.columns([2, 3])
                with col_pie:
                    st.plotly_chart(fig_lbl, width="stretch")


# ===========================================================================
# v8 — Single-record richness drill-down (full mode only — not in PUBLIC_BUILD)
# In public mode these tabs don't exist in TABS, so TAB["Record Drill-Down"]
# would KeyError; the guard also ensures build_record_index / get_raw_record
# are never invoked (no JSONL access in public mode).
# ===========================================================================
if not PUBLIC_BUILD:
    with tabs[TAB["Record Drill-Down"]]:
        st.markdown("## Single-Record Richness Drill-Down")
        st.markdown(
            "Select any record from the filtered set and see the **full nested annotation** "
            "rendered as a structured compliance brief — the richness you cannot see in a "
            "list of links."
        )
        richness_definition()

        if view.empty:
            st.warning("No records match the current filters.")
        else:
            record_idx = _build_index()

            # Build display options: title + artifact_id for identification
            title_col = "title" if "title" in view.columns else None
            if title_col:
                options_series = view["artifact_id"].astype(str)
                label_map = dict(
                    zip(
                        view["artifact_id"].astype(str),
                        view[title_col].fillna(view["artifact_id"].astype(str)),
                    )
                )
            else:
                options_series = view["artifact_id"].astype(str)
                label_map = {}

            # Search / filter records
            drill_search = st.text_input(
                "Filter records (search title or artifact_id)",
                value="",
                key="drill_search",
            )
            if drill_search.strip():
                q = drill_search.strip().lower()
                mask = (
                    view["artifact_id"].astype(str).str.lower().str.contains(q, regex=False)
                )
                if title_col:
                    mask |= view[title_col].fillna("").str.lower().str.contains(q, regex=False)
                candidate_ids = view.loc[mask, "artifact_id"].astype(str).tolist()
            else:
                # Default: show top 200 by richness_score for selector performance
                if "richness_score" in view.columns:
                    candidate_ids = (
                        view.nlargest(200, "richness_score")["artifact_id"]
                        .astype(str)
                        .tolist()
                    )
                else:
                    candidate_ids = view["artifact_id"].astype(str).head(200).tolist()

            if not candidate_ids:
                st.info("No records match your search.")
            else:
                def _format_option(aid: str) -> str:
                    title = label_map.get(aid, "")
                    if title and title != aid:
                        return f"{title[:80]}… [{aid[:8]}]" if len(title) > 80 else f"{title} [{aid[:8]}]"
                    return aid[:16]

                selected_id = st.selectbox(
                    f"Select a record ({len(candidate_ids):,} shown)",
                    options=candidate_ids,
                    format_func=_format_option,
                    key="drill_select",
                )

                if selected_id:
                    with st.spinner("Loading record…"):
                        raw = get_raw_record(selected_id, jsonl_path=ANNOTATIONS_JSONL, index=record_idx)

                    if raw is None:
                        st.error(f"Record {selected_id} not found in the JSONL index.")
                    else:
                        output_data = raw.get("output_data") or {}
                        # Show richness score from the normalized frame if available
                        row = view[view["artifact_id"].astype(str) == selected_id]
                        if not row.empty and "richness_score" in row.columns:
                            rs = row.iloc[0]["richness_score"]
                            if pd.notna(rs):
                                st.metric("Richness score", f"{int(rs)}/100")
                        record_drilldown(output_data, envelope=raw)


# ===========================================================================
# v9 — Highlight reel (full mode only — not in PUBLIC_BUILD)
# ===========================================================================
if not PUBLIC_BUILD:
    with tabs[TAB["Highlight Reel"]]:
        st.markdown("## Highlight Reel")
        st.markdown(
            "Auto-selected top records by **deterministic richness score** within the current "
            "filter. Diversity pass: at most one record per institution, then per update-type. "
            "No randomness — reproducible across runs."
        )
        richness_definition()

        if view.empty:
            st.warning("No records match the current filters.")
        elif "richness_score" not in view.columns:
            st.warning("richness_score column not available.")
        else:
            n_reel = st.slider(
                "Number of records in reel",
                min_value=3,
                max_value=20,
                value=9,
                step=1,
                key="reel_n",
            )
            diversify = st.checkbox("Diversify (one per institution)", value=True, key="reel_diversify")

            with st.spinner("Selecting highlight reel…"):
                reel = highlight_reel(view, n=n_reel, diversify=diversify)

            if reel.empty:
                st.info("Not enough records to build a highlight reel with current filters.")
            else:
                st.caption(
                    f"Showing top **{len(reel)}** records by richness score "
                    f"(median={int(view['richness_score'].dropna().median())}/100 "
                    f"in current filter)."
                )

                # Render as cards in a 3-column grid
                card_cols = 3
                for row_start in range(0, len(reel), card_cols):
                    row_cards = reel.iloc[row_start : row_start + card_cols]
                    cols = st.columns(card_cols)
                    for col, (_, record) in zip(cols, row_cards.iterrows()):
                        with col:
                            title = str(record.get("title", "")) if pd.notna(record.get("title", None)) else ""
                            artifact_id = str(record.get("artifact_id", ""))
                            richness = record.get("richness_score", None)
                            impact_score = record.get("impact_score", None)
                            urgency_label = record.get("urgency_label", "")
                            regulator = record.get("regulator_name", "")
                            update_type = record.get("update_type", "")

                            richness_str = f"{int(richness)}/100" if pd.notna(richness) else "—"
                            impact_str = f"{float(impact_score):.1f}" if pd.notna(impact_score) else "—"

                            display_title = (title[:70] + "…") if len(title) > 70 else (title or artifact_id[:16])

                            st.markdown(
                                f'<div style="border:1px solid #e0e0e0;border-radius:8px;'
                                f'padding:12px;height:200px;overflow:hidden;background:#fafafa">'
                                f"<strong>{display_title}</strong><br>"
                                f'<small style="color:#888">{str(regulator)[:40]}</small><br>'
                                f'<small style="color:#888">{str(update_type)}</small><br>'
                                f'<span style="background:#1976d2;color:white;border-radius:4px;'
                                f'padding:2px 6px;font-size:0.8em">Richness: {richness_str}</span> '
                                f'<span style="background:#f57c00;color:white;border-radius:4px;'
                                f'padding:2px 6px;font-size:0.8em">Impact: {impact_str}</span>'
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                            # Link to drill-down via session state
                            if st.button(
                                "View full record",
                                key=f"reel_btn_{artifact_id}",
                                width="stretch",
                            ):
                                st.session_state["drill_select"] = artifact_id
                                st.session_state["_switch_to_drilldown"] = True

            # Handle drill-down navigation from highlight reel
            if st.session_state.get("_switch_to_drilldown"):
                st.session_state["_switch_to_drilldown"] = False
                st.info(
                    "Record selected — switch to the **Record Drill-Down** tab to view it. "
                    f"(artifact_id: `{st.session_state.get('drill_select', '')}`)"
                )


# ===========================================================================
# Tags & Entities (conditional — only when term_stats artifacts exist)
# ===========================================================================
if term_stats is not None:
    with tabs[TAB["Tags & Entities"]]:
        st.subheader("Tags & Entities")
        st.caption(
            "Stats across the full corpus — not affected by the sidebar filters."
        )

        # -----------------------------------------------------------------------
        # Headline tiles — two rows of KPI cards
        # -----------------------------------------------------------------------
        ts_meta = term_stats["meta"]

        # Row 1: corpus-wide counts from the term_stats meta
        st.markdown("### Entity & tag counts (full corpus)")
        kpi_cards(
            {
                "Distinct entities": f"{ts_meta.get('n_distinct_entities', 0):,}",
                "Distinct tags": f"{ts_meta.get('n_distinct_tags', 0):,}",
                "Entity mentions": f"{ts_meta.get('n_entity_mentions', 0):,}",
                "Tag mentions": f"{ts_meta.get('n_tag_mentions', 0):,}",
            }
        )

        # Row 2: per-record density and coverage from the full (unfiltered) frame
        med_entities = int(df_full["n_entities"].median()) if "n_entities" in df_full.columns else 0
        med_tags = int(df_full["n_tags"].median()) if "n_tags" in df_full.columns else 0
        ent_coverage = (df_full["n_entities"] > 0).mean() if "n_entities" in df_full.columns else 0.0
        tag_coverage = (df_full["n_tags"] > 0).mean() if "n_tags" in df_full.columns else 0.0

        kpi_cards(
            {
                "Median entities/record": str(med_entities),
                "Median tags/record": str(med_tags),
                "Entity coverage": f"{ent_coverage:.1%}",
                "Tag coverage": f"{tag_coverage:.1%}",
            }
        )

        st.divider()

        # -----------------------------------------------------------------------
        # Charts — breakdown + entity leaderboard side-by-side, then tag leaderboard
        # -----------------------------------------------------------------------
        col_breakdown, col_entity_lb = st.columns(2)
        with col_breakdown:
            st.plotly_chart(
                charts.fig_entity_type_breakdown(term_stats["breakdown"]),
                width="stretch",
            )
        with col_entity_lb:
            st.plotly_chart(
                charts.fig_entity_leaderboard(term_stats["entity_leaderboard"]),
                width="stretch",
            )

        st.plotly_chart(
            charts.fig_tag_leaderboard(term_stats["tag_leaderboard"]),
            width="stretch",
        )

        st.caption(
            "Entity names are merged best-effort; minor variants of the same body "
            "may occasionally appear separately."
        )
