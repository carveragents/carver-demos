"""Carver Annotation Data Showcase — External Gallery (spec §6).

Entry point:  streamlit run apps/gallery.py

Views (spec §6.2):
  v0   Overview + "What is an annotation" explainer + headline KPIs + historical-depth block
  v1   Jurisdiction & geography breadth (choropleth + bloc/scope bars)
  v1a  Monitored institutions — 1,071 institutions from topic_catalog.csv
  v2   Category → topic structure (sunburst / treemap)
  v3   Update-type mix (top-N bar + long-tail count)
  v4   Volume over time (line/bar by reconciled_published_date)
  v5   Score distributions (histograms + confidence + label mix)
  v6   Urgency basis breakdown (bar)
  v7   Label-vs-score calibration (per-axis band×score heatmap)
  v8   Single-record richness drill-down
  v9   Highlight reel (top-N by richness_score)

Design rules:
  - Cache all data loads with st.cache_data / st.cache_resource.
  - Never call the live API; read cached snapshot only.
  - All views drive from the sidebar-filtered 'view' DataFrame.
  - No per-row Python over 59K rows — use metrics functions.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — allow running from the repo root without installing the package
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from carver_showcase.config import (
    ANNOTATIONS_JSONL,
    ANNOTATIONS_PARQUET,
    ISO_COUNTRY,
    LABEL_BANDS,
    TOPIC_CATALOG_CSV,
    TOPIC_CATEGORIES_CSV,
)
from carver_showcase.load import (
    build_record_index,
    get_raw_record,
    load_catalog,
    load_normalized,
)
from carver_showcase.metrics import (
    breadth_summary,
    historical_depth,
    score_distributions,
    volume_over_time,
)
from carver_showcase.richness import highlight_reel
from apps.components.filters import FilterState, apply_filters, sidebar_filters
from apps.components.theme import AXIS_COLORS, SCORE_AXES
from apps.components.render import (
    kpi_cards,
    record_drilldown,
    sampling_caveat_banner,
)

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
# Cached data loaders (app edge — spec §9.1)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading annotation snapshot…")
def _load_df() -> pd.DataFrame:
    return load_normalized(
        parquet_path=ANNOTATIONS_PARQUET,
        jsonl_path=ANNOTATIONS_JSONL,
        categories_path=TOPIC_CATEGORIES_CSV,
    )


@st.cache_data(show_spinner="Loading institutions catalog…")
def _load_catalog() -> pd.DataFrame:
    return load_catalog(catalog_path=TOPIC_CATALOG_CSV)


@st.cache_resource(show_spinner="Building record index…")
def _build_index() -> dict[str, int]:
    return build_record_index(jsonl_path=ANNOTATIONS_JSONL)


# ---------------------------------------------------------------------------
# App header
# ---------------------------------------------------------------------------
st.title("Carver Annotation Data Showcase")
st.markdown(
    "**Range · Quality · Richness** — explore 58,982 AI-generated regulatory annotations "
    "across Finance, Data protection & cybersecurity, and Medical Devices."
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_full = _load_df()
catalog_df = _load_catalog()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
state: FilterState = sidebar_filters(df_full)
view: pd.DataFrame = apply_filters(df_full, state)

n_filtered = len(view)
if n_filtered < len(df_full):
    st.sidebar.caption(f"{n_filtered:,} of {len(df_full):,} records match current filters.")

# ---------------------------------------------------------------------------
# View tabs
# ---------------------------------------------------------------------------
TABS = [
    "v0 Overview",
    "v1 Geography",
    "v1a Institutions",
    "v2 Category Structure",
    "v3 Update Types",
    "v4 Volume Over Time",
    "v5 Score Distributions",
    "v6 Urgency Basis",
    "v7 Calibration",
    "v8 Record Drill-Down",
    "v9 Highlight Reel",
]

tabs = st.tabs(TABS)


# ===========================================================================
# v0 — Overview + explainer + KPIs + historical-depth + sampling banner
# ===========================================================================
with tabs[0]:
    sampling_caveat_banner()

    st.markdown("## What is a Carver Annotation?")
    st.markdown(
        """
Carver attaches a rich, AI-generated **annotation** to every raw regulatory feed entry.
A raw feed entry is little more than a title, a link, and a date. The annotation turns
it into a machine-readable compliance object with:

| Component | What it captures |
|---|---|
| **Three scored axes** | Impact · Urgency · Relevance — each with a label, numeric score, and confidence |
| **Impact narrative** | Objective · What changed · Why it matters · Risk/impact · Key requirements |
| **Seven actionable lanes** | Policy / Status / Process / Training / Reporting / Tech-data / Other changes |
| **Critical dates** | Effective, compliance, comment-deadline, and other calendar dates |
| **Entities & tags** | Named organisations, officials, and free-text topic tags |
| **Regulatory references** | Rules, statutes, precedents, personnel, past releases |
| **Jurisdiction classification** | Country, bloc, scope — with explicit reasoning |
| **Impacted business & functions** | Industry, business type, and functions affected |
| **Penalties & consequences** | Enforcement implications |

Every field below is computed over the **58,982-record stratified snapshot** — not hard-coded.
"""
    )
    st.divider()

    # Headline KPIs
    bs = breadth_summary(view)
    cat_counts = bs.get("category_counts", {})
    total_records = len(view)

    richness_median = (
        int(view["richness_score"].dropna().median())
        if "richness_score" in view.columns and not view["richness_score"].dropna().empty
        else "—"
    )
    pct_full_score = (
        view[["impact_score", "urgency_score", "relevance_score"]].notna().all(axis=1).mean()
        if all(c in view.columns for c in ["impact_score", "urgency_score", "relevance_score"])
        else 0.0
    )

    st.markdown("### Headline KPIs (current filter)")
    kpi_cards(
        {
            "Records": f"{total_records:,}",
            "Topics": f"{bs['n_topics']:,}",
            "Countries": f"{bs['n_countries']:,}",
            "Regulators": f"{bs['n_regulators']:,}",
            "Update types": f"{bs['n_update_types']:,}",
        }
    )
    kpi_cards(
        {
            "Median richness score": f"{richness_median}/100",
            "% with full score trio": f"{pct_full_score:.1%}",
            "Finance records": f"{cat_counts.get('Finance', 0):,}",
            "Data protection records": f"{cat_counts.get('Data protection and cybersecurity', 0):,}",
            "Medical Devices records": f"{cat_counts.get('Medical Devices', 0):,}",
        }
    )

    st.divider()

    # Historical depth block (spec §6.2 v0, G5)
    st.markdown("### Historical Depth")
    st.caption(
        "Earliest and latest plausible record dates, data span, and recency distribution. "
        "Implausible dates (outside 1990–present+2y) are excluded here; they surface "
        "only as anomalies in the Data-Quality Cockpit."
    )
    hd = historical_depth(view)
    if hd["earliest_date"] is not None:
        span_years = round((hd["span_days"] or 0) / 365.25, 1)
        kpi_cards(
            {
                "Earliest plausible record": str(hd["earliest_date"]),
                "Latest plausible record": str(hd["latest_date"]),
                "Data span": f"{span_years} years",
                "Plausible records": f"{hd['n_plausible']:,}",
                "Implausible (excluded)": f"{hd['n_implausible']:,}",
            }
        )
        rec = hd["recency"]
        kpi_cards(
            {
                "Within last 1 year": f"{rec['pct_1y']:.1%}",
                "Within last 3 years": f"{rec['pct_3y']:.1%}",
                "Within last 7 years": f"{rec['pct_7y']:.1%}",
            }
        )
        st.info(
            "**Recency note:** The bulk of records are from 2024–2026 (strongly "
            "recency-skewed); there is a thin but genuine pre-2000 tail. The "
            "advertised earliest date excludes known garbage extremes (e.g. "
            "1947-12-25, 2105-07-01 — those are anomalies, not real coverage).",
            icon="ℹ️",
        )
    else:
        st.info("No plausible dates in the current filter selection.")


# ===========================================================================
# v1 — Jurisdiction & geography breadth
# ===========================================================================
with tabs[1]:
    st.markdown("## v1 — Jurisdiction & Geography Breadth")
    st.markdown(
        "Shows the global reach of the annotation dataset. "
        "Each dot on the map and each bar reflects records in the **current filter**."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        # --- Choropleth ---
        st.markdown("### Country-level record count")

        country_counts = (
            view["jurisdiction_country"]
            .dropna()
            .value_counts()
            .reset_index()
        )
        country_counts.columns = ["iso2", "count"]

        # Map ISO-2 → ISO-3 (needed by Plotly choropleth)
        country_counts["iso3"] = country_counts["iso2"].map(
            lambda x: ISO_COUNTRY.get(x, {}).get("iso3")
        )
        country_counts["name"] = country_counts["iso2"].map(
            lambda x: ISO_COUNTRY.get(x, {}).get("name", x)
        )

        n_not_mappable = int(country_counts["iso3"].isna().sum())
        mappable = country_counts.dropna(subset=["iso3"])

        if not mappable.empty:
            fig_map = px.choropleth(
                mappable,
                locations="iso3",
                color="count",
                hover_name="name",
                hover_data={"iso3": False, "iso2": True, "count": True},
                color_continuous_scale="Blues",
                labels={"count": "Records"},
                title="Records by country (mapped jurisdictions only)",
            )
            fig_map.update_layout(
                geo=dict(showframe=False, showcoastlines=True),
                margin=dict(l=0, r=0, t=40, b=0),
                height=420,
            )
            st.plotly_chart(fig_map, width="stretch")
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
        top_countries = country_counts.nlargest(20, "count")
        if not top_countries.empty:
            fig_bar = px.bar(
                top_countries,
                x="count",
                y="name",
                orientation="h",
                labels={"count": "Records", "name": "Country"},
                title="Top 20 countries",
            )
            fig_bar.update_layout(yaxis=dict(autorange="reversed"), height=420)
            st.plotly_chart(fig_bar, width="stretch")

        col1, col2 = st.columns(2)

        # --- Bloc bar ---
        with col1:
            st.markdown("### Jurisdiction bloc")
            bloc_counts = (
                view["jurisdiction_bloc"]
                .dropna()
                .value_counts()
                .head(15)
                .reset_index()
            )
            bloc_counts.columns = ["bloc", "count"]
            if not bloc_counts.empty:
                fig_bloc = px.bar(
                    bloc_counts,
                    x="count",
                    y="bloc",
                    orientation="h",
                    labels={"count": "Records", "bloc": "Bloc"},
                    title=f"Top blocs (of {view['jurisdiction_bloc'].dropna().nunique()} total)",
                )
                fig_bloc.update_layout(yaxis=dict(autorange="reversed"), height=350)
                st.plotly_chart(fig_bloc, width="stretch")
            else:
                st.info("No bloc data in current filter.")

        # --- Scope bar ---
        with col2:
            st.markdown("### Jurisdiction scope")
            scope_counts = (
                view["jurisdiction_scope"]
                .dropna()
                .value_counts()
                .reset_index()
            )
            scope_counts.columns = ["scope", "count"]
            if not scope_counts.empty:
                fig_scope = px.bar(
                    scope_counts,
                    x="scope",
                    y="count",
                    labels={"count": "Records", "scope": "Scope"},
                    title="Records by jurisdiction scope",
                )
                st.plotly_chart(fig_scope, width="stretch")
            else:
                st.info("No scope data in current filter.")


# ===========================================================================
# v1a — Monitored institutions (G4)
# ===========================================================================
with tabs[2]:
    st.markdown("## v1a — Monitored Institutions")
    st.info(
        "**Three populations — never conflated:** "
        "**Monitored universe = 1,071** institutions (full topics catalog) ⊃ "
        "**Categorized = 610** topics (three showcased categories) ⊃ "
        "**Present in this sample = 405** topics (those appearing in the 58,982-record snapshot). "
        "The table below shows ALL 1,071 monitored institutions with a "
        "`records_in_sample` count — 0 means not present in the snapshot.",
        icon="ℹ️",
    )

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
            "scope", "category", "records_in_sample",
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
            ["records_in_sample", "name", "jurisdiction_code", "category"],
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

        with col_c:
            by_country = (
                inst_df["jurisdiction_code"]
                .dropna()
                .value_counts()
                .head(20)
                .reset_index()
            )
            by_country.columns = ["country", "institutions"]
            if not by_country.empty:
                fig_c = px.bar(
                    by_country,
                    x="institutions",
                    y="country",
                    orientation="h",
                    labels={"institutions": "Institutions", "country": "Country"},
                    title="Top 20 countries by institution count",
                )
                fig_c.update_layout(yaxis=dict(autorange="reversed"), height=380)
                st.plotly_chart(fig_c, width="stretch")

        with col_t:
            # entity_type can contain semicolon-separated values — split and count
            all_types: list[str] = []
            for val in inst_df["entity_type"].dropna():
                all_types.extend([t.strip() for t in str(val).split(";") if t.strip()])
            if all_types:
                type_counts = (
                    pd.Series(all_types)
                    .value_counts()
                    .head(15)
                    .reset_index()
                )
                type_counts.columns = ["entity_type", "count"]
                fig_t = px.bar(
                    type_counts,
                    x="count",
                    y="entity_type",
                    orientation="h",
                    labels={"count": "Institutions", "entity_type": "Regulator type"},
                    title="Top regulator types",
                )
                fig_t.update_layout(yaxis=dict(autorange="reversed"), height=380)
                st.plotly_chart(fig_t, width="stretch")

        with col_s:
            by_scope = (
                inst_df["scope"]
                .dropna()
                .value_counts()
                .reset_index()
            )
            by_scope.columns = ["scope", "count"]
            if not by_scope.empty:
                fig_s = px.bar(
                    by_scope,
                    x="scope",
                    y="count",
                    labels={"count": "Institutions", "scope": "Scope"},
                    title="Institutions by scope",
                )
                st.plotly_chart(fig_s, width="stretch")


# ===========================================================================
# v2 — Category → topic structure
# ===========================================================================
with tabs[3]:
    st.markdown("## v2 — Category → Topic Structure")
    st.markdown(
        "Taxonomic breadth: the three showcased categories and their constituent topics. "
        "Category is catalog-sourced (≈100% mapped); any unmapped topics render as "
        "'Uncategorized'."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        cat_topic = (
            view.groupby(["category", "topic_id"])
            .size()
            .reset_index(name="count")
        )

        # Sunburst: category → topic_id (labeled by topic_id for now)
        if not cat_topic.empty:
            col_chart, col_info = st.columns([3, 1])
            with col_chart:
                fig_sun = px.sunburst(
                    cat_topic,
                    path=["category", "topic_id"],
                    values="count",
                    title="Records by category → topic (sunburst)",
                    color="count",
                    color_continuous_scale="Blues",
                )
                fig_sun.update_layout(height=520)
                st.plotly_chart(fig_sun, width="stretch")

            with col_info:
                st.markdown("**Category summary**")
                for cat, grp in cat_topic.groupby("category"):
                    st.metric(
                        label=str(cat),
                        value=f"{grp['count'].sum():,} records",
                        delta=f"{len(grp):,} topics",
                    )

        st.markdown("### Topic volume (top 30 by record count)")
        topic_bar = (
            view["topic_id"]
            .dropna()
            .value_counts()
            .head(30)
            .reset_index()
        )
        topic_bar.columns = ["topic_id", "count"]
        # Join name from catalog if available
        if not catalog_df.empty and "topic_id" in catalog_df.columns:
            name_map = catalog_df.set_index("topic_id")["name"].to_dict()
            topic_bar["label"] = topic_bar["topic_id"].map(
                lambda x: name_map.get(x, x)
            )
        else:
            topic_bar["label"] = topic_bar["topic_id"]

        fig_topic = px.bar(
            topic_bar,
            x="count",
            y="label",
            orientation="h",
            labels={"count": "Records", "label": "Topic"},
            title="Top 30 topics by record count",
        )
        fig_topic.update_layout(yaxis=dict(autorange="reversed"), height=520)
        st.plotly_chart(fig_topic, width="stretch")


# ===========================================================================
# v3 — Update-type mix
# ===========================================================================
with tabs[4]:
    st.markdown("## v3 — Update-Type Mix")
    st.markdown(
        "Distribution of `update_type` in the current filter. "
        "The long tail (56 distinct values in the full snapshot) is shown honestly."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        TOP_N = 25
        ut_counts = view["update_type"].dropna().value_counts()
        top_ut = ut_counts.head(TOP_N).reset_index()
        top_ut.columns = ["update_type", "count"]
        longtail_n = max(0, len(ut_counts) - TOP_N)
        longtail_count = int(ut_counts.iloc[TOP_N:].sum()) if longtail_n > 0 else 0

        fig_ut = px.bar(
            top_ut,
            x="count",
            y="update_type",
            orientation="h",
            labels={"count": "Records", "update_type": "Update type"},
            title=f"Top {TOP_N} update types by record count",
        )
        fig_ut.update_layout(yaxis=dict(autorange="reversed"), height=520)
        st.plotly_chart(fig_ut, width="stretch")

        if longtail_n > 0:
            st.info(
                f"Long tail: **{longtail_n}** additional update-type values "
                f"(combined **{longtail_count:,}** records) not shown in the chart. "
                "This cardinality sprawl (56 distinct values in the full snapshot) "
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
with tabs[5]:
    st.markdown("## v4 — Volume Over Time")
    st.markdown(
        "Annotations per month by `reconciled_published_date`. "
        "Implausible dates (outside 1990–present+2y) are excluded by default."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        col_freq, col_implausible = st.columns(2)
        with col_freq:
            freq = st.selectbox(
                "Frequency",
                ["Monthly (ME)", "Quarterly (QE)", "Yearly (YE)"],
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

        vol_df = volume_over_time(
            view,
            freq=freq_code,
            exclude_implausible=not include_implausible,
        )

        if vol_df.empty:
            st.info("No records with plausible dates in the current filter.")
        else:
            fig_vol = px.bar(
                vol_df,
                x="period",
                y="count",
                labels={"period": "Period", "count": "Annotations"},
                title=f"Annotations per period ({freq})",
            )
            fig_vol.update_layout(height=400)
            st.plotly_chart(fig_vol, width="stretch")

            st.caption(
                f"Showing {len(vol_df):,} non-empty periods · "
                f"{int(vol_df['count'].sum()):,} total records with plausible dates."
            )


# ===========================================================================
# v5 — Score distributions
# ===========================================================================
with tabs[6]:
    st.markdown("## v5 — Score Distributions")
    st.markdown(
        "Histograms of impact, urgency, and relevance scores (0–10) with "
        "confidence overlays and label mix. Scores are AI-generated — "
        "this view proves the dataset is scored, not just labelled."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        dists = score_distributions(view)
        axes = SCORE_AXES
        axis_labels = {a: a.capitalize() for a in SCORE_AXES}
        axis_colors = AXIS_COLORS

        # Score histograms in 3 columns
        score_cols = st.columns(3)
        for i, axis in enumerate(axes):
            with score_cols[i]:
                scores = dists[axis]["scores"]
                if scores:
                    fig_s = px.histogram(
                        x=scores,
                        nbins=20,
                        labels={"x": f"{axis_labels[axis]} score"},
                        title=f"{axis_labels[axis]} score distribution",
                        color_discrete_sequence=[axis_colors[axis]],
                    )
                    fig_s.update_layout(showlegend=False, height=280)
                    st.plotly_chart(fig_s, width="stretch")
                else:
                    st.info(f"No {axis} score data.")

        st.divider()

        # Confidence histograms in 3 columns
        st.markdown("### Confidence (0–1)")
        conf_cols = st.columns(3)
        for i, axis in enumerate(axes):
            with conf_cols[i]:
                confs = dists[axis]["confidence"]
                if confs:
                    fig_c = px.histogram(
                        x=confs,
                        nbins=20,
                        labels={"x": f"{axis_labels[axis]} confidence"},
                        title=f"{axis_labels[axis]} confidence",
                        color_discrete_sequence=[axis_colors[axis]],
                    )
                    fig_c.update_layout(showlegend=False, height=280)
                    st.plotly_chart(fig_c, width="stretch")

        st.divider()

        # Label mix pie / bar in 3 columns
        st.markdown("### Label mix")
        label_cols = st.columns(3)
        for i, axis in enumerate(axes):
            with label_cols[i]:
                label_counts = dists[axis]["label_counts"]
                if label_counts:
                    ldf = pd.DataFrame(
                        list(label_counts.items()), columns=["label", "count"]
                    )
                    fig_l = px.pie(
                        ldf,
                        names="label",
                        values="count",
                        title=f"{axis_labels[axis]} label mix",
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig_l.update_layout(height=260)
                    st.plotly_chart(fig_l, width="stretch")


# ===========================================================================
# v6 — Urgency basis breakdown
# ===========================================================================
with tabs[7]:
    st.markdown("## v6 — Urgency Basis Breakdown")
    st.markdown(
        "Every urgency score carries an explicit `basis` value — showing that "
        "urgency is *reasoned*, not guessed."
    )

    if view.empty:
        st.warning("No records match the current filters.")
    elif "urgency_basis" not in view.columns:
        st.warning("urgency_basis column not found in the dataset.")
    else:
        basis_counts = (
            view["urgency_basis"]
            .dropna()
            .value_counts()
            .reset_index()
        )
        basis_counts.columns = ["urgency_basis", "count"]

        if basis_counts.empty:
            st.info("No urgency_basis data in current filter.")
        else:
            col_bar, col_pie = st.columns([2, 1])
            with col_bar:
                fig_basis_bar = px.bar(
                    basis_counts,
                    x="urgency_basis",
                    y="count",
                    labels={"urgency_basis": "Urgency basis", "count": "Records"},
                    title="Urgency basis distribution",
                    color="urgency_basis",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_basis_bar.update_layout(showlegend=False, height=350)
                st.plotly_chart(fig_basis_bar, width="stretch")

            with col_pie:
                fig_basis_pie = px.pie(
                    basis_counts,
                    names="urgency_basis",
                    values="count",
                    title="Basis share",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_basis_pie.update_layout(height=350)
                st.plotly_chart(fig_basis_pie, width="stretch")

            st.markdown(
                "| Basis | Meaning |\n"
                "|---|---|\n"
                "| `no_future_date` | No future action date found — urgency derives from publication alone |\n"
                "| `past_deadline` | A key deadline has already passed |\n"
                "| `future_deadline` | An upcoming deadline drives urgency |\n"
                "| `effective_immediately` | Regulation takes effect immediately |\n"
            )


# ===========================================================================
# v7 — Label-vs-score calibration
# ===========================================================================
with tabs[8]:
    st.markdown("## v7 — Label-vs-Score Calibration")
    st.markdown(
        "Per-axis heatmap of the assigned label vs. the expected band given the numeric "
        "score (A2 convention: low=[0,4), medium=[4,7), high=[7,10]). "
        "Off-diagonal cells are mismatches — framed as **calibration** (not errors), "
        "and tracked in the Data-Quality Cockpit."
    )

    def _expected_band(score):
        """Band for an in-range score using the canonical config.LABEL_BANDS
        (spec A2; high inclusive of its upper bound). Out-of-range → None, matching
        quality.label_score_mismatch (those are caught by score_out_of_range)."""
        lo_min = LABEL_BANDS["low"][0]
        hi_max = LABEL_BANDS["high"][1]
        if score < lo_min or score > hi_max:
            return None
        if score < LABEL_BANDS["low"][1]:
            return "low"
        if score < LABEL_BANDS["medium"][1]:
            return "medium"
        return "high"

    if view.empty:
        st.warning("No records match the current filters.")
    else:
        calib_axes = SCORE_AXES
        calib_cols = st.columns(3)

        for i, axis in enumerate(calib_axes):
            with calib_cols[i]:
                score_col = f"{axis}_score"
                label_col = f"{axis}_label"
                if score_col not in view.columns or label_col not in view.columns:
                    st.info(f"No {axis} data.")
                    continue

                sub = view[[score_col, label_col]].dropna()
                if sub.empty:
                    st.info(f"No {axis} data.")
                    continue

                sub = sub.copy()
                sub["expected_band"] = (
                    pd.to_numeric(sub[score_col], errors="coerce")
                    .map(lambda v: _expected_band(v) if pd.notna(v) else None)
                )
                sub = sub.dropna(subset=["expected_band"])

                heatmap_data = (
                    sub.groupby([label_col, "expected_band"])
                    .size()
                    .unstack(fill_value=0)
                )
                band_order = ["low", "medium", "high"]
                heatmap_data = heatmap_data.reindex(
                    index=[b for b in band_order if b in heatmap_data.index],
                    columns=[b for b in band_order if b in heatmap_data.columns],
                    fill_value=0,
                )

                if heatmap_data.empty:
                    st.info(f"Not enough {axis} data to render calibration.")
                    continue

                fig_hm = px.imshow(
                    heatmap_data,
                    labels={
                        "x": "Expected band (from score)",
                        "y": "Assigned label",
                        "color": "Records",
                    },
                    title=f"{axis.capitalize()} calibration",
                    color_continuous_scale="Blues",
                    text_auto=True,
                )
                fig_hm.update_layout(height=260)
                st.plotly_chart(fig_hm, width="stretch")

        n_mismatch = 0
        for axis in calib_axes:
            score_col = f"{axis}_score"
            label_col = f"{axis}_label"
            if score_col in view.columns and label_col in view.columns:
                sub = view[[score_col, label_col]].dropna().copy()
                sub["expected"] = pd.to_numeric(sub[score_col], errors="coerce").map(
                    lambda v: _expected_band(v) if pd.notna(v) else None
                )
                sub = sub.dropna(subset=["expected"])
                n_mismatch += int((sub[label_col] != sub["expected"]).sum())

        if n_mismatch > 0:
            st.caption(
                f"Total label-score mismatches across all three axes in current filter: "
                f"**{n_mismatch:,}**. "
                "These are tracked and triaged in the Data-Quality Cockpit."
            )


# ===========================================================================
# v8 — Single-record richness drill-down
# ===========================================================================
with tabs[9]:
    st.markdown("## v8 — Single-Record Richness Drill-Down")
    st.markdown(
        "Select any record from the filtered set and see the **full nested annotation** "
        "rendered as a structured compliance brief — the richness you cannot see in a "
        "list of links."
    )

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
# v9 — Highlight reel
# ===========================================================================
with tabs[10]:
    st.markdown("## v9 — Highlight Reel")
    st.markdown(
        "Auto-selected top records by **deterministic richness score** within the current "
        "filter. Diversity pass: at most one record per topic, then per update-type. "
        "No randomness — reproducible across runs."
    )

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
        diversify = st.checkbox("Diversify (one per topic)", value=True, key="reel_diversify")

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
                        category = record.get("category", "")
                        regulator = record.get("regulator_name", "")
                        update_type = record.get("update_type", "")

                        richness_str = f"{int(richness)}/100" if pd.notna(richness) else "—"
                        impact_str = f"{float(impact_score):.1f}" if pd.notna(impact_score) else "—"

                        display_title = (title[:70] + "…") if len(title) > 70 else (title or artifact_id[:16])

                        st.markdown(
                            f'<div style="border:1px solid #e0e0e0;border-radius:8px;'
                            f'padding:12px;height:200px;overflow:hidden;background:#fafafa">'
                            f"<strong>{display_title}</strong><br>"
                            f'<small style="color:#666">{str(category)}</small><br>'
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
                "Record selected — switch to the **v8 Record Drill-Down** tab to view it. "
                f"(artifact_id: `{st.session_state.get('drill_select', '')}`)"
            )
