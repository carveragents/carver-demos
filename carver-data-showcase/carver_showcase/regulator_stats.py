"""Pure aggregation logic for the Regulators stats view.

One public function
-------------------
build_regulator_stats(canonical_df, context_df, min_mentions) -> dict

    Aggregates raw regulator canonicalization data into the three outputs
    consumed by the gallery's Regulators tab and the deck:

    - "leaderboard" : DataFrame[name, mentions, country] — top-50 regulator
      bodies by total mention count.
    - "by_country"  : DataFrame[iso2, n_regulators, iso3, name] — distinct
      regulator bodies with >= min_mentions per parent country.
    - "meta"        : dict — six headline counts.

Design constraints
------------------
- Pure: no I/O, no Streamlit.  Input is two DataFrames (read by load.py).
- Defensive: missing/empty inputs return a dict of empty frames + zeroed meta,
  never raise.
- Reuses carver_showcase.load._regulator_merge_key (light dedup key: lowercase,
  strip punctuation, collapse whitespace — no suffix stripping).
- Reuses carver_showcase.charts.rollup_country to map raw country codes to
  ISO-2 parents.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from carver_showcase.config import ISO_COUNTRY, REGULATOR_MIN_MENTIONS
from carver_showcase.load import _regulator_merge_key

logger = logging.getLogger(__name__)


def _rollup_country(code) -> str | None:
    """ISO-2 parent for a raw country code; None if unmappable.

    Mirrors charts.rollup_country without importing charts (avoids heavy dep
    at import time in unit tests).
    """
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return None
    code = str(code)
    if code in ISO_COUNTRY:
        return code
    prefix = code.split("-")[0].strip()
    return prefix if prefix in ISO_COUNTRY else None


def _parse_countries(value) -> list[str]:
    """Parse a JSON-encoded list of ISO codes; return [] on any error."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return [str(c) for c in parsed if c]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []


def _empty_result() -> dict:
    """Return the canonical empty-result dict so all callers stay DRY."""
    return {
        "leaderboard": pd.DataFrame(columns=["name", "mentions", "country"]),
        "by_country": pd.DataFrame(columns=["iso2", "n_regulators", "iso3", "name"]),
        "meta": {
            "n_distinct_bodies": 0,
            "n_significant_bodies": 0,
            "n_raw_names": 0,
            "n_mentions": 0,
            "n_private_excluded": 0,
            "n_countries": 0,
        },
    }


def build_regulator_stats(
    canonical_df: pd.DataFrame,
    context_df: pd.DataFrame,
    mentions_by_name: dict | None = None,
    min_mentions: int = REGULATOR_MIN_MENTIONS,
) -> dict:
    """Aggregate regulator canonicalization data into leaderboard + choropleth inputs.

    Parameters
    ----------
    canonical_df:
        DataFrame with columns ``regulator_name``, ``canonical_regulator``,
        ``is_regulator`` (string "True"/"False"), ``mentions`` (int).
        Read by load.load_regulator_stats with keep_default_na=False so
        the literal string "NA" is preserved.
    context_df:
        DataFrame with columns ``regulator_name``, ``countries`` (JSON list
        of ISO-2 codes for that raw name).  Used to look up the dominant
        variant's first country.  May be empty (countries become None).
    mentions_by_name:
        Optional authoritative per-raw-name mention count (e.g. derived from
        the curated parquet).  When provided it OVERRIDES the ``mentions``
        column in ``canonical_df``:

        - Each raw name's effective mentions = ``mentions_by_name.get(name, 0)``.
        - Names with 0 effective mentions are excluded from ALL aggregations
          (they are absent from the curated frame).

        When ``None``, falls back to the existing ``canonical_df["mentions"]``
        behaviour unchanged (backward-compatible).
    min_mentions:
        Minimum summed mentions for a body to appear in ``by_country``.
        Does NOT filter the leaderboard (all bodies appear there up to top-50).

    Returns
    -------
    dict
        ``{"leaderboard": DataFrame, "by_country": DataFrame, "meta": dict}``
        Always returned — never raises.  Empty frames + zeroed meta on bad input.
    """
    # ------------------------------------------------------------------
    # Guard: require the four expected columns in canonical_df
    # ------------------------------------------------------------------
    required_cols = {"regulator_name", "canonical_regulator", "is_regulator", "mentions"}
    if canonical_df is None or canonical_df.empty:
        return _empty_result()
    if not required_cols.issubset(canonical_df.columns):
        logger.warning(
            "canonical_df is missing required columns (need %s, got %s); "
            "returning empty result",
            required_cols,
            set(canonical_df.columns),
        )
        return _empty_result()

    # ------------------------------------------------------------------
    # Parse is_regulator to bool
    # ------------------------------------------------------------------
    def _parse_is_reg(val) -> bool:
        return str(val).strip().lower() in ("true", "1")

    df = canonical_df.copy()
    df["_is_reg"] = df["is_regulator"].map(_parse_is_reg)
    df["mentions"] = pd.to_numeric(df["mentions"], errors="coerce").fillna(0).astype(int)

    # ------------------------------------------------------------------
    # Apply curated mention counts when the caller supplies mentions_by_name
    # ------------------------------------------------------------------
    if mentions_by_name is not None:
        df["mentions"] = df["regulator_name"].map(
            lambda n: int(mentions_by_name.get(n, 0))
        )
        # Exclude names absent from the curated frame (effective mentions == 0)
        df = df[df["mentions"] > 0].copy()

        if df.empty:
            return _empty_result()

    # ------------------------------------------------------------------
    # Compute merge key for every row (applied to canonical, fallback to raw)
    # ------------------------------------------------------------------
    def _make_key(row) -> str:
        key = _regulator_merge_key(str(row["canonical_regulator"]))
        if not key:
            key = _regulator_merge_key(str(row["regulator_name"]))
        if not key:
            key = str(row["regulator_name"])
        return key

    df["_key"] = df.apply(_make_key, axis=1)

    # ------------------------------------------------------------------
    # Meta: raw-name counts (all rows with effective mentions > 0, including private)
    # ------------------------------------------------------------------
    n_raw_names = len(df)
    n_private_excluded = int(df[~df["_is_reg"]]["regulator_name"].nunique())

    # ------------------------------------------------------------------
    # Build a country lookup from context_df: regulator_name → first ISO-2
    # ------------------------------------------------------------------
    country_map: dict[str, str | None] = {}
    if context_df is not None and not context_df.empty and "countries" in context_df.columns and "regulator_name" in context_df.columns:
        for _, ctx_row in context_df.iterrows():
            raw_name = str(ctx_row["regulator_name"])
            codes = _parse_countries(ctx_row["countries"])
            country_map[raw_name] = codes[0] if codes else None

    # ------------------------------------------------------------------
    # Restrict to is_regulator=True rows for the aggregation
    # ------------------------------------------------------------------
    reg_df = df[df["_is_reg"]].copy()

    if reg_df.empty:
        meta = _empty_result()["meta"]
        meta["n_raw_names"] = n_raw_names
        meta["n_private_excluded"] = n_private_excluded
        return {
            "leaderboard": pd.DataFrame(columns=["name", "mentions", "country"]),
            "by_country": pd.DataFrame(columns=["iso2", "n_regulators", "iso3", "name"]),
            "meta": meta,
        }

    # Attach the country for each raw variant (from context_df)
    reg_df["_country"] = reg_df["regulator_name"].map(country_map)

    # ------------------------------------------------------------------
    # Per-body aggregation grouped by _key
    # ------------------------------------------------------------------
    # For each key: sum mentions; find the dominant variant (most mentions);
    # name = canonical_regulator of dominant variant;
    # country = _country of dominant variant.

    records = []
    for key, group in reg_df.groupby("_key", sort=False):
        total_mentions = int(group["mentions"].sum())
        # Dominant variant: highest individual mentions; ties broken by regulator_name ascending
        # (deterministic regardless of CSV row order)
        dominant = group.sort_values(
            ["mentions", "regulator_name"], ascending=[False, True]
        ).iloc[0]
        name = str(dominant["canonical_regulator"])
        country = dominant["_country"]
        if country is not None and (not isinstance(country, float) or not pd.isna(country)):
            country = str(country)
        else:
            country = None
        records.append({"_key": key, "name": name, "mentions": total_mentions, "country": country})

    bodies_df = pd.DataFrame(records)

    # ------------------------------------------------------------------
    # Meta: n_distinct_bodies + n_significant_bodies
    # ------------------------------------------------------------------
    n_distinct_bodies = len(bodies_df)
    n_mentions = int(bodies_df["mentions"].sum())
    n_significant_bodies = int((bodies_df["mentions"] >= min_mentions).sum())

    # ------------------------------------------------------------------
    # Leaderboard: sort desc by mentions, then asc by name; top 50
    # ------------------------------------------------------------------
    leaderboard = (
        bodies_df[["name", "mentions", "country"]]
        .sort_values(["mentions", "name"], ascending=[False, True])
        .head(50)
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------
    # by_country: distinct bodies (key) with mentions >= min_mentions
    # per rolled-up ISO-2; enrich with iso3/name from ISO_COUNTRY
    # ------------------------------------------------------------------
    significant = bodies_df[bodies_df["mentions"] >= min_mentions].copy()
    significant["_iso2"] = significant["country"].map(_rollup_country)
    # Drop bodies with unmappable country
    mappable = significant.dropna(subset=["_iso2"])

    if mappable.empty:
        by_country = pd.DataFrame(columns=["iso2", "n_regulators", "iso3", "name"])
    else:
        by_country = (
            mappable.groupby("_iso2")["_key"]
            .nunique()
            .rename_axis("iso2")
            .reset_index(name="n_regulators")
        )
        by_country["iso3"] = by_country["iso2"].map(lambda x: ISO_COUNTRY.get(x, {}).get("iso3"))
        by_country["name"] = by_country["iso2"].map(lambda x: ISO_COUNTRY.get(x, {}).get("name", x))
        # Drop rows where iso3 couldn't be resolved (shouldn't happen after rollup_country, but be safe)
        by_country = by_country.dropna(subset=["iso3"]).sort_values("n_regulators", ascending=False).reset_index(drop=True)

    n_countries = len(by_country)

    meta = {
        "n_distinct_bodies": n_distinct_bodies,
        "n_significant_bodies": n_significant_bodies,
        "n_raw_names": n_raw_names,
        "n_mentions": n_mentions,
        "n_private_excluded": n_private_excluded,
        "n_countries": n_countries,
    }

    logger.info(
        "build_regulator_stats: %d distinct bodies, %d significant, %d countries",
        n_distinct_bodies,
        n_significant_bodies,
        n_countries,
    )
    return {"leaderboard": leaderboard, "by_country": by_country, "meta": meta}
