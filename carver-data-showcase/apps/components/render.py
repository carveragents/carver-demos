"""Shared Streamlit render helpers for the Carver Annotation Data Showcase.

Public functions
----------------
kpi_cards(metrics_dict)
    Render headline KPI metric cards (st.metric / columns).

sampling_caveat_banner()
    Persistent honest scope banner per spec §2.2/§8.

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
"""

from __future__ import annotations

import math
from typing import Any, Optional

import streamlit as st

from carver_showcase.config import PLACEHOLDERS


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
    ...     "Records": "58,982",
    ...     "Topics": 405,
    ...     "Countries": 111,
    ...     "Regulators": "3,219",
    ...     "Median richness": "72",
    ... })
    """
    if not metrics_dict:
        return

    items = list(metrics_dict.items())
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label=label, value=str(value))


# ---------------------------------------------------------------------------
# Public: sampling_caveat_banner
# ---------------------------------------------------------------------------


def sampling_caveat_banner() -> None:
    """Render the persistent honest-scope sampling caveat banner.

    Per spec §2.2/§8: a non-negotiable banner on the overview stating the
    stratified composition (per-category record counts; MD/DP pulled in full,
    Finance sub-sampled), topic coverage (405/1,071 monitored), and that the
    sample is category-stratified, not random.

    Corpus-wide breadth claims are clearly marked as describing the FULL
    dataset; live metrics describe this 58,982-record slice.
    """
    st.info(
        "**Sampling scope** — This showcase is built on a **category-stratified snapshot "
        "of 58,982 records**: Finance 40,000 · Data protection & cybersecurity 10,132 · "
        "Medical Devices 8,850. Medical Devices and Data protection were pulled in full; "
        "Finance was sub-sampled to 40,000 to balance representation. "
        "This slice covers **405 of the 1,071 monitored institutions** in the Carver universe. "
        "Corpus-wide figures (1,071 institutions, 241 jurisdictions) describe the **full "
        "Carver dataset** — all live metrics computed here are over this stratified snapshot.",
        icon="ℹ️",
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
    2. Scores: three gauges (impact/urgency/relevance) with label+confidence;
       urgency also shows basis
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
    relevance = scores.get("relevance") or {}

    has_any_score = any(
        not _is_empty(s.get("score"))
        for s in [impact, urgency, relevance]
    )
    if has_any_score:
        _section_header("Scores", "📊")
        cols = st.columns(3)
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
        with cols[2]:
            _score_gauge(
                f"Relevance ({_safe_str(relevance.get('label'))})",
                relevance.get("score"),
                relevance.get("confidence"),
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
