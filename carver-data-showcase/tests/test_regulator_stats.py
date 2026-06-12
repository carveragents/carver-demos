"""Tests for carver_showcase/regulator_stats.py — build_regulator_stats().

TDD: tests written BEFORE implementation.

Coverage
--------
- Aggregation: variants for the same canonical body sum mentions; the dominant
  variant (most mentions) determines the display name and country.
- by_country: distinct bodies per rolled-up ISO-2 country, with min_mentions
  cutoff applied; iso3/name populated from ISO_COUNTRY.
- meta: all six meta fields correct.
- NA-literal survival: a regulator literally named "NA" must not become NaN.
- Empty input: returns a dict with empty frames and zeroed meta — never raises.
- missing context_df: gracefully handles missing country data.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from carver_showcase.regulator_stats import build_regulator_stats
from carver_showcase.config import ISO_COUNTRY


# ---------------------------------------------------------------------------
# Helpers: build hand-crafted DataFrames
# ---------------------------------------------------------------------------

def _make_canonical_df(rows: list[dict]) -> pd.DataFrame:
    """Build a canonical DataFrame from a list of dicts (same structure as the CSV)."""
    df = pd.DataFrame(rows)
    # Ensure consistent dtypes (as if read from CSV with keep_default_na=False)
    for col in ("regulator_name", "canonical_regulator", "is_regulator"):
        if col in df.columns:
            df[col] = df[col].astype(str)
    if "mentions" in df.columns:
        df["mentions"] = df["mentions"].astype(int)
    return df


def _make_context_df(rows: list[dict]) -> pd.DataFrame:
    """Build a context DataFrame (regulator_name + countries JSON list)."""
    df = pd.DataFrame(rows)
    for col in ("regulator_name",):
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


# ---------------------------------------------------------------------------
# Fixture: a small, realistic hand-crafted dataset
#
# Bodies:
#   "Federal Reserve" — two raw variants (sum=150), dominant name = "Federal Reserve System"
#   "Financial Conduct Authority" — one raw variant (mentions=80), country=GB
#   "NA" — a regulator literally named "NA" (mentions=5, country=US)
#   "Private Corp Inc" — is_regulator=False (should be excluded from regulator aggregation)
#   "FCA UK" — is_regulator=True, canonical="Financial Conduct Authority" (same key as above → merged)
# ---------------------------------------------------------------------------

_CANONICAL_ROWS = [
    {
        "regulator_name": "US Federal Reserve",
        "canonical_regulator": "Federal Reserve System",
        "is_regulator": "True",
        "mentions": 100,
    },
    {
        "regulator_name": "Federal Reserve",
        "canonical_regulator": "Federal Reserve System",
        "is_regulator": "True",
        "mentions": 50,
    },
    {
        "regulator_name": "Financial Conduct Authority",
        "canonical_regulator": "Financial Conduct Authority",
        "is_regulator": "True",
        "mentions": 80,
    },
    {
        "regulator_name": "FCA UK",
        "canonical_regulator": "Financial Conduct Authority",
        "is_regulator": "True",
        "mentions": 20,
    },
    {
        "regulator_name": "NA",
        "canonical_regulator": "NA",
        "is_regulator": "True",
        "mentions": 5,
    },
    {
        "regulator_name": "Private Corp Inc",
        "canonical_regulator": "Private Corp Inc",
        "is_regulator": "False",
        "mentions": 300,
    },
    # A body with only 2 mentions — below default min_mentions=3, should be excluded from by_country
    {
        "regulator_name": "Tiny Body",
        "canonical_regulator": "Tiny Regulatory Body",
        "is_regulator": "True",
        "mentions": 2,
    },
]

_CONTEXT_ROWS = [
    {"regulator_name": "US Federal Reserve", "countries": json.dumps(["US", "CA"])},
    {"regulator_name": "Federal Reserve",     "countries": json.dumps(["US"])},
    {"regulator_name": "Financial Conduct Authority", "countries": json.dumps(["GB", "IE"])},
    {"regulator_name": "FCA UK",              "countries": json.dumps(["GB"])},
    {"regulator_name": "NA",                  "countries": json.dumps(["US"])},
    {"regulator_name": "Private Corp Inc",    "countries": json.dumps(["US"])},
    {"regulator_name": "Tiny Body",           "countries": json.dumps(["DE"])},
]


@pytest.fixture()
def canonical_df():
    return _make_canonical_df(_CANONICAL_ROWS)


@pytest.fixture()
def context_df():
    return _make_context_df(_CONTEXT_ROWS)


@pytest.fixture()
def stats(canonical_df, context_df):
    return build_regulator_stats(canonical_df, context_df, min_mentions=3)


# ---------------------------------------------------------------------------
# TestBuildRegulatorStatsReturn — dict shape
# ---------------------------------------------------------------------------


class TestBuildRegulatorStatsReturn:
    def test_returns_dict(self, stats):
        assert isinstance(stats, dict)

    def test_has_required_keys(self, stats):
        assert set(stats.keys()) == {"leaderboard", "by_country", "meta"}

    def test_leaderboard_is_dataframe(self, stats):
        assert isinstance(stats["leaderboard"], pd.DataFrame)

    def test_by_country_is_dataframe(self, stats):
        assert isinstance(stats["by_country"], pd.DataFrame)

    def test_meta_is_dict(self, stats):
        assert isinstance(stats["meta"], dict)


# ---------------------------------------------------------------------------
# TestLeaderboard — aggregation and ordering
# ---------------------------------------------------------------------------


class TestLeaderboard:
    def test_has_required_columns(self, stats):
        lb = stats["leaderboard"]
        for col in ("name", "mentions", "country"):
            assert col in lb.columns, f"Missing column: {col}"

    def test_variants_summed_under_one_body(self, stats):
        """Both 'US Federal Reserve' and 'Federal Reserve' map to 'Federal Reserve System' → sum=150."""
        lb = stats["leaderboard"]
        fed_row = lb[lb["name"] == "Federal Reserve System"]
        assert len(fed_row) == 1, f"Expected exactly 1 row for Federal Reserve System, got: {lb['name'].tolist()}"
        assert fed_row.iloc[0]["mentions"] == 150

    def test_fca_variants_merged(self, stats):
        """'Financial Conduct Authority' + 'FCA UK' both → 'Financial Conduct Authority' key → sum=100."""
        lb = stats["leaderboard"]
        fca_row = lb[lb["name"] == "Financial Conduct Authority"]
        assert len(fca_row) == 1
        assert fca_row.iloc[0]["mentions"] == 100

    def test_dominant_name_is_highest_mention_variant(self, stats):
        """For Federal Reserve System: 'US Federal Reserve' (100) > 'Federal Reserve' (50)
        so the canonical_regulator of the dominant raw variant defines the display name.
        Both point to 'Federal Reserve System' as canonical, so that is the name."""
        lb = stats["leaderboard"]
        # The display name 'Federal Reserve System' is the canonical of the dominant raw variant
        assert "Federal Reserve System" in lb["name"].values

    def test_sorted_desc_by_mentions(self, stats):
        lb = stats["leaderboard"]
        mentions = lb["mentions"].tolist()
        assert mentions == sorted(mentions, reverse=True)

    def test_ties_broken_by_name_asc(self, stats):
        """When two bodies tie on mentions, they must appear in ascending name order."""
        rows = [
            {"regulator_name": "Zebra Auth", "canonical_regulator": "Zebra Authority",
             "is_regulator": "True", "mentions": 10},
            {"regulator_name": "Alpha Auth", "canonical_regulator": "Alpha Authority",
             "is_regulator": "True", "mentions": 10},
        ]
        ctx_rows = [
            {"regulator_name": "Zebra Auth", "countries": json.dumps(["US"])},
            {"regulator_name": "Alpha Auth", "countries": json.dumps(["GB"])},
        ]
        df = _make_canonical_df(rows)
        ctx = _make_context_df(ctx_rows)
        result = build_regulator_stats(df, ctx, min_mentions=3)
        lb = result["leaderboard"]
        names = lb["name"].tolist()
        assert names.index("Alpha Authority") < names.index("Zebra Authority"), (
            f"Alpha Authority should precede Zebra Authority in tie, got: {names}"
        )

    def test_private_excluded(self, stats):
        """'Private Corp Inc' has is_regulator=False → must not appear in leaderboard."""
        lb = stats["leaderboard"]
        assert "Private Corp Inc" not in lb["name"].values

    def test_na_literal_survives(self, stats):
        """A regulator literally named 'NA' must survive as the string 'NA'."""
        lb = stats["leaderboard"]
        assert "NA" in lb["name"].values, f"Expected 'NA' in leaderboard, got: {lb['name'].tolist()}"

    def test_country_from_dominant_variant(self, stats):
        """Federal Reserve System's dominant variant is 'US Federal Reserve' (100 mentions);
        its country FIRST element from context_df is 'US'."""
        lb = stats["leaderboard"]
        fed_row = lb[lb["name"] == "Federal Reserve System"].iloc[0]
        assert fed_row["country"] == "US"

    def test_fca_country(self, stats):
        """FCA dominant is 'Financial Conduct Authority' (80 mentions) → country = 'GB'."""
        lb = stats["leaderboard"]
        fca_row = lb[lb["name"] == "Financial Conduct Authority"].iloc[0]
        assert fca_row["country"] == "GB"

    def test_at_most_50_rows_stored(self, stats):
        """Leaderboard stores at most top 50."""
        assert len(stats["leaderboard"]) <= 50

    def test_all_is_regulator_rows_present_when_few(self, stats):
        """With only 5 is_regulator=True bodies, all 5 should appear."""
        lb = stats["leaderboard"]
        # 5 distinct regulator bodies: FedReserve, FCA, NA, Tiny Body (2 mentions), no Private
        # Tiny Body has 2 mentions but leaderboard stores all up to 50 (min_mentions is for by_country only)
        assert len(lb) >= 4  # at minimum FedReserve, FCA, NA, Tiny Body

    def test_n_param_honoured_by_caller(self, stats):
        """Leaderboard contains top-50 rows; taking head(2) produces 2 rows."""
        lb = stats["leaderboard"]
        assert len(lb.head(2)) == 2


# ---------------------------------------------------------------------------
# TestByCountry — country aggregation
# ---------------------------------------------------------------------------


class TestByCountry:
    def test_has_required_columns(self, stats):
        bc = stats["by_country"]
        for col in ("iso2", "n_regulators", "iso3", "name"):
            assert col in bc.columns, f"Missing column: {col}"

    def test_us_count_includes_fed_reserve_and_na(self, stats):
        """Federal Reserve System (dominant country=US) + NA (country=US) → 2 bodies in US.
        Both have mentions >= 3 so both pass the min_mentions filter."""
        bc = stats["by_country"]
        us_row = bc[bc["iso2"] == "US"]
        assert not us_row.empty, f"Expected US row in by_country, got: {bc['iso2'].tolist()}"
        assert us_row.iloc[0]["n_regulators"] == 2

    def test_gb_count_is_1(self, stats):
        """FCA has dominant country=GB → 1 body in GB."""
        bc = stats["by_country"]
        gb_row = bc[bc["iso2"] == "GB"]
        assert not gb_row.empty
        assert gb_row.iloc[0]["n_regulators"] == 1

    def test_tiny_body_excluded_by_min_mentions(self, stats):
        """Tiny Body has 2 mentions < min_mentions=3 → excluded from by_country."""
        bc = stats["by_country"]
        de_row = bc[bc["iso2"] == "DE"]
        # Tiny Body is the only body in DE — it should be absent because mentions < 3
        assert de_row.empty, f"Tiny Body should be excluded, but DE row found: {de_row}"

    def test_private_excluded_from_by_country(self, stats):
        """Private Corp Inc (is_regulator=False) must not inflate US count."""
        # If Private Corp were included, US would be 3 (FedReserve + NA + Private)
        bc = stats["by_country"]
        us_row = bc[bc["iso2"] == "US"]
        assert us_row.iloc[0]["n_regulators"] == 2  # not 3

    def test_iso3_populated(self, stats):
        """iso3 must be populated from ISO_COUNTRY for all rows."""
        bc = stats["by_country"]
        assert bc["iso3"].notna().all(), f"iso3 has nulls: {bc[['iso2','iso3']]}"
        for _, row in bc.iterrows():
            assert row["iso3"] == ISO_COUNTRY[row["iso2"]]["iso3"]

    def test_name_populated(self, stats):
        """name must be populated from ISO_COUNTRY."""
        bc = stats["by_country"]
        assert bc["name"].notna().all()
        us_row = bc[bc["iso2"] == "US"]
        assert us_row.iloc[0]["name"] == ISO_COUNTRY["US"]["name"]

    def test_sorted_desc_by_n_regulators(self, stats):
        bc = stats["by_country"]
        vals = bc["n_regulators"].tolist()
        assert vals == sorted(vals, reverse=True)

    def test_distinct_bodies_per_country(self):
        """Two bodies in the same country should count as 2 distinct, not sum of variants."""
        rows = [
            {"regulator_name": "BodyA v1", "canonical_regulator": "Body A",
             "is_regulator": "True", "mentions": 10},
            {"regulator_name": "BodyA v2", "canonical_regulator": "Body A",
             "is_regulator": "True", "mentions": 5},
            {"regulator_name": "BodyB",    "canonical_regulator": "Body B",
             "is_regulator": "True", "mentions": 8},
        ]
        ctx_rows = [
            {"regulator_name": "BodyA v1", "countries": json.dumps(["US"])},
            {"regulator_name": "BodyA v2", "countries": json.dumps(["US"])},
            {"regulator_name": "BodyB",    "countries": json.dumps(["US"])},
        ]
        df = _make_canonical_df(rows)
        ctx = _make_context_df(ctx_rows)
        result = build_regulator_stats(df, ctx, min_mentions=3)
        bc = result["by_country"]
        us_row = bc[bc["iso2"] == "US"]
        # Body A (sum=15) + Body B (8) → 2 distinct bodies in US
        assert us_row.iloc[0]["n_regulators"] == 2


# ---------------------------------------------------------------------------
# TestMeta — all six fields
# ---------------------------------------------------------------------------


class TestMeta:
    def test_has_required_keys(self, stats):
        meta = stats["meta"]
        for key in (
            "n_distinct_bodies",
            "n_significant_bodies",
            "n_raw_names",
            "n_mentions",
            "n_private_excluded",
            "n_countries",
        ):
            assert key in meta, f"Missing meta key: {key}"

    def test_n_distinct_bodies(self, stats):
        """5 is_regulator=True distinct keys."""
        # Keys: "federal reserve system", "financial conduct authority", "na", "tiny regulatory body"
        # = 4 distinct bodies (5 raw is_regulator=True rows collapsing to 4 keys)
        assert stats["meta"]["n_distinct_bodies"] == 4

    def test_n_significant_bodies(self, stats):
        """Bodies with summed mentions >= 3: FedReserve (150), FCA (100), NA (5).
        Tiny Body has 2 < 3 → excluded."""
        assert stats["meta"]["n_significant_bodies"] == 3

    def test_n_raw_names(self, stats):
        """7 total raw rows in canonical_df (including private)."""
        assert stats["meta"]["n_raw_names"] == 7

    def test_n_mentions(self, stats):
        """Sum of mentions for is_regulator=True rows: 100+50+80+20+5+2 = 257."""
        assert stats["meta"]["n_mentions"] == 257

    def test_n_private_excluded(self, stats):
        """1 row has is_regulator=False: 'Private Corp Inc'."""
        assert stats["meta"]["n_private_excluded"] == 1

    def test_n_countries(self, stats):
        """by_country has US and GB (DE excluded by min_mentions cutoff)."""
        assert stats["meta"]["n_countries"] == len(stats["by_country"])
        assert stats["meta"]["n_countries"] == 2


# ---------------------------------------------------------------------------
# TestNaLiteralSurvival
# ---------------------------------------------------------------------------


class TestNaLiteralSurvival:
    def test_na_as_regulator_name_not_float(self):
        rows = [
            {"regulator_name": "NA", "canonical_regulator": "NA",
             "is_regulator": "True", "mentions": 5},
        ]
        ctx_rows = [{"regulator_name": "NA", "countries": json.dumps(["US"])}]
        df = _make_canonical_df(rows)
        ctx = _make_context_df(ctx_rows)
        result = build_regulator_stats(df, ctx, min_mentions=3)
        lb = result["leaderboard"]
        assert "NA" in lb["name"].values
        na_row = lb[lb["name"] == "NA"].iloc[0]
        assert isinstance(na_row["name"], str)
        assert na_row["mentions"] == 5

    def test_na_as_canonical_with_key_fallback(self):
        """When canonical_regulator is blank, key falls back to _regulator_merge_key(regulator_name)."""
        rows = [
            {"regulator_name": "Some Regulator", "canonical_regulator": "",
             "is_regulator": "True", "mentions": 10},
        ]
        ctx_rows = [{"regulator_name": "Some Regulator", "countries": json.dumps(["US"])}]
        df = _make_canonical_df(rows)
        ctx = _make_context_df(ctx_rows)
        result = build_regulator_stats(df, ctx, min_mentions=3)
        # Should not crash; leaderboard should have an entry
        lb = result["leaderboard"]
        assert len(lb) >= 1


# ---------------------------------------------------------------------------
# TestEmptyInput
# ---------------------------------------------------------------------------


class TestEmptyInput:
    def test_empty_canonical_returns_empty_frames(self):
        df = _make_canonical_df([])
        ctx = _make_context_df([])
        result = build_regulator_stats(df, ctx, min_mentions=3)
        assert isinstance(result, dict)
        assert result["leaderboard"].empty
        assert result["by_country"].empty

    def test_empty_canonical_meta_zeroed(self):
        df = _make_canonical_df([])
        ctx = _make_context_df([])
        result = build_regulator_stats(df, ctx)
        meta = result["meta"]
        for key in ("n_distinct_bodies", "n_significant_bodies", "n_raw_names",
                    "n_mentions", "n_private_excluded", "n_countries"):
            assert meta[key] == 0, f"Expected meta[{key}]=0, got {meta[key]}"

    def test_empty_context_still_returns_leaderboard(self):
        """Missing context → country is None for all; leaderboard still populated."""
        rows = [
            {"regulator_name": "Body X", "canonical_regulator": "Body X",
             "is_regulator": "True", "mentions": 10},
        ]
        df = _make_canonical_df(rows)
        ctx = _make_context_df([])  # no context rows
        result = build_regulator_stats(df, ctx, min_mentions=3)
        lb = result["leaderboard"]
        assert len(lb) == 1
        assert lb.iloc[0]["name"] == "Body X"
        # country unavailable → None or empty string
        assert lb.iloc[0]["country"] in (None, "", float("nan")) or pd.isna(lb.iloc[0]["country"])

    def test_missing_columns_returns_empty_gracefully(self):
        df = pd.DataFrame({"wrong_col": ["x"]})
        ctx = pd.DataFrame()
        result = build_regulator_stats(df, ctx)
        assert isinstance(result, dict)
        assert result["leaderboard"].empty
        assert result["by_country"].empty

    def test_no_exception_on_none_context(self):
        rows = [
            {"regulator_name": "Body Y", "canonical_regulator": "Body Y",
             "is_regulator": "True", "mentions": 5},
        ]
        df = _make_canonical_df(rows)
        # Pass None-ish: an empty DataFrame simulates a missing context file
        ctx = pd.DataFrame(columns=["regulator_name", "countries"])
        result = build_regulator_stats(df, ctx, min_mentions=3)
        # Should not raise; by_country will be empty (no mappable countries)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestDominantVariantTiebreak — deterministic selection on mention ties
# ---------------------------------------------------------------------------


class TestDominantVariantTiebreak:
    """When two raw variants of the SAME canonical body share an equal mention
    count, the dominant variant (which determines the display canonical_regulator
    name in the leaderboard) must be chosen deterministically — the row whose
    regulator_name sorts earliest alphabetically wins — regardless of input row order.

    Both raw variants must share the same _key (same canonical after merge-key
    normalisation) so they collapse to one body.  We give them the same
    canonical_regulator string but expose the tie via their regulator_name;
    the dominant row's canonical_regulator ends up as the leaderboard display name.
    """

    def _two_equal_variants(self, row_order: str) -> pd.DataFrame:
        """Build a canonical_df with two raw variants of the same body, each
        with 10 mentions.  Both map to the same canonical_regulator so they
        share one merge key.  raw names differ to exercise the tiebreak.

        'Alpha Raw Variant' < 'Zebra Raw Variant' alphabetically, so
        'Alpha Raw Variant' should be the dominant row.
        """
        rows_ab = [
            {
                "regulator_name": "Alpha Raw Variant",
                "canonical_regulator": "Same Canonical Body",
                "is_regulator": "True",
                "mentions": 10,
            },
            {
                "regulator_name": "Zebra Raw Variant",
                "canonical_regulator": "Same Canonical Body",
                "is_regulator": "True",
                "mentions": 10,
            },
        ]
        rows_ba = list(reversed(rows_ab))
        rows = rows_ab if row_order == "ab" else rows_ba
        return _make_canonical_df(rows)

    def test_tie_resolves_to_name_ascending_winner(self):
        """Both row orders produce the same dominant regulator_name (alphabetically first)."""
        ctx = _make_context_df([
            {"regulator_name": "Alpha Raw Variant", "countries": json.dumps(["US"])},
            {"regulator_name": "Zebra Raw Variant",  "countries": json.dumps(["GB"])},
        ])

        result_ab = build_regulator_stats(
            self._two_equal_variants("ab"), ctx, min_mentions=3
        )
        result_ba = build_regulator_stats(
            self._two_equal_variants("ba"), ctx, min_mentions=3
        )

        lb_ab = result_ab["leaderboard"]
        lb_ba = result_ba["leaderboard"]

        # Both row orders collapse to one body (same merge key after dedup).
        assert len(lb_ab) == 1, f"Expected 1 body, got: {lb_ab['name'].tolist()}"
        assert len(lb_ba) == 1, f"Expected 1 body, got: {lb_ba['name'].tolist()}"

        dominant_ab = lb_ab.iloc[0]["name"]
        dominant_ba = lb_ba.iloc[0]["name"]

        # Determinism: both orderings must produce the same dominant name.
        assert dominant_ab == dominant_ba, (
            f"Tie resolution is non-deterministic: ab→{dominant_ab!r}, ba→{dominant_ba!r}"
        )

        # Both variants share the same canonical name so this is always
        # "Same Canonical Body" — the test proves the call didn't crash or
        # produce different results across row orderings.
        assert dominant_ab == "Same Canonical Body", (
            f"Expected 'Same Canonical Body', got: {dominant_ab!r}"
        )

        # Tiebreak on country: 'Alpha Raw Variant' (alphabetically first) wins
        # → its country 'US' should be the dominant country.
        assert lb_ab.iloc[0]["country"] == "US", (
            f"Expected dominant country 'US' (from 'Alpha Raw Variant'), "
            f"got: {lb_ab.iloc[0]['country']!r}"
        )
        # The ba-ordered result must produce the same country.
        assert lb_ba.iloc[0]["country"] == "US", (
            f"Expected dominant country 'US' (ba-order), got: {lb_ba.iloc[0]['country']!r}"
        )


# ---------------------------------------------------------------------------
# TestMentionsByNameOverride — curated mention injection
# ---------------------------------------------------------------------------
#
# Fixture layout:
#   - "Big Regulator"  stored mentions=10, curated=2 → drops below min_mentions=3
#   - "Small Regulator" stored mentions=5, curated=8 → stays above threshold
#   - "Absent Name"    stored mentions=20, not in mentions_by_name → excluded
#   - "Private Corp"   is_regulator=False, stored=50, curated=30 → private, excluded from bodies
#
# When mentions_by_name is None (fallback), stored column values apply.
# ---------------------------------------------------------------------------

_OVERRIDE_CANONICAL_ROWS = [
    {
        "regulator_name": "Big Regulator",
        "canonical_regulator": "Big Regulatory Body",
        "is_regulator": "True",
        "mentions": 10,
    },
    {
        "regulator_name": "Small Regulator",
        "canonical_regulator": "Small Regulatory Body",
        "is_regulator": "True",
        "mentions": 5,
    },
    {
        "regulator_name": "Absent Name",
        "canonical_regulator": "Absent Body",
        "is_regulator": "True",
        "mentions": 20,
    },
    {
        "regulator_name": "Private Corp",
        "canonical_regulator": "Private Corp",
        "is_regulator": "False",
        "mentions": 50,
    },
]

_OVERRIDE_CONTEXT_ROWS = [
    {"regulator_name": "Big Regulator",   "countries": json.dumps(["US"])},
    {"regulator_name": "Small Regulator", "countries": json.dumps(["GB"])},
    {"regulator_name": "Absent Name",     "countries": json.dumps(["DE"])},
    {"regulator_name": "Private Corp",    "countries": json.dumps(["US"])},
]

# Curated counts: Big=2 (below threshold), Small=8 (above), Absent is absent.
_CURATED_MENTIONS = {
    "Big Regulator": 2,
    "Small Regulator": 8,
    "Private Corp": 30,
}


@pytest.fixture()
def override_canonical_df():
    df = pd.DataFrame(_OVERRIDE_CANONICAL_ROWS)
    for col in ("regulator_name", "canonical_regulator", "is_regulator"):
        df[col] = df[col].astype(str)
    df["mentions"] = df["mentions"].astype(int)
    return df


@pytest.fixture()
def override_context_df():
    df = pd.DataFrame(_OVERRIDE_CONTEXT_ROWS)
    df["regulator_name"] = df["regulator_name"].astype(str)
    return df


@pytest.fixture()
def override_stats(override_canonical_df, override_context_df):
    return build_regulator_stats(
        override_canonical_df,
        override_context_df,
        mentions_by_name=_CURATED_MENTIONS,
        min_mentions=3,
    )


class TestMentionsByNameOverride:
    """Injected mentions_by_name must be the AUTHORITATIVE source.

    All aggregations (leaderboard, by_country, meta) must reflect the CURATED
    counts, not the stored ``mentions`` column values.
    """

    def test_returns_dict(self, override_stats):
        assert isinstance(override_stats, dict)

    def test_has_required_keys(self, override_stats):
        assert set(override_stats.keys()) == {"leaderboard", "by_country", "meta"}

    def test_absent_name_excluded_from_leaderboard(self, override_stats):
        """'Absent Name' is not in mentions_by_name → excluded entirely."""
        lb = override_stats["leaderboard"]
        assert "Absent Body" not in lb["name"].values, (
            f"'Absent Body' should be excluded, but found in leaderboard: {lb['name'].tolist()}"
        )

    def test_small_regulator_uses_curated_mentions(self, override_stats):
        """'Small Regulator' has curated=8, not stored=5."""
        lb = override_stats["leaderboard"]
        row = lb[lb["name"] == "Small Regulatory Body"]
        assert len(row) == 1
        assert row.iloc[0]["mentions"] == 8, (
            f"Expected curated mentions=8, got {row.iloc[0]['mentions']}"
        )

    def test_big_regulator_below_threshold_absent_from_by_country(self, override_stats):
        """'Big Regulator' has curated=2 < min_mentions=3 → excluded from by_country."""
        bc = override_stats["by_country"]
        # Big Regulator is the only US body in the override fixture
        us_row = bc[bc["iso2"] == "US"]
        assert us_row.empty, (
            f"'Big Regulator' (curated=2) should be below threshold and absent from US "
            f"by_country, but found: {us_row}"
        )

    def test_big_regulator_still_in_leaderboard(self, override_stats):
        """min_mentions does NOT filter the leaderboard — Big Regulator still appears."""
        lb = override_stats["leaderboard"]
        row = lb[lb["name"] == "Big Regulatory Body"]
        assert len(row) == 1
        assert row.iloc[0]["mentions"] == 2

    def test_private_corp_excluded_from_leaderboard(self, override_stats):
        """is_regulator=False rows never appear in the leaderboard."""
        lb = override_stats["leaderboard"]
        assert "Private Corp" not in lb["name"].values

    def test_meta_n_raw_names_reflects_curated(self, override_stats):
        """n_raw_names = distinct rows with effective mentions > 0 (Big + Small + Private).
        'Absent Name' is excluded because it has 0 curated mentions."""
        meta = override_stats["meta"]
        # Big Regulator (2), Small Regulator (8), Private Corp (30) → 3 names with mentions > 0
        assert meta["n_raw_names"] == 3, (
            f"Expected n_raw_names=3, got {meta['n_raw_names']}"
        )

    def test_meta_n_private_excluded(self, override_stats):
        """n_private_excluded = distinct is_regulator=False names with effective mentions > 0."""
        meta = override_stats["meta"]
        # Only 'Private Corp' is is_regulator=False with curated mentions=30 > 0
        assert meta["n_private_excluded"] == 1

    def test_meta_n_distinct_bodies(self, override_stats):
        """n_distinct_bodies = distinct is_regulator=True keys with effective mentions > 0."""
        meta = override_stats["meta"]
        # Big Regulator (2), Small Regulator (8) → 2 distinct bodies; Absent Name excluded
        assert meta["n_distinct_bodies"] == 2

    def test_meta_n_significant_bodies(self, override_stats):
        """n_significant_bodies = bodies with curated mentions >= min_mentions=3.
        Big Regulator (2) is below threshold; Small Regulator (8) passes."""
        meta = override_stats["meta"]
        assert meta["n_significant_bodies"] == 1

    def test_meta_n_mentions_uses_curated(self, override_stats):
        """n_mentions = sum of curated mentions for is_regulator=True rows.
        Big=2 + Small=8 = 10; Absent Name excluded."""
        meta = override_stats["meta"]
        assert meta["n_mentions"] == 10

    def test_meta_n_countries(self, override_stats):
        """Only GB passes the threshold (Small=8 >= 3); US (Big=2 < 3) excluded."""
        meta = override_stats["meta"]
        assert meta["n_countries"] == 1
        bc = override_stats["by_country"]
        assert len(bc) == 1
        assert bc.iloc[0]["iso2"] == "GB"

    def test_leaderboard_sorted_desc_by_curated_mentions(self, override_stats):
        """Leaderboard ordering uses curated mentions (Small=8, Big=2 → Small first)."""
        lb = override_stats["leaderboard"]
        mentions = lb["mentions"].tolist()
        assert mentions == sorted(mentions, reverse=True)


class TestMentionsByNameNoneFallback:
    """When mentions_by_name=None, stored column values govern (backward compat)."""

    def test_none_falls_back_to_stored_column(self, override_canonical_df, override_context_df):
        """Without injection, the stored mentions column (10, 5, 20, 50) applies."""
        result = build_regulator_stats(
            override_canonical_df,
            override_context_df,
            mentions_by_name=None,
            min_mentions=3,
        )
        lb = result["leaderboard"]
        # 'Absent Body' should be present (stored=20)
        assert "Absent Body" in lb["name"].values, (
            f"Without injection, 'Absent Body' (stored=20) should be in leaderboard"
        )
        # Leaderboard mentions come from stored column, not curated dict
        absent_row = lb[lb["name"] == "Absent Body"].iloc[0]
        assert absent_row["mentions"] == 20

    def test_none_stored_n_distinct_bodies(self, override_canonical_df, override_context_df):
        """Without injection, all 3 is_regulator=True names form 3 distinct bodies."""
        result = build_regulator_stats(
            override_canonical_df,
            override_context_df,
            mentions_by_name=None,
            min_mentions=3,
        )
        meta = result["meta"]
        assert meta["n_distinct_bodies"] == 3

    def test_none_stored_n_mentions(self, override_canonical_df, override_context_df):
        """Without injection, n_mentions = 10 + 5 + 20 = 35 (is_regulator=True only)."""
        result = build_regulator_stats(
            override_canonical_df,
            override_context_df,
            mentions_by_name=None,
            min_mentions=3,
        )
        meta = result["meta"]
        assert meta["n_mentions"] == 35
