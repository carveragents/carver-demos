"""Shared Streamlit render helpers for the Carver Annotation Data Showcase.

Public functions
----------------
kpi_cards(metrics_dict)
    Render headline KPI metric cards (st.metric / columns).

snapshot_note(meta)
    One-line, always-visible "point-in-time as of <date>" note so a viewer
    never mistakes the snapshot for a live feed.  Rendered above the tabs.

scope_banner(df, catalog_df, meta)
    Data-driven scope/composition banner.  Counts are computed live from the
    loaded frame and catalog, so they can never drift from the data.

richness_definition()
    Reusable info box defining the deterministic richness score.

record_drilldown(raw_output_data, envelope=None)
    Render the FULL nested annotation per spec §6.3 from the RAW
    ``output_data`` dict.  HIDES empty sections (honest — no blank
    scaffolding).

Design notes
------------
- All functions use Streamlit directly — this module is app-layer only.
- Empty sections are hidden: a section is only rendered when it has at
  least one non-empty value to show.
- ``record_drilldown`` accepts the raw ``output_data`` dict (not a
  normalized row) so it can render the full nested payload fetched via
  ``load.get_raw_record``.
- Relevance is never shown: it is a deprecated weighted sum of impact and
  urgency, so the score section renders only those two axes.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import streamlit as st

from carver_showcase.config import DECK_PDF, DECK_TITLE, PLACEHOLDERS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_empty(value: Any) -> bool:
    """Return True when a value is effectively empty/missing.

    Shares the placeholder set with the ingest pipeline (config.PLACEHOLDERS)
    so the drill-down's "hide empty" rule matches the coverage numbers.
    """
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, str):
        return value.strip().lower() in PLACEHOLDERS
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _safe_float(value: Any) -> Optional[float]:
    """Coerce to float; return None for missing/non-numeric values (never raises)."""
    if _is_empty(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    """Convert a value to a display string, returning empty string if missing."""
    if _is_empty(value):
        return ""
    return str(value).strip()


def _section_header(title: str, icon: str = "") -> None:
    prefix = f"{icon} " if icon else ""
    st.markdown(f"### {prefix}{title}")


def _chip_row(items: list[str], label: str = "") -> None:
    """Render a list of strings as styled chip-like badges."""
    if not items:
        return
    if label:
        st.markdown(f"**{label}**")
    # Use inline HTML for chip styling
    chips_html = " ".join(
        f'<span style="background:#f0f2f6;border-radius:12px;padding:2px 10px;'
        f'margin:2px;font-size:0.85em;display:inline-block">{item}</span>'
        for item in items
        if not _is_empty(item)
    )
    if chips_html:
        st.markdown(chips_html, unsafe_allow_html=True)


def _score_gauge(label: str, score: Any, confidence: Any, basis: str = "") -> None:
    """Render a single score gauge (label + value + confidence)."""
    score_val = _safe_float(score)
    if score_val is None:
        return  # missing or non-numeric (garbage) score — skip the gauge

    conf_val = _safe_float(confidence)

    # Color coding by score band
    if score_val >= 7:
        color = "#d32f2f"  # red = high
    elif score_val >= 4:
        color = "#f57c00"  # orange = medium
    else:
        color = "#388e3c"  # green = low

    conf_text = f" · conf {conf_val:.0%}" if conf_val is not None else ""
    basis_text = f" · *{basis}*" if not _is_empty(basis) else ""

    st.markdown(
        f'<div style="background:#f8f9fa;border-left:4px solid {color};'
        f'padding:8px 12px;border-radius:4px;margin:4px 0">'
        f'<strong>{label}</strong>: '
        f'<span style="font-size:1.3em;font-weight:bold;color:{color}">{score_val:.1f}</span>/10'
        f'<span style="color:#666;font-size:0.9em">{conf_text}{basis_text}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Public: kpi_cards
# ---------------------------------------------------------------------------


def kpi_cards(metrics_dict: dict[str, Any]) -> None:
    """Render headline KPI metric cards in a row of st.metric columns.

    Parameters
    ----------
    metrics_dict:
        Mapping of label → value.  Values can be ints, floats, or strings.
        Pass up to 5 for a readable layout.

    Example
    -------
    >>> kpi_cards({
    ...     "Records": f"{len(df):,}",
    ...     "Institutions": bs["n_topics"],
    ...     "Countries": bs["n_countries"],
    ...     "Regulators": f"{bs['n_regulators']:,}",
    ...     "Median richness": median_richness,
    ... })
    """
    if not metrics_dict:
        return

    items = list(metrics_dict.items())
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label=label, value=str(value))


# ---------------------------------------------------------------------------
# Public: snapshot_note + scope_banner (data-driven; no hard-coded counts)
# ---------------------------------------------------------------------------


def deck_download(meta: Optional[dict] = None) -> None:
    """Render the prominent download link for the "State of Carver Data" deck.

    Serves the pre-rendered PDF (``config.DECK_PDF``) — a point-in-time,
    filter-free snapshot of every showcase view, one slide per tab, re-rendered
    on each data pull.  When the file is absent (a fresh checkout before any
    pull), a subtle caption is shown instead of an error.

    Parameters
    ----------
    meta:
        Snapshot provenance from ``load.load_snapshot_meta`` (used for the
        snapshot date in the downloaded file name).
    """
    meta = meta or {}
    if not DECK_PDF.exists():
        st.caption(
            f"📑 The downloadable **{DECK_TITLE}** deck will appear here after the "
            "next data pull."
        )
        return

    date = meta.get("snapshot_date") or "latest"
    st.download_button(
        label=f"📑  Download the “{DECK_TITLE}” deck (PDF)",
        data=DECK_PDF.read_bytes(),
        file_name=f"carver-state-of-data-{date}.pdf",
        mime="application/pdf",
        type="primary",
        help=(
            "A point-in-time, filter-free snapshot of every chart in this showcase "
            "— one slide per view. Re-rendered on every data refresh."
        ),
    )


def snapshot_note(meta: Optional[dict] = None) -> None:
    """Render the always-visible point-in-time snapshot note.

    Rendered ABOVE the tabs so it shows on every page.  States the pull date
    and that the data is a static snapshot, not a live feed — so a viewer never
    mistakes a figure here for the current platform value.

    Parameters
    ----------
    meta:
        The dict returned by ``load.load_snapshot_meta`` (carries
        ``snapshot_date``).  Falls back gracefully if missing.
    """
    meta = meta or {}
    date = meta.get("snapshot_date") or "an earlier date"
    st.caption(
        f"📸 **Point-in-time snapshot — computed on {date} (UTC).** "
        "This is a static extract of the Carver annotation corpus, **not a live feed**; "
        "figures here will differ from the live platform as new annotations land."
    )


def _composition_str(category_counts: dict) -> str:
    """Render ``{cat: n}`` as 'Cat A 12,345 · Cat B 6,789' (largest first)."""
    if not category_counts:
        return ""
    ordered = sorted(category_counts.items(), key=lambda kv: kv[1], reverse=True)
    return " · ".join(f"{cat} {int(n):,}" for cat, n in ordered)


def scope_banner(
    df,
    catalog_df=None,
    meta: Optional[dict] = None,
    show_categories: bool = True,
) -> None:
    """Render the honest scope/composition banner with LIVE counts.

    Every number is computed from the loaded frame and catalog at render time,
    so the banner can never drift from the actual snapshot.  The wording adapts
    to the snapshot scope recorded in ``meta`` (a full corpus pull vs a
    breadth-balanced sample).

    Parameters
    ----------
    df:
        The normalized annotations DataFrame (the full, unfiltered snapshot).
    catalog_df:
        The monitored-institutions catalog (``topic_catalog.csv``); used for
        the corpus-wide universe size.  Optional.
    meta:
        Snapshot provenance from ``load.load_snapshot_meta``.
    show_categories:
        When ``False``, the banner omits all category composition/wording
        (categories are an internal concept).  The external Gallery passes
        ``False``; the Cockpit leaves the default ``True``.
    """
    meta = meta or {}
    n_records = len(df)
    category_counts = (
        df["category"].dropna().value_counts().to_dict()
        if show_categories and "category" in df.columns else {}
    )
    composition = _composition_str(category_counts)
    n_topics_present = (
        int(df["topic_id"].dropna().nunique()) if "topic_id" in df.columns else 0
    )
    n_countries = (
        int(df["jurisdiction_country"].dropna().nunique())
        if "jurisdiction_country" in df.columns else 0
    )

    has_catalog = catalog_df is not None and not catalog_df.empty
    n_monitored = len(catalog_df) if has_catalog else None

    # Breadth headline — distinct institutions and jurisdictions actually in the data.
    breadth_clause = (
        f"It spans **{n_topics_present:,} distinct institutions** in "
        f"**{n_countries:,} jurisdictions** present in the data."
    )

    # Catalog reconciliation, phrased as a breakdown of the breadth count ("Of these,
    # X … and Y …") so the three numbers read as one whole rather than three competing
    # totals. The snapshot's distinct institutions are NOT all a subset of the catalog:
    # some topic_ids appear in the data but aren't (yet) catalogued, so a bare "X of Y"
    # would be wrong.
    catalog_clause = ""
    if n_monitored and "topic_id" in df.columns:
        _data_ids = set(df["topic_id"].dropna().unique())
        _catalog_ids = set(catalog_df["topic_id"].dropna().unique())
        n_cataloged_present = len(_data_ids & _catalog_ids)
        n_uncataloged = n_topics_present - n_cataloged_present
        if n_uncataloged > 0:
            catalog_clause = (
                f" Of these, **{n_cataloged_present:,}** are part of Carver's "
                f"**{n_monitored:,}-institution** monitored catalog and "
                f"**{n_uncataloged:,}** are not yet catalogued."
            )
        else:
            catalog_clause = (
                f" All are part of Carver's **{n_monitored:,}-institution** monitored catalog."
            )

    # Category phrasing only when this view talks about categories (Cockpit).
    # Drift-proof — derived from the data, not a fixed "three".
    if show_categories and category_counts:
        n_showcased = len([c for c in category_counts if c != "Uncategorized"])
        showcased_clause = f"{n_showcased} showcased categor{'y' if n_showcased == 1 else 'ies'}"
        uncat_clause = (
            " plus any uncategorized institutions" if "Uncategorized" in category_counts else ""
        )
        full_category_phrase = f" across {showcased_clause}{uncat_clause} ({composition})"
        sample_label = "category-stratified sample"
        sample_kind = "category-stratified"
        sample_category_phrase = f" ({composition})"
        sample_note = (
            "Per-category volumes are balanced for breadth, so they are **not** "
            "proportional to the live corpus. "
        )
    else:
        full_category_phrase = ""
        sample_label = "representative sample"
        sample_kind = "breadth-balanced"
        sample_category_phrase = ""
        sample_note = (
            "Volumes are selected for breadth, so they are **not** proportional to "
            "the live corpus. "
        )

    scope = meta.get("scope", "full")
    if scope == "full":
        st.info(
            f"**Scope — complete snapshot.** This showcase is built on the **full "
            f"set of {n_records:,} annotations**{full_category_phrase}. "
            f"{breadth_clause}{catalog_clause} "
            "All figures below are computed live over this snapshot — nothing is hard-coded.",
            icon="ℹ️",
        )
    else:
        st.info(
            f"**Scope — {sample_label}.** This showcase is built on a "
            f"**{n_records:,}-record** {sample_kind} snapshot{sample_category_phrase}. "
            f"{breadth_clause}{catalog_clause} "
            f"{sample_note}All figures below are computed live over this snapshot.",
            icon="ℹ️",
        )


def richness_definition(expanded: bool = False) -> None:
    """Reusable info box defining the deterministic richness score (spec §5.2).

    Shown wherever the richness score is surfaced so a viewer always knows what
    the number means and how it is derived.
    """
    with st.expander("How is the richness score computed?", expanded=expanded):
        st.markdown(
            "**Richness score (0–100)** is a deterministic, rule-based measure of how "
            "much structured content an annotation carries — **no LLM, no randomness**, "
            "fully reproducible. It is a weighted blend of six populated-content signals:\n\n"
            "| Component | Weight | What it measures |\n"
            "|---|---:|---|\n"
            "| Impact prose | 30% | How many of the 5 impact-summary parts are present |\n"
            "| Actionables | 20% | How many of the 7 actionable lanes are populated |\n"
            "| Critical dates | 15% | Count of key dates (capped at 5) |\n"
            "| Regulatory refs | 15% | Count of rules/statutes/precedents (capped at 6) |\n"
            "| Entities & tags | 10% | Named entities and topic tags (each capped at 8) |\n"
            "| Impacted business | 10% | Whether impacted business + functions are present |\n\n"
            "A high score means a deep, well-populated compliance object; a low score flags "
            "a thin 'shell' record. It measures **completeness, not correctness.**"
        )


# ---------------------------------------------------------------------------
# Public: record_drilldown
# ---------------------------------------------------------------------------


def record_drilldown(
    raw_output_data: dict,
    envelope: Optional[dict] = None,
) -> None:
    """Render the full nested annotation per spec §6.3.

    Every section is HIDDEN when it has no populated content (honest —
    no blank scaffolding).

    Parameters
    ----------
    raw_output_data:
        The ``output_data`` dict from the raw JSONL envelope.
    envelope:
        The full envelope dict (optional).  Used only to extract the
        ``input_data.extracted_metadata`` title/url fallback if
        ``output_data.classification.metadata`` is absent.

    Sections rendered (spec §6.3):
    1. Header: title / regulator / jurisdiction / update_type / date / source link
    2. Scores: two gauges (impact/urgency) with label+confidence; urgency also
       shows basis.  Relevance is omitted (deprecated weighted sum).
    3. Impact summary: 5 parts + key_requirements list
    4. Actionables: 7 lanes as labelled cards (only populated lanes shown)
    5. Critical dates: key dates (with calendars) + other_dates[] list
    6. Entities & tags: chip rows
    7. Regulatory references: 6 lanes
    8. Impacted business & functions: industry/type/jurisdiction/notes + functions
    9. Penalties & consequences
    10. Jurisdiction reasoning
    """
    if not raw_output_data:
        st.warning("No annotation data available for this record.")
        return

    scores = raw_output_data.get("scores", {}) or {}
    metadata = raw_output_data.get("metadata", {}) or {}
    classification = raw_output_data.get("classification", {}) or {}
    class_meta = classification.get("metadata", {}) or {}
    juris = classification.get("jurisdiction", {}) or {}
    reg_source = classification.get("regulatory_source", {}) or {}
    reconciled = raw_output_data.get("reconciled_published_date", {}) or {}

    # Pull title / url from classification.metadata first, then envelope fallback
    title = _safe_str(class_meta.get("title"))
    feed_url = _safe_str(class_meta.get("feed_url"))
    if not title and envelope:
        ext = (envelope.get("input_data") or {}).get("extracted_metadata") or {}
        title = _safe_str(ext.get("title"))
    if not feed_url and envelope:
        ext = (envelope.get("input_data") or {}).get("extracted_metadata") or {}
        feed_url = _safe_str(ext.get("url"))

    # -----------------------------------------------------------------------
    # 1. HEADER
    # -----------------------------------------------------------------------
    if title:
        st.title(title)
    else:
        st.title("Annotation Record")

    header_parts = []
    regulator = _safe_str(reg_source.get("name"))
    reg_division = _safe_str(reg_source.get("division_office"))
    if regulator:
        reg_display = f"{regulator}"
        if reg_division:
            reg_display += f" · {reg_division}"
        header_parts.append(f"**Regulator:** {reg_display}")

    country = _safe_str(juris.get("country"))
    bloc = _safe_str(juris.get("bloc"))
    scope = _safe_str(juris.get("scope"))
    juris_parts = [p for p in [country, bloc, scope] if p]
    if juris_parts:
        header_parts.append(f"**Jurisdiction:** {' / '.join(juris_parts)}")

    update_type = _safe_str(classification.get("update_type"))
    update_subtype = _safe_str(classification.get("update_subtype"))
    if update_type:
        ut_display = update_type
        if update_subtype:
            ut_display += f" — {update_subtype}"
        header_parts.append(f"**Type:** {ut_display}")

    pub_date = _safe_str(reconciled.get("date"))
    if pub_date:
        header_parts.append(f"**Published:** {pub_date}")

    if header_parts:
        st.markdown("  \n".join(header_parts))

    if feed_url:
        st.markdown(f"[View source document]({feed_url})")

    st.divider()

    # -----------------------------------------------------------------------
    # 2. SCORES
    # -----------------------------------------------------------------------
    impact = scores.get("impact") or {}
    urgency = scores.get("urgency") or {}

    # Relevance is intentionally omitted — it is a deprecated weighted sum of
    # impact and urgency, so only the two independent axes are shown.
    has_any_score = any(
        not _is_empty(s.get("score"))
        for s in [impact, urgency]
    )
    if has_any_score:
        _section_header("Scores", "📊")
        cols = st.columns(2)
        with cols[0]:
            _score_gauge(
                f"Impact ({_safe_str(impact.get('label'))})",
                impact.get("score"),
                impact.get("confidence"),
            )
        with cols[1]:
            _score_gauge(
                f"Urgency ({_safe_str(urgency.get('label'))})",
                urgency.get("score"),
                urgency.get("confidence"),
                basis=_safe_str(urgency.get("basis")),
            )
        st.divider()

    # -----------------------------------------------------------------------
    # 3. IMPACT SUMMARY
    # -----------------------------------------------------------------------
    impact_summary = metadata.get("impact_summary") or {}
    if isinstance(impact_summary, dict):
        prose_parts = {
            "Objective": impact_summary.get("objective"),
            "What changed": impact_summary.get("what_changed"),
            "Why it matters": impact_summary.get("why_it_matters"),
            "Risk & impact": impact_summary.get("risk_impact"),
        }
        key_reqs = impact_summary.get("key_requirements") or []

        non_empty_parts = {k: v for k, v in prose_parts.items() if not _is_empty(v)}
        has_reqs = isinstance(key_reqs, list) and len(key_reqs) > 0

        if non_empty_parts or has_reqs:
            _section_header("Impact Summary", "📋")
            for part_label, part_value in non_empty_parts.items():
                st.markdown(f"**{part_label}**")
                st.markdown(_safe_str(part_value))
            if has_reqs:
                st.markdown("**Key requirements**")
                for req in key_reqs:
                    if not _is_empty(req):
                        st.markdown(f"- {_safe_str(req)}")
            st.divider()

    # -----------------------------------------------------------------------
    # 4. ACTIONABLES
    # -----------------------------------------------------------------------
    actionables = metadata.get("actionables") or {}
    if isinstance(actionables, dict):
        lane_labels = {
            "policy_change": "Policy change",
            "status_change": "Status change",
            "process_change": "Process change",
            "training_change": "Training change",
            "reporting_change": "Reporting change",
            "tech_data_change": "Tech / data change",
            "other_change": "Other",
        }
        populated_lanes = [
            (lane_labels.get(k, k), v)
            for k, v in actionables.items()
            if not _is_empty(v)
        ]
        if populated_lanes:
            _section_header("Actionables", "✅")
            for lane_label, lane_value in populated_lanes:
                with st.container():
                    st.markdown(
                        f'<div style="background:#f0f7ff;border-left:3px solid #1976d2;'
                        f'padding:8px 12px;border-radius:4px;margin:4px 0">'
                        f"<strong>{lane_label}</strong><br>{_safe_str(lane_value)}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            st.divider()

    # -----------------------------------------------------------------------
    # 5. CRITICAL DATES
    # -----------------------------------------------------------------------
    critical_dates = metadata.get("critical_dates") or {}
    if isinstance(critical_dates, dict):
        date_fields = [
            ("Effective date", "effective_date", "effective_date_calendar"),
            ("Compliance date", "compliance_date", "compliance_date_calendar"),
            ("Comment deadline", "comment_deadline", "comment_deadline_calendar"),
            ("Early adoption date", "early_adoption_date", "early_adoption_date_calendar"),
            ("Updated date", "updated_date", "updated_date_calendar"),
            ("Publication date (content)", "pub_date_content", "pub_date_calendar"),
        ]
        other_dates = critical_dates.get("other_dates") or []

        key_date_rows = []
        for date_label, date_key, cal_key in date_fields:
            date_val = _safe_str(critical_dates.get(date_key))
            cal_val = _safe_str(critical_dates.get(cal_key))
            if date_val:
                cal_suffix = f" ({cal_val})" if cal_val else ""
                key_date_rows.append((date_label, f"{date_val}{cal_suffix}"))

        other_date_rows = []
        if isinstance(other_dates, list):
            for od in other_dates:
                if isinstance(od, dict):
                    od_date = _safe_str(od.get("date"))
                    od_cal = _safe_str(od.get("calendar"))
                    od_desc = _safe_str(od.get("description"))
                    if od_date:
                        cal_suffix = f" ({od_cal})" if od_cal else ""
                        desc_suffix = f" — {od_desc}" if od_desc else ""
                        other_date_rows.append(f"{od_date}{cal_suffix}{desc_suffix}")

        if key_date_rows or other_date_rows:
            _section_header("Key Dates", "📅")
            if key_date_rows:
                for date_label, date_display in key_date_rows:
                    st.markdown(f"**{date_label}:** {date_display}")
            if other_date_rows:
                st.markdown("**Other dates**")
                for row in other_date_rows:
                    st.markdown(f"- {row}")
            st.divider()

    # -----------------------------------------------------------------------
    # 6. ENTITIES & TAGS
    # -----------------------------------------------------------------------
    entities = metadata.get("entities") or []
    tags = metadata.get("tags") or []
    ent_list = [_safe_str(e) for e in entities if not _is_empty(e)] if isinstance(entities, list) else []
    tag_list = [_safe_str(t) for t in tags if not _is_empty(t)] if isinstance(tags, list) else []

    if ent_list or tag_list:
        _section_header("Entities & Tags", "🏷️")
        if ent_list:
            _chip_row(ent_list, label="Entities")
        if tag_list:
            _chip_row(tag_list, label="Tags")
        st.divider()

    # -----------------------------------------------------------------------
    # 7. REGULATORY REFERENCES
    # -----------------------------------------------------------------------
    reg_refs = metadata.get("reg_references") or {}
    if isinstance(reg_refs, dict):
        ref_lane_labels = {
            "rules": "Rules",
            "statutes": "Statutes",
            "other_ref": "Other references",
            "personnel": "Personnel",
            "precedents": "Precedents",
            "past_release": "Past releases",
        }
        populated_ref_lanes = []
        for key, label in ref_lane_labels.items():
            val = reg_refs.get(key)
            if isinstance(val, list):
                items = [_safe_str(i) for i in val if not _is_empty(i)]
                if items:
                    populated_ref_lanes.append((label, items))
            elif not _is_empty(val):
                populated_ref_lanes.append((label, [_safe_str(val)]))

        if populated_ref_lanes:
            _section_header("Regulatory References", "⚖️")
            for ref_label, ref_items in populated_ref_lanes:
                st.markdown(f"**{ref_label}**")
                for item in ref_items:
                    st.markdown(f"- {item}")
            st.divider()

    # -----------------------------------------------------------------------
    # 8. IMPACTED BUSINESS & FUNCTIONS
    # -----------------------------------------------------------------------
    impacted_business = metadata.get("impacted_business") or {}
    impacted_functions = metadata.get("impacted_functions") or []

    biz_parts = {}
    if isinstance(impacted_business, dict):
        biz_labels = {
            "industry": "Industry",
            "type": "Type",
            "jurisdiction": "Jurisdiction",
            "other_notes": "Other notes",
        }
        for key, label in biz_labels.items():
            val = impacted_business.get(key)
            if isinstance(val, list):
                items = [_safe_str(i) for i in val if not _is_empty(i)]
                if items:
                    biz_parts[label] = items
            elif not _is_empty(val):
                biz_parts[label] = [_safe_str(val)]

    func_list = []
    if isinstance(impacted_functions, list):
        func_list = [_safe_str(f) for f in impacted_functions if not _is_empty(f)]

    if biz_parts or func_list:
        _section_header("Impacted Business & Functions", "🏢")
        for biz_label, biz_items in biz_parts.items():
            st.markdown(f"**{biz_label}:** {', '.join(biz_items)}")
        if func_list:
            st.markdown(f"**Functions:** {', '.join(func_list)}")
        st.divider()

    # -----------------------------------------------------------------------
    # 9. PENALTIES & CONSEQUENCES
    # -----------------------------------------------------------------------
    penalties = metadata.get("penalties_consequences")
    if not _is_empty(penalties):
        _section_header("Penalties & Consequences", "⚠️")
        if isinstance(penalties, list):
            for p in penalties:
                if not _is_empty(p):
                    st.markdown(f"- {_safe_str(p)}")
        else:
            st.markdown(_safe_str(penalties))
        st.divider()

    # -----------------------------------------------------------------------
    # 10. JURISDICTION REASONING
    # -----------------------------------------------------------------------
    reasoning = _safe_str(juris.get("reasoning"))
    if reasoning:
        _section_header("Jurisdiction Reasoning", "🌐")
        st.markdown(reasoning)
