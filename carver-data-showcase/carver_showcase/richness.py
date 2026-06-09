"""Gallery curation: deterministic richness score and highlight-reel selection.

Public functions
----------------
richness_scores(df) -> pd.Series
    Compute the weighted richness score (0–100) for each row per spec §5.2.

highlight_reel(df, n, diversify=True) -> pd.DataFrame
    Top-n rows by richness_score desc, tiebroken by impact_score desc then
    artifact_id; with diversify=True applies a one-pass topic/update_type
    diversity filter.

Design notes
------------
- Deterministic: no LLM, no randomness.
- All weights live in config.RICHNESS_WEIGHTS (sum=1).
- Each component is normalized to [0,1] before weighting.
- Bounds: output is always in [0, 100] (round-then-clamp).
- Monotonic: adding any component population never decreases the score.
"""

from __future__ import annotations

import pandas as pd

from carver_showcase.config import RICHNESS_WEIGHTS


# ---------------------------------------------------------------------------
# Internal: per-component normalizers
# ---------------------------------------------------------------------------


def _prose_depth(df: pd.DataFrame) -> pd.Series:
    """Prose depth: (#present of 5 impact_summary parts) / 5.

    The 5 parts are: objective, what_changed, why_it_matters, risk_impact, key_requirements.
    For the 4 text parts we use their has_* boolean flags; for key_requirements we use
    (n_key_requirements > 0).
    """
    flags = (
        df["has_objective"].fillna(False).astype(bool).astype(int)
        + df["has_what_changed"].fillna(False).astype(bool).astype(int)
        + df["has_why_it_matters"].fillna(False).astype(bool).astype(int)
        + df["has_risk_impact"].fillna(False).astype(bool).astype(int)
        + (df["n_key_requirements"].fillna(0) > 0).astype(int)
    )
    return flags / 5.0


def _actionables_norm(df: pd.DataFrame) -> pd.Series:
    """Actionables: n_actionable_lanes / 7."""
    return df["n_actionable_lanes"].fillna(0) / 7.0


def _critical_dates_norm(df: pd.DataFrame) -> pd.Series:
    """Critical dates: min(n_critical_dates, 5) / 5."""
    return df["n_critical_dates"].fillna(0).clip(upper=5) / 5.0


def _reg_refs_norm(df: pd.DataFrame) -> pd.Series:
    """Regulatory references: min(n_reg_refs_total, 6) / 6."""
    return df["n_reg_refs_total"].fillna(0).clip(upper=6) / 6.0


def _entities_tags_norm(df: pd.DataFrame) -> pd.Series:
    """Entities & tags: (min(n_entities,8)/8 + min(n_tags,8)/8) / 2."""
    ent = df["n_entities"].fillna(0).clip(upper=8) / 8.0
    tag = df["n_tags"].fillna(0).clip(upper=8) / 8.0
    return (ent + tag) / 2.0


def _impacted_norm(df: pd.DataFrame) -> pd.Series:
    """Impacted business/functions: (has_impacted_business + (n_impacted_functions>0)) / 2."""
    biz = df["has_impacted_business"].fillna(False).astype(bool).astype(int)
    func = (df["n_impacted_functions"].fillna(0) > 0).astype(int)
    return (biz + func) / 2.0


# ---------------------------------------------------------------------------
# Public: richness_scores
# ---------------------------------------------------------------------------


def richness_scores(df: pd.DataFrame) -> pd.Series:
    """Compute the weighted richness score (0–100) for every row.

    Formula (spec §5.2):
        richness_score = round(100 × Σ weightᵢ × valueᵢ)

    where each valueᵢ is normalized to [0,1] before weighting.

    Parameters
    ----------
    df:
        Normalized annotations DataFrame (must have the richness count/flag columns).

    Returns
    -------
    pd.Series
        Float64 series of scores in [0, 100], same index as df.
    """
    w = RICHNESS_WEIGHTS
    raw = (
        w["prose"]          * _prose_depth(df)
        + w["actionables"]  * _actionables_norm(df)
        + w["critical_dates"] * _critical_dates_norm(df)
        + w["reg_refs"]     * _reg_refs_norm(df)
        + w["entities_tags"] * _entities_tags_norm(df)
        + w["impacted"]     * _impacted_norm(df)
    )
    # Scale to 0–100, round, then clamp to [0, 100] (defensive)
    scores = (raw * 100).round().clip(0, 100)
    return scores.astype("Float64")


# ---------------------------------------------------------------------------
# Public: highlight_reel
# ---------------------------------------------------------------------------


def highlight_reel(
    df: pd.DataFrame,
    n: int,
    diversify: bool = True,
) -> pd.DataFrame:
    """Return the top-n rows by richness_score for the Gallery highlight reel.

    Sort order (fully deterministic):
        1. richness_score descending
        2. impact_score descending (tiebreak)
        3. artifact_id ascending (final tiebreak — lexicographic, stable)

    With diversify=True a one-pass filter is applied:
        Pass 1: keep at most one record per topic_id until n is reached.
        Pass 2: if still below n, add one per update_type (not yet included).
        Pass 3: fill any remaining slots from the sorted remainder.

    No randomness — the diversify pass is deterministic (picks the top-ranked
    record per topic_id / update_type in rank order).

    Parameters
    ----------
    df:
        Normalized DataFrame; must have ``richness_score``, ``impact_score``,
        ``artifact_id``, ``topic_id``, and ``update_type`` columns.
    n:
        Number of records to return.
    diversify:
        If True, apply the one-per-topic then one-per-update_type diversity pass.

    Returns
    -------
    pd.DataFrame
        Up to n rows, sorted as described above.
    """
    if df.empty:
        return df.iloc[:0].copy()

    # Sort deterministically: richness desc, impact desc, artifact_id asc
    sorted_df = df.sort_values(
        by=["richness_score", "impact_score", "artifact_id"],
        ascending=[False, False, True],
    )

    if not diversify:
        return sorted_df.head(n).reset_index(drop=True)

    # Diversify pass
    selected_indices: list = []
    seen_topics: set = set()
    seen_update_types: set = set()

    # Pass 1: one per topic_id
    for idx, row in sorted_df.iterrows():
        if len(selected_indices) >= n:
            break
        t = row.get("topic_id")
        if t not in seen_topics:
            selected_indices.append(idx)
            seen_topics.add(t)

    if len(selected_indices) < n:
        # Pass 2: one per update_type (from records not yet selected)
        # Track update_types already represented in selected rows
        already_selected = set(selected_indices)
        for idx, row in sorted_df.iterrows():
            if len(selected_indices) >= n:
                break
            if idx in already_selected:
                continue
            ut = row.get("update_type")
            if ut not in seen_update_types:
                selected_indices.append(idx)
                seen_update_types.add(ut)
                already_selected.add(idx)

    if len(selected_indices) < n:
        # Pass 3: fill remaining from sorted order (exclude already selected)
        already_selected = set(selected_indices)
        for idx in sorted_df.index:
            if len(selected_indices) >= n:
                break
            if idx not in already_selected:
                selected_indices.append(idx)

    result = df.loc[selected_indices]
    # Re-sort the final selection to maintain the deterministic order
    result = result.sort_values(
        by=["richness_score", "impact_score", "artifact_id"],
        ascending=[False, False, True],
    )
    return result.reset_index(drop=True)
