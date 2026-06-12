"""Shared sidebar filter state and pure apply_filters for the Carver Showcase apps.

Two public surfaces
-------------------
FilterState (dataclass)
    Captures all user-selected filter criteria.  An "unset" filter field uses
    the sentinel that means "no restriction":
      - multiselects: empty list []
      - score ranges: the full possible range tuple (0.0, 10.0) or (0.0, 1.0)
      - date range: (None, None)
      - min_richness: 0

apply_filters(df, state) -> DataFrame
    PURE, vectorized, conjunctive filter.  No Streamlit import here — kept
    framework-agnostic so it can be unit-tested cleanly.
    An unset/empty filter field is a strict no-op (all rows pass that filter).

sidebar_filters(df, include_category=True, catalog_df=None) -> FilterState
    Renders the st.sidebar widgets from the frame's distinct values and
    returns a FilterState.  Uses Streamlit; NOT unit-tested directly.
    The Institution multiselect is rendered only when ``catalog_df`` is provided.

Design notes
------------
- apply_filters is the only unit-tested surface.  Keep it pure.
- All multiselect filters use isin() — empty list → no restriction.
- Score/date ranges: a range equal to the full extent is treated as no-op.
- Conjunctive: every active filter narrows the mask with &.
- Missing values (NA/NaT) are excluded when a filter is active on that
  column (consistent with honest-coverage stance — NA rows don't silently
  pass filters they haven't met).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# FilterState
# ---------------------------------------------------------------------------


@dataclass
class FilterState:
    """All user-selected filter criteria for the showcase sidebar.

    Sentinel values (unset):
      - multiselects: [] (empty list → no restriction)
      - score ranges: (0.0, 10.0) for scores, (0.0, 1.0) for confidences
      - date range: (None, None)
      - min_richness: 0
    """

    # Multiselect filters
    category: list[str] = field(default_factory=list)
    jurisdiction_country: list[str] = field(default_factory=list)
    jurisdiction_bloc: list[str] = field(default_factory=list)
    jurisdiction_scope: list[str] = field(default_factory=list)
    topic_id: list[str] = field(default_factory=list)
    regulator_name: list[str] = field(default_factory=list)
    update_type: list[str] = field(default_factory=list)

    # Score range sliders: (min, max) — default = full range
    impact_score_range: tuple[float, float] = (0.0, 10.0)
    urgency_score_range: tuple[float, float] = (0.0, 10.0)
    relevance_score_range: tuple[float, float] = (0.0, 10.0)

    # Date range: (start, end) — None means no bound
    date_range: tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]] = (None, None)

    # Minimum richness score (int 0–100); 0 = no restriction
    min_richness: int = 0


# ---------------------------------------------------------------------------
# Pure apply_filters — NO streamlit import
# ---------------------------------------------------------------------------

_SCORE_FULL_RANGE = (0.0, 10.0)


def apply_filters(df: pd.DataFrame, state: FilterState) -> pd.DataFrame:
    """Return the subset of df matching all active filters in state.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.
    state:
        A FilterState; unset fields are no-ops.

    Returns
    -------
    pd.DataFrame
        A view (or copy) of df containing only the rows that pass ALL active
        filters.  Row order is preserved.

    Notes
    -----
    - Empty multiselect list → no restriction (all rows pass).
    - Score range equal to (0.0, 10.0) → no restriction (all rows pass).
    - date_range (None, None) → no restriction.
    - min_richness == 0 → no restriction.
    - NA values in a filtered column are excluded when that filter is active.
    """
    mask = pd.Series(True, index=df.index)

    # --- Multiselect filters ---
    multiselect_cols = [
        ("category", state.category),
        ("jurisdiction_country", state.jurisdiction_country),
        ("jurisdiction_bloc", state.jurisdiction_bloc),
        ("jurisdiction_scope", state.jurisdiction_scope),
        ("topic_id", state.topic_id),
        ("regulator_name", state.regulator_name),
        ("update_type", state.update_type),
    ]
    for col, selected in multiselect_cols:
        if selected and col in df.columns:
            mask &= df[col].isin(selected)

    # --- Score range filters ---
    score_filters = [
        ("impact_score", state.impact_score_range),
        ("urgency_score", state.urgency_score_range),
        ("relevance_score", state.relevance_score_range),
    ]
    for col, (lo, hi) in score_filters:
        # Only apply if the range is non-trivial (not the full 0–10 extent)
        if (lo, hi) != _SCORE_FULL_RANGE and col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            mask &= series.notna() & (series >= lo) & (series <= hi)

    # --- Date range filter ---
    date_lo, date_hi = state.date_range
    if (date_lo is not None or date_hi is not None) and "reconciled_published_date" in df.columns:
        dates = df["reconciled_published_date"]
        date_mask = dates.notna()
        if date_lo is not None:
            date_mask &= dates >= date_lo
        if date_hi is not None:
            date_mask &= dates <= date_hi
        mask &= date_mask

    # --- Min richness ---
    if state.min_richness > 0 and "richness_score" in df.columns:
        richness = pd.to_numeric(df["richness_score"], errors="coerce")
        mask &= richness.notna() & (richness >= state.min_richness)

    return df[mask]


# ---------------------------------------------------------------------------
# sidebar_filters — uses Streamlit (not unit-tested directly)
# ---------------------------------------------------------------------------


def sidebar_filters(
    df: pd.DataFrame,
    include_category: bool = True,
    include_regulator: bool = True,
    catalog_df: pd.DataFrame | None = None,
) -> FilterState:
    """Render sidebar filter widgets and return a FilterState.

    Builds widgets from the distinct non-null values in each filter column.
    Returns a FilterState with the user's current selections.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame.
    include_category:
        When ``False``, the Category multiselect is not rendered and
        ``FilterState.category`` stays at its no-op default.  The external
        Gallery passes ``False`` (categories are an internal concept); the
        Cockpit leaves the default ``True``.
    include_regulator:
        When ``False``, the Regulator multiselect is not rendered and
        ``FilterState.regulator_name`` stays at its no-op default ``[]``.  The
        external Gallery passes ``False`` (regulators are no longer surfaced in
        the showcase); the Cockpit leaves the default ``True``.
    catalog_df:
        Optional topic catalog DataFrame (columns: topic_id, name, acronym,
        jurisdiction_code).  When provided and non-empty, an "Institution"
        multiselect is rendered.  When ``None`` or empty (e.g., the Cockpit
        caller), the widget is skipped and ``FilterState.topic_id`` stays at
        its no-op default ``[]``.

    Returns
    -------
    FilterState
        Current user selections.
    """
    # Import streamlit here so the module can be imported without streamlit
    # being available (e.g., in unit tests).
    import streamlit as st

    st.sidebar.header("Filters")

    def _sorted_unique(col: str) -> list[str]:
        if col not in df.columns:
            return []
        vals = df[col].dropna().unique().tolist()
        return sorted(str(v) for v in vals)

    # --- Multiselects ---
    # Category is an internal concept — the external Gallery opts out via
    # include_category=False, leaving the field at its no-op default.
    if include_category:
        category = st.sidebar.multiselect(
            "Category",
            options=_sorted_unique("category"),
            default=[],
            key="filter_category",
        )
    else:
        category = []
    jurisdiction_country = st.sidebar.multiselect(
        "Country",
        options=_sorted_unique("jurisdiction_country"),
        default=[],
        key="filter_country",
    )
    jurisdiction_bloc = st.sidebar.multiselect(
        "Bloc",
        options=_sorted_unique("jurisdiction_bloc"),
        default=[],
        key="filter_bloc",
    )
    jurisdiction_scope = st.sidebar.multiselect(
        "Jurisdiction scope",
        options=_sorted_unique("jurisdiction_scope"),
        default=[],
        key="filter_scope",
    )
    # --- Institution (topic_id) multiselect ---
    # Only rendered when a catalog is provided and df has a topic_id column.
    # Cockpit caller passes catalog_df=None → block is skipped entirely.
    topic_id: list[str] = []
    if catalog_df is not None and not catalog_df.empty and "topic_id" in df.columns:
        raw_topic_ids = df["topic_id"].dropna().unique()
        if len(raw_topic_ids) > 0:
            # Treat None, NaN, and empty/whitespace strings as missing.
            def _present(val) -> bool:
                if val is None:
                    return False
                try:
                    if pd.isna(val):
                        return False
                except (TypeError, ValueError):
                    pass
                return str(val).strip() != ""

            # Build inst_label_map in a single catalog pass; first-occurrence-wins
            # for any duplicate topic_id (avoids .loc returning a DataFrame).
            inst_label_map: dict[str, str] = {}
            has_name = "name" in catalog_df.columns
            has_acronym = "acronym" in catalog_df.columns
            has_jcode = "jurisdiction_code" in catalog_df.columns
            for row in catalog_df.to_dict("records"):
                tid = str(row.get("topic_id", ""))
                if not tid or tid in inst_label_map:
                    continue
                name_str = str(row["name"]).strip() if has_name and _present(row.get("name")) else ""
                if not name_str:
                    inst_label_map[tid] = f"Unknown institution ({tid[:8]})"
                    continue
                label = name_str
                if has_acronym and _present(row.get("acronym")):
                    label = f"{label} ({str(row['acronym']).strip()})"
                if has_jcode and _present(row.get("jurisdiction_code")):
                    label = f"{label} — {str(row['jurisdiction_code']).strip()}"
                inst_label_map[tid] = label

            def _inst_display(tid: str) -> str:
                return inst_label_map.get(tid, f"Unknown institution ({tid[:8]})")

            sorted_topic_ids = sorted(
                (str(t) for t in raw_topic_ids),
                key=lambda tid: _inst_display(tid).lower(),
            )

            topic_id = list(
                st.sidebar.multiselect(
                    "Institution",
                    options=sorted_topic_ids,
                    default=[],
                    format_func=_inst_display,
                    key="filter_institution",
                )
            )

    # Regulator is no longer surfaced in the external Gallery (it opts out via
    # include_regulator=False); the Cockpit keeps it via the default.
    if include_regulator:
        regulator_name = st.sidebar.multiselect(
            "Regulator",
            options=_sorted_unique("regulator_name"),
            default=[],
            key="filter_regulator",
        )
    else:
        regulator_name = []
    update_type = st.sidebar.multiselect(
        "Update type",
        options=_sorted_unique("update_type"),
        default=[],
        key="filter_update_type",
    )

    st.sidebar.markdown("---")

    # --- Score sliders ---
    impact_score_range = st.sidebar.slider(
        "Impact score",
        min_value=0.0,
        max_value=10.0,
        value=(0.0, 10.0),
        step=0.1,
        key="filter_impact_score",
    )
    urgency_score_range = st.sidebar.slider(
        "Urgency score",
        min_value=0.0,
        max_value=10.0,
        value=(0.0, 10.0),
        step=0.1,
        key="filter_urgency_score",
    )
    # Relevance is a deprecated weighted sum of impact + urgency, so it is not
    # offered as a filter.  The FilterState field stays at its no-op default.
    relevance_score_range = (0.0, 10.0)

    # --- Min richness ---
    min_richness = st.sidebar.slider(
        "Min richness score",
        min_value=0,
        max_value=100,
        value=0,
        step=1,
        key="filter_min_richness",
    )

    st.sidebar.markdown("---")

    # --- Date range ---
    # Use date_input for the published date range
    date_range_raw = st.sidebar.date_input(
        "Published date range",
        value=[],
        key="filter_date_range",
    )
    # Normalize: date_input returns a list of 0, 1, or 2 dates
    date_lo: Optional[pd.Timestamp] = None
    date_hi: Optional[pd.Timestamp] = None
    if isinstance(date_range_raw, (list, tuple)) and len(date_range_raw) >= 1:
        date_lo = pd.Timestamp(date_range_raw[0], tz="UTC")
    if isinstance(date_range_raw, (list, tuple)) and len(date_range_raw) >= 2:
        date_hi = pd.Timestamp(date_range_raw[1], tz="UTC")

    return FilterState(
        category=list(category),
        jurisdiction_country=list(jurisdiction_country),
        jurisdiction_bloc=list(jurisdiction_bloc),
        jurisdiction_scope=list(jurisdiction_scope),
        topic_id=list(topic_id),
        regulator_name=list(regulator_name),
        update_type=list(update_type),
        impact_score_range=tuple(impact_score_range),
        urgency_score_range=tuple(urgency_score_range),
        relevance_score_range=tuple(relevance_score_range),
        date_range=(date_lo, date_hi),
        min_richness=int(min_richness),
    )
