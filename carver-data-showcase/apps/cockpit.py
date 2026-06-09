"""Data-Quality Cockpit — internal Streamlit app for the Carver QA team.

Spec §7 (all views 7.1–7.7). Audience: internal cleanup/migration team.
Tone: diagnostic and actionable — find problems, triage, export.

Views
-----
7.1  Coverage matrix — field population % sliced by category / update_type /
     jurisdiction_country; heatmap coloring; catalog cross-check note.
7.2  Gap finder / cleanup queue — filterable table of records failing ≥1
     predicate; CSV download; feed_url triage links.
7.3  Anomaly & consistency panel — one row per rule, sorted by count;
     expandable drill-down of offending records.
7.4  Field-health / cardinality — update_type sprawl + rare list;
     regulator near-dup canonical groups; jurisdiction_country validity.
7.5  Distribution / outlier — score distributions re-framed for QA (spikes at
     0/10, degenerate confidence); prose-length distribution; richness
     distribution to find empty-shell records.
7.6  Coverage-over-time trend — field population % by month/quarter.
7.7  Deprecation / migration tracker — residual jurisdiction_tier legacy count
     and its breakdown by category.

Design notes
------------
- No live API, no LLM: cached snapshot only.
- cache_data wraps load_normalized, load_catalog, predicate_flags, and
  anomaly_report so they are computed once per session.
- Sidebar filters drive 7.1 and 7.2 (coverage matrix + cleanup queue);
  7.3–7.7 run over the full (unfiltered) frame for global health reporting.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from carver_showcase.load import load_catalog, load_normalized
from carver_showcase.metrics import (
    coverage_matrix,
    score_distributions,
    volume_over_time,
)
from carver_showcase.quality import anomaly_report, cleanup_queue, predicate_flags
from apps.components.filters import apply_filters, sidebar_filters
from apps.components.render import kpi_cards, sampling_caveat_banner
from apps.components.theme import AXIS_COLORS


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Carver Data-Quality Cockpit",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Cached loaders — framework boundary: st.cache_data lives here, not in load.py
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading annotations parquet…")
def _load_df() -> pd.DataFrame:
    return load_normalized()


@st.cache_data(show_spinner="Loading topic catalog…")
def _load_catalog_df() -> pd.DataFrame:
    return load_catalog()


@st.cache_data(show_spinner="Computing predicate flags…")
def _predicate_flags_cached() -> pd.DataFrame:
    """Predicate flags over the full snapshot, computed once per session.

    Zero-arg: the snapshot is an immutable cached singleton (``_load_df`` is
    itself ``@st.cache_data``), so a keyless cache computes once and reuses the
    result for the session — no DataFrame hashing or ``id()`` proxy needed.
    """
    return predicate_flags(_full_df)


@st.cache_data(show_spinner="Running anomaly rules…")
def _anomaly_report_cached() -> dict:
    """Anomaly report over the full snapshot, computed once per session."""
    return anomaly_report(_full_df)


# ---------------------------------------------------------------------------
# Load data (once per session)
# ---------------------------------------------------------------------------

_full_df = _load_df()
_catalog_df = _load_catalog_df()

# Compute quality artifacts once over the full frame
_flags_df = _predicate_flags_cached()
_anomalies = _anomaly_report_cached()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Carver Data-Quality Cockpit")
st.caption("Internal tool — for the cleanup and migration team only.")
sampling_caveat_banner()

st.markdown("---")

# ---------------------------------------------------------------------------
# Sidebar filters — drive coverage matrix + cleanup queue
# ---------------------------------------------------------------------------

filter_state = sidebar_filters(_full_df)
filtered_df = apply_filters(_full_df, filter_state)

n_total = len(_full_df)
n_filtered = len(filtered_df)
if n_filtered < n_total:
    st.sidebar.info(f"Filtered: {n_filtered:,} / {n_total:,} records")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_labels = [
    "7.1 Coverage Matrix",
    "7.2 Cleanup Queue",
    "7.3 Anomaly Panel",
    "7.4 Field Health",
    "7.5 Distributions",
    "7.6 Coverage Trend",
    "7.7 Migration Tracker",
]
tabs = st.tabs(tab_labels)


# ============================================================
# 7.1  Coverage matrix
# ============================================================

with tabs[0]:
    st.subheader("Coverage Matrix")
    st.markdown(
        "Field population % overall and by selected slice dimension. "
        "**Red = sparse** (below 50%), amber 50–80%, green ≥80%. "
        "Uses the sidebar-filtered subset."
    )

    slice_dim = st.selectbox(
        "Slice dimension",
        options=["(none)", "category", "update_type", "jurisdiction_country"],
        index=0,
        key="cov_slice_dim",
    )
    slice_arg: Optional[str] = None if slice_dim == "(none)" else slice_dim

    # Field groups to surface (ordered, meaningful to a QA operator)
    FIELD_GROUPS: dict[str, list[str]] = {
        "Scores": [
            "impact_score", "impact_confidence",
            "urgency_score", "urgency_confidence",
            "relevance_score", "relevance_confidence",
            "urgency_basis",
        ],
        "Classification": [
            "update_type", "update_subtype",
            "regulator_name",
            "jurisdiction_country", "jurisdiction_scope",
            "jurisdiction_bloc",
        ],
        "Source / linkability": [
            "feed_url", "title",
        ],
        "Prose / impact summary": [
            "has_impact_summary", "has_objective", "has_what_changed",
            "has_why_it_matters", "has_risk_impact",
        ],
        "Dates": [
            "effective_date", "compliance_date", "comment_deadline",
            "pub_date_content",
        ],
        "Regulatory refs": [
            "n_reg_rules", "n_reg_statutes", "n_reg_other_ref",
        ],
        "Richness": [
            "richness_score", "n_actionable_lanes",
            "n_entities", "n_tags",
            "has_impacted_business", "n_impacted_functions",
            "has_penalties",
        ],
    }

    cov = coverage_matrix(filtered_df, slice_by=slice_arg)
    # Keep only fields present in the frame
    all_qa_fields = [f for grp in FIELD_GROUPS.values() for f in grp if f in cov.index]
    cov_display = cov.loc[all_qa_fields].copy() if all_qa_fields else cov.copy()

    # Add group label column
    field_to_group = {
        f: grp
        for grp, fields in FIELD_GROUPS.items()
        for f in fields
    }
    cov_display.insert(0, "Group", [field_to_group.get(f, "Other") for f in cov_display.index])

    # Build styled display
    pct_cols = [c for c in cov_display.columns if c != "Group"]

    def _color_pct(val: float) -> str:
        if pd.isna(val):
            return ""
        pct = float(val)
        if pct < 0.5:
            return "background-color: #ffcdd2"  # red
        if pct < 0.8:
            return "background-color: #fff9c4"  # amber
        return "background-color: #c8e6c9"  # green

    formatted = cov_display.copy()
    for col in pct_cols:
        formatted[col] = formatted[col].map(
            lambda v: f"{v:.1%}" if pd.notna(v) else "—"
        )

    st.dataframe(
        formatted.reset_index().rename(columns={"field": "Field"}),
        hide_index=True,
        width="stretch",
        height=min(600, 35 * len(formatted) + 40),
    )

    # ------ Catalog cross-check note ------
    st.markdown("---")
    st.markdown("#### Catalog cross-check")
    st.caption(
        "Institutions from the topics catalog with missing metadata or 0 records "
        "in this sample are quality/coverage targets."
    )

    if not _catalog_df.empty:
        # Count sample records per topic_id from the FULL frame (not filtered)
        topic_counts = (
            _full_df["topic_id"]
            .value_counts()
            .reset_index()
            .rename(columns={"topic_id": "topic_id", "count": "sample_records"})
        )
        cat_check = _catalog_df.merge(topic_counts, on="topic_id", how="left")
        cat_check["sample_records"] = cat_check["sample_records"].fillna(0).astype(int)

        # Missing jurisdiction_code
        missing_jc = cat_check["jurisdiction_code"].isna() | (cat_check["jurisdiction_code"] == "")
        n_missing_jc = int(missing_jc.sum())

        # Missing entity_type
        missing_et_col = "entity_type" if "entity_type" in cat_check.columns else None
        n_missing_et = 0
        if missing_et_col:
            missing_et = cat_check[missing_et_col].isna() | (cat_check[missing_et_col] == "")
            n_missing_et = int(missing_et.sum())

        # Zero records in sample
        zero_recs = cat_check[cat_check["sample_records"] == 0]
        n_zero = len(zero_recs)

        cols = st.columns(3)
        cols[0].metric("Missing jurisdiction_code", f"{n_missing_jc:,}", help="Catalog institutions with no country code")
        cols[1].metric("Missing entity_type", f"{n_missing_et:,}", help="Catalog institutions with no entity type")
        cols[2].metric("0 records in this sample", f"{n_zero:,}", help="Monitored institutions absent from the 58,982-record slice")

        if n_zero > 0:
            with st.expander(f"Institutions with 0 sample records ({n_zero:,})"):
                show_cols = [c for c in ["topic_id", "name", "category", "jurisdiction_code"] if c in zero_recs.columns]
                st.dataframe(zero_recs[show_cols].reset_index(drop=True), width="stretch")
    else:
        st.warning("topic_catalog.csv not found — skipping catalog cross-check.")


# ============================================================
# 7.2  Gap finder / cleanup queue
# ============================================================

with tabs[1]:
    st.subheader("Gap Finder / Cleanup Queue")
    st.markdown(
        "Records failing one or more quality predicates. "
        "Rows with no `feed_url` are harder to action (≈46% of the corpus). "
        "Use sidebar filters to narrow the scope, then export the queue as CSV."
    )

    from carver_showcase.quality import PREDICATE_COLUMNS  # noqa: PLC0415

    # Queue filter controls (in addition to sidebar)
    col_p, col_c, col_u, col_j = st.columns(4)
    with col_p:
        pred_filter = st.multiselect(
            "Filter by predicate",
            options=PREDICATE_COLUMNS,
            default=[],
            key="queue_pred",
        )
    with col_c:
        cat_opts = sorted(_full_df["category"].dropna().unique().tolist())
        cat_filter = st.multiselect("Category", options=cat_opts, default=[], key="queue_cat")
    with col_u:
        ut_opts = sorted(_full_df["update_type"].dropna().unique().tolist())
        ut_filter = st.multiselect("Update type", options=ut_opts, default=[], key="queue_ut")
    with col_j:
        jc_opts = sorted(_full_df["jurisdiction_country"].dropna().unique().tolist())
        jc_filter = st.multiselect("Country", options=jc_opts, default=[], key="queue_jc")

    # Apply queue-level narrowing on top of the sidebar-filtered df
    queue_df = filtered_df.copy()
    if cat_filter:
        queue_df = queue_df[queue_df["category"].isin(cat_filter)]
    if ut_filter:
        queue_df = queue_df[queue_df["update_type"].isin(ut_filter)]
    if jc_filter:
        queue_df = queue_df[queue_df["jurisdiction_country"].isin(jc_filter)]

    pred_arg = pred_filter if pred_filter else None
    queue = cleanup_queue(queue_df, predicates=pred_arg)

    if queue.empty:
        st.success("No records match the current filter criteria — queue is empty.")
    else:
        n_queue = len(queue)
        n_no_url = int(queue["feed_url"].isna().sum()) if "feed_url" in queue.columns else 0
        st.markdown(
            f"**{n_queue:,} records** in queue · "
            f"**{n_no_url:,} ({n_no_url / n_queue:.0%})** have no `feed_url` (harder to triage)"
        )

        # Make feed_url clickable via HTML (Streamlit doesn't support link columns natively)
        display_queue = queue.copy()
        if "feed_url" in display_queue.columns:
            display_queue["feed_url"] = display_queue["feed_url"].apply(
                lambda u: f"[link]({u})" if pd.notna(u) and str(u).startswith("http") else "—"
            )

        st.dataframe(
            display_queue,
            width="stretch",
            height=400,
        )

        # CSV download
        csv_bytes = queue.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download cleanup queue as CSV",
            data=csv_bytes,
            file_name="cleanup_queue.csv",
            mime="text/csv",
        )

    # Predicate summary bar
    st.markdown("---")
    st.markdown("#### Predicate hit summary (filtered frame)")
    flags_filtered = predicate_flags(filtered_df)
    pred_counts = flags_filtered.sum().sort_values(ascending=False)
    pred_pct = (pred_counts / max(len(filtered_df), 1) * 100).round(1)
    pred_summary = pd.DataFrame({
        "Predicate": pred_counts.index,
        "Count": pred_counts.values,
        "Pct": pred_pct.values,
    })
    fig_pred = px.bar(
        pred_summary,
        x="Predicate",
        y="Count",
        text="Pct",
        labels={"Count": "Records failing", "Pct": "%"},
        color="Count",
        color_continuous_scale="Reds",
        title="Records failing each predicate",
    )
    fig_pred.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_pred.update_layout(showlegend=False, height=350, coloraxis_showscale=False)
    st.plotly_chart(fig_pred, width="stretch")


# ============================================================
# 7.3  Anomaly & consistency panel
# ============================================================

with tabs[2]:
    st.subheader("Anomaly & Consistency Panel")
    st.markdown(
        "One row per deterministic rule, sorted biggest-count-first. "
        "Expand a rule to inspect the offending records. "
        "Computed over the **full frame** (not sidebar-filtered)."
    )

    # Build summary table
    rule_rows = []
    for rule_name, rule_data in _anomalies.items():
        rule_rows.append({
            "Rule": rule_name,
            "Count": rule_data["count"],
            "% of corpus": f"{rule_data['count'] / max(n_total, 1):.2%}",
        })

    anomaly_summary = pd.DataFrame(rule_rows).sort_values("Count", ascending=False).reset_index(drop=True)
    st.dataframe(anomaly_summary, width="stretch", hide_index=True)

    # Drill-down expanders per rule (only when count > 0)
    st.markdown("---")
    st.markdown("#### Drill-down by rule")

    for _, row in anomaly_summary.iterrows():
        rule = row["Rule"]
        count = row["Count"]
        rule_data = _anomalies[rule]
        offending = rule_data["records"]

        label = f"**{rule}** — {count:,} records ({row['% of corpus']})"
        if count == 0:
            st.markdown(f"- {label} (clean)")
            continue

        with st.expander(label, expanded=False):
            show_cols = [
                c for c in [
                    "artifact_id", "entry_id", "topic_id", "category",
                    "update_type", "regulator_name",
                    "jurisdiction_country",
                    "impact_label", "impact_score",
                    "reconciled_published_date",
                    "feed_url",
                ]
                if c in offending.columns
            ]
            st.dataframe(
                offending[show_cols].head(200).reset_index(drop=True),
                width="stretch",
                height=min(400, 35 * min(len(offending), 200) + 40),
            )
            if len(offending) > 200:
                st.caption(f"Showing first 200 of {len(offending):,} offending records.")


# ============================================================
# 7.4  Field-health / cardinality
# ============================================================

with tabs[3]:
    st.subheader("Field-Health / Cardinality")
    st.markdown(
        "Taxonomy sprawl, near-duplicate regulator names, and jurisdiction validity. "
        "Computed over the **full frame**."
    )

    # ---- update_type cardinality ----
    st.markdown("### update_type cardinality")
    if "update_type" in _full_df.columns:
        ut_counts = _full_df["update_type"].value_counts()
        n_distinct_ut = len(ut_counts)
        from carver_showcase.config import RARE_UPDATE_TYPE_CUTOFF  # noqa: PLC0415
        rare_ut = ut_counts[ut_counts < RARE_UPDATE_TYPE_CUTOFF]
        n_rare = len(rare_ut)

        col1, col2, col3 = st.columns(3)
        col1.metric("Distinct update_type values", n_distinct_ut)
        col2.metric("Rare values (< threshold)", n_rare, help=f"Threshold: {RARE_UPDATE_TYPE_CUTOFF} records")
        col3.metric("Rare threshold", RARE_UPDATE_TYPE_CUTOFF)

        st.markdown("**Top 30 update_type values**")
        top30 = ut_counts.head(30).reset_index()
        top30.columns = ["update_type", "count"]
        fig_ut = px.bar(
            top30, x="count", y="update_type", orientation="h",
            labels={"count": "Records", "update_type": ""},
            title="Top 30 update_type values",
            height=500,
        )
        fig_ut.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_ut, width="stretch")

        if n_rare > 0:
            with st.expander(f"Rare update_type values ({n_rare}) — review/merge candidates"):
                rare_df = rare_ut.reset_index()
                rare_df.columns = ["update_type", "count"]
                st.dataframe(rare_df.sort_values("count"), width="stretch", hide_index=True)

    # ---- regulator near-duplicates ----
    st.markdown("---")
    st.markdown("### Regulator name near-duplicates")
    st.caption(
        "Regulator names that canonicalize to the same form (lowercase, strip punctuation, "
        "drop legal suffixes). These are merge/deduplicate candidates."
    )

    near_dup_data = _anomalies.get("regulator_near_duplicate", {})
    near_dup_records = near_dup_data.get("records", pd.DataFrame())
    n_near_dup_rows = near_dup_data.get("count", 0)

    if n_near_dup_rows == 0:
        st.success("No regulator near-duplicates detected.")
    else:
        from carver_showcase.quality import canonicalize_regulator  # noqa: PLC0415

        # Build canonical-group table
        nd_df = near_dup_records[["regulator_name"]].drop_duplicates() if not near_dup_records.empty else pd.DataFrame()
        if not nd_df.empty:
            nd_df = nd_df.copy()
            nd_df["canonical"] = nd_df["regulator_name"].apply(canonicalize_regulator)
            groups = (
                nd_df.groupby("canonical")["regulator_name"]
                .apply(list)
                .reset_index()
                .rename(columns={"regulator_name": "raw_names"})
            )
            groups["n_variants"] = groups["raw_names"].apply(len)
            groups = groups[groups["n_variants"] >= 2].sort_values("n_variants", ascending=False)

            st.metric("Canonical groups with ≥2 raw names", len(groups))
            st.metric("Records affected", f"{n_near_dup_rows:,}")

            with st.expander(f"Near-duplicate canonical groups ({len(groups):,} groups)", expanded=False):
                for _, grow in groups.head(100).iterrows():
                    st.markdown(
                        f"**{grow['canonical']}** ({grow['n_variants']} variants): "
                        + " · ".join(f"`{v}`" for v in grow["raw_names"][:10])
                    )
                if len(groups) > 100:
                    st.caption(f"Showing first 100 of {len(groups):,} groups.")

    # ---- jurisdiction_country validity ----
    st.markdown("---")
    st.markdown("### jurisdiction_country validity")

    invalid_jc_data = _anomalies.get("invalid_jurisdiction_country", {})
    n_invalid_jc = invalid_jc_data.get("count", 0)
    n_missing_jc = int(_full_df["jurisdiction_country"].isna().sum()) if "jurisdiction_country" in _full_df.columns else 0
    n_total_nonmissing = int(_full_df["jurisdiction_country"].notna().sum()) if "jurisdiction_country" in _full_df.columns else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Missing country", f"{n_missing_jc:,}", help=f"{n_missing_jc / max(n_total, 1):.1%} of corpus")
    col2.metric("Present but invalid ISO", f"{n_invalid_jc:,}")
    col3.metric("Valid ISO entries", f"{n_total_nonmissing - n_invalid_jc:,}")

    if n_invalid_jc > 0:
        invalid_jc_records = invalid_jc_data.get("records", pd.DataFrame())
        with st.expander(f"Invalid jurisdiction_country values ({n_invalid_jc:,} records)"):
            if not invalid_jc_records.empty:
                inv_val_counts = invalid_jc_records["jurisdiction_country"].value_counts().head(30)
                st.dataframe(
                    inv_val_counts.reset_index().rename(
                        columns={"jurisdiction_country": "value", "count": "n_records"}
                    ),
                    width="stretch",
                    hide_index=True,
                )


# ============================================================
# 7.5  Distribution / outlier views
# ============================================================

with tabs[4]:
    st.subheader("Distribution / Outlier Views (QA framing)")
    st.markdown(
        "Score and richness distributions re-framed for systematic defect detection. "
        "Computed over the sidebar-filtered frame."
    )

    dist_data = score_distributions(filtered_df)

    # Score distributions with QA annotations
    st.markdown("### Score distributions — watch for spikes at 0 and 10")
    score_axes = [("impact", "Impact"), ("urgency", "Urgency"), ("relevance", "Relevance")]
    fig_scores = go.Figure()
    axis_colors = AXIS_COLORS
    for axis, axis_label in score_axes:
        scores = dist_data[axis]["scores"]
        if scores:
            fig_scores.add_trace(go.Histogram(
                x=scores,
                name=axis_label,
                opacity=0.65,
                nbinsx=20,
                marker_color=axis_colors.get(axis, "grey"),
            ))
    fig_scores.update_layout(
        barmode="overlay",
        xaxis_title="Score (0–10)",
        yaxis_title="Record count",
        title="Impact / Urgency / Relevance score distributions",
        height=350,
    )
    fig_scores.add_vrect(
        x0=0, x1=0.5, fillcolor="red", opacity=0.08, line_width=0,
        annotation_text="0-spike?", annotation_position="top left",
    )
    fig_scores.add_vrect(
        x0=9.5, x1=10, fillcolor="red", opacity=0.08, line_width=0,
        annotation_text="10-spike?", annotation_position="top right",
    )
    st.plotly_chart(fig_scores, width="stretch")

    # Confidence distributions — look for degenerate clustering
    st.markdown("### Confidence distributions — degenerate clustering check")
    fig_conf = go.Figure()
    conf_colors = AXIS_COLORS
    for axis, axis_label in score_axes:
        confs = dist_data[axis]["confidence"]
        if confs:
            fig_conf.add_trace(go.Histogram(
                x=confs,
                name=axis_label,
                opacity=0.65,
                nbinsx=20,
                marker_color=conf_colors.get(axis, "grey"),
            ))
    fig_conf.update_layout(
        barmode="overlay",
        xaxis_title="Confidence (0–1)",
        yaxis_title="Record count",
        title="Impact / Urgency / Relevance confidence distributions",
        height=350,
    )
    st.plotly_chart(fig_conf, width="stretch")

    # Prose-length distribution (min_prose_len)
    st.markdown("---")
    st.markdown("### Prose-length distribution")
    st.caption("Records where a prose field is present but suspiciously short indicate thin content.")

    if "min_prose_len" in filtered_df.columns:
        from carver_showcase.config import MIN_PROSE_CHARS  # noqa: PLC0415

        prose_lens = pd.to_numeric(filtered_df["min_prose_len"], errors="coerce").dropna()
        if not prose_lens.empty:
            fig_prose = px.histogram(
                x=prose_lens,
                nbins=40,
                labels={"x": "Min prose part length (chars)"},
                title="Min prose length per record (has_impact_summary == True rows)",
            )
            fig_prose.add_vline(
                x=MIN_PROSE_CHARS,
                line_dash="dash",
                line_color="red",
                annotation_text=f"threshold ({MIN_PROSE_CHARS} chars)",
            )
            st.plotly_chart(fig_prose, width="stretch")

            n_short = int((prose_lens < MIN_PROSE_CHARS).sum())
            st.caption(f"{n_short:,} records with prose shorter than {MIN_PROSE_CHARS} chars (short_prose predicate).")
        else:
            st.info("No min_prose_len data in filtered frame.")

    # Richness-score distribution — find "empty-shell" records
    st.markdown("---")
    st.markdown("### Richness score vs impact score — empty-shell detection")
    st.caption(
        "Records with HIGH impact score but LOW richness score are 'empty-shell' records: "
        "scored confidently, but missing the supporting prose, actionables, and references."
    )

    if "richness_score" in filtered_df.columns and "impact_score" in filtered_df.columns:
        scatter_df = filtered_df[["richness_score", "impact_score", "category"]].dropna().copy()
        scatter_df = scatter_df.sample(min(5000, len(scatter_df)), random_state=42) if len(scatter_df) > 5000 else scatter_df

        fig_shell = px.scatter(
            scatter_df,
            x="richness_score",
            y="impact_score",
            color="category",
            opacity=0.4,
            labels={
                "richness_score": "Richness score (0–100)",
                "impact_score": "Impact score (0–10)",
                "category": "Category",
            },
            title="Richness vs Impact — upper-left quadrant = empty-shell candidates",
            height=400,
        )
        fig_shell.add_vrect(
            x0=0, x1=30, fillcolor="red", opacity=0.05, line_width=0,
            annotation_text="low richness", annotation_position="top left",
        )
        fig_shell.add_hrect(
            y0=7, y1=10, fillcolor="red", opacity=0.05, line_width=0,
            annotation_text="high impact", annotation_position="right",
        )
        st.plotly_chart(fig_shell, width="stretch")

        # Richness distribution histogram
        if "richness_score" in filtered_df.columns:
            rich_scores = pd.to_numeric(filtered_df["richness_score"], errors="coerce").dropna()
            fig_rich = px.histogram(
                x=rich_scores,
                nbins=25,
                labels={"x": "Richness score (0–100)"},
                title="Richness score distribution",
            )
            st.plotly_chart(fig_rich, width="stretch")


# ============================================================
# 7.6  Coverage-over-time trend
# ============================================================

with tabs[5]:
    st.subheader("Coverage-over-time Trend")
    st.markdown(
        "Population % of key fields by publication month — are recent records "
        "better annotated than older ones? Guides backfill prioritization. "
        "Computed over the sidebar-filtered frame (implausible dates excluded)."
    )

    freq_choice = st.radio(
        "Bucket by",
        options=["Month", "Quarter"],
        horizontal=True,
        key="trend_freq",
    )
    # Two separate freq maps:
    # - period_freq: used with dt.to_period() (legacy Period aliases)
    # - resample_freq: used with pd.resample() / volume_over_time
    _period_freq_map = {"Month": "M", "Quarter": "Q"}
    _resample_freq_map = {"Month": "ME", "Quarter": "QE"}
    freq = _period_freq_map[freq_choice]

    # Key fields to track over time
    TREND_FIELDS: list[tuple[str, str]] = [
        ("feed_url", "feed_url (source link)"),
        ("has_impact_summary", "has_impact_summary (prose)"),
        ("jurisdiction_country", "jurisdiction_country"),
        ("update_type", "update_type"),
        ("n_reg_refs_total", "n_reg_refs_total (refs count)"),
        ("effective_date", "effective_date"),
    ]

    # Build time-bucketed population % for each field
    date_col = "reconciled_published_date"
    if date_col not in filtered_df.columns or filtered_df[date_col].isna().all():
        st.warning("No plausible publication dates in the filtered frame.")
    else:
        from carver_showcase.metrics import plausible_date_mask, ensure_utc  # noqa: PLC0415

        dates_series = ensure_utc(filtered_df[date_col].copy())
        plausible = plausible_date_mask(dates_series)
        trend_base = filtered_df[plausible].copy()
        # Strip timezone before to_period — pandas Period doesn't carry tz info
        trend_base["_period"] = (
            pd.to_datetime(dates_series[plausible])
            .dt.tz_localize(None)
            .dt.to_period(freq)
            .dt.start_time
        )

        if trend_base.empty:
            st.warning("No plausible-date records in filtered frame.")
        else:
            trend_rows = []
            for col, label in TREND_FIELDS:
                if col not in trend_base.columns:
                    continue
                col_series = trend_base[col]
                is_bool = str(col_series.dtype) in ("boolean", "bool")

                for period, grp in trend_base.groupby("_period"):
                    n_grp = len(grp)
                    if n_grp == 0:
                        continue
                    col_data = grp[col]
                    if is_bool:
                        pct = float(col_data.eq(True).sum()) / n_grp
                    else:
                        pct = float(col_data.notna().mean())
                    trend_rows.append({"period": period, "field": label, "pct": pct, "n": n_grp})

            if trend_rows:
                trend_df = pd.DataFrame(trend_rows)
                fig_trend = px.line(
                    trend_df,
                    x="period",
                    y="pct",
                    color="field",
                    labels={"period": "Period", "pct": "Population %", "field": "Field"},
                    title=f"Field population % by {freq_choice.lower()}",
                    height=450,
                )
                fig_trend.update_yaxes(tickformat=".0%", range=[0, 1.05])
                st.plotly_chart(fig_trend, width="stretch")

                st.caption(
                    f"Only periods with plausible publication dates included. "
                    f"Total plausible records: {len(trend_base):,}."
                )

                # Show recent vs historical comparison
                if len(trend_df["period"].unique()) >= 4:
                    st.markdown("---")
                    st.markdown("#### Recent vs older records — annotation quality improvement?")
                    cutoff = pd.Timestamp.now() - pd.DateOffset(years=1)
                    recent = trend_base[trend_base["_period"] >= cutoff]
                    older = trend_base[trend_base["_period"] < cutoff]

                    comp_rows = []
                    for col, label in TREND_FIELDS:
                        if col not in trend_base.columns:
                            continue
                        is_bool = str(trend_base[col].dtype) in ("boolean", "bool")
                        for subset, subset_label in [(recent, "Last 12 months"), (older, "Older")]:
                            if len(subset) == 0:
                                continue
                            col_data = subset[col]
                            pct = float(col_data.eq(True).sum() / len(subset)) if is_bool else float(col_data.notna().mean())
                            comp_rows.append({"Field": label, "Period": subset_label, "Population %": f"{pct:.1%}"})

                    if comp_rows:
                        comp_df = pd.DataFrame(comp_rows)
                        st.dataframe(comp_df, width="stretch", hide_index=True)
            else:
                st.info("Not enough data to compute time trend for the current filter.")


# ============================================================
# 7.7  Deprecation / migration tracker
# ============================================================

with tabs[6]:
    st.subheader("Deprecation / Migration Tracker")
    st.markdown(
        "Residual `has_jurisdiction_tier_legacy` records — the deprecated field that should "
        "reach 0% after the ~2026-06-11 backfill. Medical Devices and Data protection carry "
        "disproportionate debt (see breakdown below). Computed over the **full frame**."
    )

    if "has_jurisdiction_tier_legacy" in _full_df.columns:
        legacy_mask = _full_df["has_jurisdiction_tier_legacy"].fillna(False).astype(bool)
        n_legacy = int(legacy_mask.sum())
        pct_legacy = n_legacy / max(n_total, 1)

        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Residual legacy records",
            f"{n_legacy:,}",
            help="Records still carrying has_jurisdiction_tier_legacy == True",
        )
        col2.metric(
            "% of corpus",
            f"{pct_legacy:.1%}",
            help="Expected: 0% after full backfill",
        )
        col3.metric(
            "Target",
            "0 records",
            help="Backfill deadline ~2026-06-11",
        )

        # Progress bar
        st.progress(1.0 - pct_legacy, text=f"Backfill progress: {(1 - pct_legacy):.1%} complete")

        # Breakdown by category
        st.markdown("---")
        st.markdown("#### Legacy field breakdown by category")
        st.caption(
            "MD and Data protection carry more backfill debt than Finance — "
            "a different migration timeline per category."
        )

        legacy_df = _full_df[legacy_mask].copy()
        non_legacy_df = _full_df[~legacy_mask].copy()

        if "category" in _full_df.columns:
            # Per-category: legacy count + legacy % within that category
            cat_legacy = legacy_df.groupby("category").size().reset_index(name="legacy_count")
            cat_total = _full_df.groupby("category").size().reset_index(name="total_count")
            cat_summary = cat_total.merge(cat_legacy, on="category", how="left")
            cat_summary["legacy_count"] = cat_summary["legacy_count"].fillna(0).astype(int)
            cat_summary["legacy_pct"] = (cat_summary["legacy_count"] / cat_summary["total_count"] * 100).round(1)
            cat_summary["clean_pct"] = 100.0 - cat_summary["legacy_pct"]
            cat_summary = cat_summary.sort_values("legacy_pct", ascending=False)

            fig_cat_legacy = px.bar(
                cat_summary,
                x="category",
                y="legacy_pct",
                text="legacy_count",
                color="legacy_pct",
                color_continuous_scale="Reds",
                labels={
                    "category": "Category",
                    "legacy_pct": "Legacy %",
                    "legacy_count": "Legacy records",
                },
                title="Residual legacy_tier field % by category",
            )
            fig_cat_legacy.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig_cat_legacy.update_layout(coloraxis_showscale=False, height=350)
            st.plotly_chart(fig_cat_legacy, width="stretch")

            st.dataframe(
                cat_summary[["category", "total_count", "legacy_count", "legacy_pct"]].rename(
                    columns={
                        "category": "Category",
                        "total_count": "Total records",
                        "legacy_count": "Legacy records",
                        "legacy_pct": "Legacy %",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

        # Volume over time for legacy vs clean
        st.markdown("---")
        st.markdown("#### Legacy vs clean records over time")
        st.caption(
            "If the backfill is progressing, recent records should be mostly clean. "
            "A flat legacy line means the backfill hasn't reached those records yet."
        )

        if "reconciled_published_date" in _full_df.columns:
            from carver_showcase.metrics import plausible_date_mask, ensure_utc  # noqa: PLC0415

            dates_all = ensure_utc(_full_df["reconciled_published_date"].copy())
            plausible_all = plausible_date_mask(dates_all)

            legacy_plaus = legacy_df[plausible_all[legacy_mask].values] if legacy_df is not None else pd.DataFrame()
            clean_plaus = non_legacy_df[plausible_all[~legacy_mask].values] if non_legacy_df is not None else pd.DataFrame()

            vot_data = []
            for subset_df, subset_label in [
                (legacy_plaus, "Legacy (has_jurisdiction_tier)"),
                (clean_plaus, "Clean"),
            ]:
                if not subset_df.empty:
                    vot = volume_over_time(subset_df, freq="ME")
                    if not vot.empty:
                        vot["subset"] = subset_label
                        vot_data.append(vot)

            if vot_data:
                vot_combined = pd.concat(vot_data, ignore_index=True)
                fig_vot = px.line(
                    vot_combined,
                    x="period",
                    y="count",
                    color="subset",
                    labels={
                        "period": "Month",
                        "count": "Record count",
                        "subset": "Group",
                    },
                    title="Legacy vs clean records over time (monthly)",
                    height=350,
                )
                st.plotly_chart(fig_vot, width="stretch")

        # Show a sample of legacy records for triage
        if n_legacy > 0:
            with st.expander(f"Sample legacy records ({min(n_legacy, 50):,} of {n_legacy:,})"):
                sample_cols = [
                    c for c in [
                        "artifact_id", "topic_id", "category", "regulator_name",
                        "jurisdiction_country", "update_type", "feed_url",
                    ]
                    if c in legacy_df.columns
                ]
                st.dataframe(
                    legacy_df[sample_cols].head(50).reset_index(drop=True),
                    width="stretch",
                )
    else:
        st.info("`has_jurisdiction_tier_legacy` column not present in the frame.")

    # Global KPI summary footer
    st.markdown("---")
    st.markdown("#### Full-corpus QA summary")
    n_any_fail = int(_flags_df.any(axis=1).sum())
    n_anomaly_total = sum(v["count"] for v in _anomalies.values())
    kpi_cards({
        "Total records": f"{n_total:,}",
        "Records in cleanup queue": f"{n_any_fail:,} ({n_any_fail / max(n_total, 1):.1%})",
        "Total anomaly hits": f"{n_anomaly_total:,}",
        "Residual legacy": f"{n_legacy:,} ({pct_legacy:.1%})" if "has_jurisdiction_tier_legacy" in _full_df.columns else "—",
        "Rules triggered": sum(1 for v in _anomalies.values() if v["count"] > 0),
    })
