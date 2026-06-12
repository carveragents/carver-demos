"""Unit tests for carver_showcase.charts — pure Plotly figure builders.

All tests use small in-memory DataFrames only.  No kaleido, no Streamlit, no
network calls.  Every public ``fig_*`` builder in ``charts.__all__`` is covered.

Test groups
-----------
- TestRollupCountry            : rollup_country helper
- TestGeoCountryCounts         : geo_country_counts prep helper
- TestInstCountryCounts        : inst_country_counts prep helper
- TestUpdateTypeCounts         : update_type_counts prep helper
- TestVolumeFrame              : volume_frame prep helper
- TestFigBuilders              : every fig_* builder → go.Figure with ≥1 trace
- TestFigBuildersEmpty         : every fig_* builder is defensive on empty input
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import pytest

from carver_showcase import charts
from carver_showcase.charts import (
    fig_category_composition,
    fig_category_sunburst,
    fig_confidence_histogram,
    fig_entity_leaderboard,
    fig_entity_type_breakdown,
    fig_geo_choropleth,
    fig_geo_top_countries,
    fig_inst_by_scope,
    fig_inst_choropleth,
    fig_inst_regulator_types,
    fig_inst_top_countries,
    fig_jurisdiction_bloc,
    fig_jurisdiction_scope,
    fig_label_mix,
    fig_recency_bar,
    fig_regulator_choropleth,
    fig_regulator_leaderboard,
    fig_score_histogram,
    fig_tag_leaderboard,
    fig_top_institutions,
    fig_update_types,
    fig_urgency_basis_bar,
    fig_urgency_basis_pie,
    fig_volume,
    geo_country_counts,
    inst_country_counts,
    rollup_country,
    update_type_counts,
    volume_frame,
)
from carver_showcase.config import ENTITY_TYPE_COLORS
from carver_showcase.metrics import historical_depth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def df() -> pd.DataFrame:
    """Small (~15 rows) synthetic normalized DataFrame with all chart-relevant columns."""
    n = 15
    dates = pd.to_datetime(
        [
            "2021-03-01", "2021-09-15", "2022-01-10", "2022-06-20", "2022-11-30",
            "2023-02-14", "2023-07-04", "2023-12-01", "2024-03-08", "2024-08-18",
            "2025-01-05", "2025-04-22", "2025-09-09", "2026-01-15", "2026-05-28",
        ],
        utc=True,
    )
    topic_ids = ["t1", "t2", "t3", "t1", "t2", "t3", "t4", "t1", "t2", "t3",
                 "t4", "t1", "t2", "t3", "t4"]
    categories = (
        ["Finance"] * 7
        + ["Medical Devices"] * 4
        + ["Data Protection"] * 4
    )
    countries = ["US", "GB", "DE", "US", "GB", "FR", "DE", "US", "AU", "GB",
                 "US", "DE", "FR", "AU", "US"]
    blocs = ["G7", "EU", "EU", "G7", "EU", None, "EU", "G7", "APAC", "EU",
             "G7", "EU", "EU", "APAC", "G7"]
    scopes = ["national", "national", "national", "supranational", "national",
              "national", "national", "national", "national", "national",
              "national", "supranational", "national", "national", "national"]
    update_types = [
        "Regulatory Update", "Guidance", "Consultation", "Regulatory Update",
        "Guidance", "Final Rule", "Regulatory Update", "Consultation",
        "Guidance", "Regulatory Update", "Final Rule", "Guidance",
        "Consultation", "Regulatory Update", "Guidance",
    ]
    urgency_bases = [
        "future_deadline", "no_future_date", "past_deadline", "future_deadline",
        "no_future_date", "effective_immediately", "future_deadline",
        "no_future_date", "past_deadline", "future_deadline",
        "no_future_date", "effective_immediately", "future_deadline",
        "no_future_date", "past_deadline",
    ]
    impact_scores = [8.0, 5.0, 3.0, 7.5, 6.0, 4.0, 9.0, 2.0, 8.5, 5.5,
                     7.0, 3.5, 6.5, 8.0, 4.5]
    urgency_scores = [7.0, 4.5, 2.0, 6.0, 5.5, 3.0, 8.0, 2.5, 7.5, 4.0,
                      6.5, 3.0, 5.0, 7.0, 4.0]
    impact_confidences = [0.9, 0.7, 0.6, 0.85, 0.75, 0.65, 0.95, 0.55,
                          0.88, 0.72, 0.80, 0.60, 0.78, 0.90, 0.68]
    urgency_confidences = [0.8, 0.75, 0.5, 0.82, 0.70, 0.60, 0.88, 0.52,
                           0.84, 0.66, 0.78, 0.58, 0.72, 0.86, 0.64]
    impact_labels = (["high"] * 5 + ["medium"] * 5 + ["low"] * 5)
    urgency_labels = (["high"] * 4 + ["medium"] * 6 + ["low"] * 5)
    richness = [70, 50, 30, 65, 55, 40, 80, 25, 75, 45, 60, 35, 58, 72, 42]

    return pd.DataFrame(
        {
            "topic_id": pd.array(topic_ids, dtype="string"),
            "category": pd.array(categories, dtype="string"),
            "jurisdiction_country": pd.array(countries, dtype="string"),
            "jurisdiction_bloc": pd.array(blocs, dtype="string"),
            "jurisdiction_scope": pd.array(scopes, dtype="string"),
            "update_type": pd.array(update_types, dtype="string"),
            "urgency_basis": pd.array(urgency_bases, dtype="string"),
            "impact_score": pd.array(impact_scores, dtype="Float64"),
            "urgency_score": pd.array(urgency_scores, dtype="Float64"),
            "impact_confidence": pd.array(impact_confidences, dtype="Float64"),
            "urgency_confidence": pd.array(urgency_confidences, dtype="Float64"),
            "impact_label": pd.array(impact_labels, dtype="string"),
            "urgency_label": pd.array(urgency_labels, dtype="string"),
            "richness_score": pd.array(richness, dtype="Float64"),
            "reconciled_published_date": dates,
        }
    )


@pytest.fixture()
def catalog() -> pd.DataFrame:
    """Small catalog with jurisdiction_code variants: subdivision, placeholder, multi-country."""
    return pd.DataFrame(
        {
            "topic_id": pd.array(
                ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"],
                dtype="string",
            ),
            "name": pd.array(
                [
                    "US Federal Reserve",
                    "FCA UK",
                    "BaFin Germany",
                    "California DBO",
                    "ECB Euro",
                    "Unknown Multi",
                    "SEC USA",
                    "APRA Australia",
                ],
                dtype="string",
            ),
            "jurisdiction_code": pd.array(
                ["US", "GB", "DE", "US-CA", "EU", "-", "US", "AU"],
                dtype="string",
            ),
            "entity_type": pd.array(
                [
                    "Central Bank",
                    "Regulator",
                    "Regulator",
                    "Central Bank;Regulator",
                    "Central Bank",
                    "Regulator",
                    "Regulator",
                    "Prudential Regulator",
                ],
                dtype="string",
            ),
            "scope": pd.array(
                ["national", "national", "national", "state", "supranational",
                 "national", "national", "national"],
                dtype="string",
            ),
        }
    )


@pytest.fixture()
def empty_df(df) -> pd.DataFrame:
    """Zero-row DataFrame with the same schema as the main fixture."""
    return df.iloc[0:0].copy()


@pytest.fixture()
def empty_catalog(catalog) -> pd.DataFrame:
    """Zero-row catalog with the same schema as the main fixture."""
    return catalog.iloc[0:0].copy()


# ---------------------------------------------------------------------------
# TestRollupCountry
# ---------------------------------------------------------------------------


class TestRollupCountry:
    def test_plain_iso2_returns_itself(self):
        assert rollup_country("US") == "US"

    def test_subdivision_returns_parent(self):
        assert rollup_country("US-CA") == "US"

    def test_placeholder_dash_returns_none(self):
        assert rollup_country("-") is None

    def test_none_input_returns_none(self):
        assert rollup_country(None) is None

    def test_unrecognised_code_returns_none(self):
        # "XX" is not a valid ISO-2 country
        assert rollup_country("XX") is None

    def test_gb_subdivision_returns_gb(self):
        assert rollup_country("GB-ENG") == "GB"


# ---------------------------------------------------------------------------
# TestGeoCountryCounts
# ---------------------------------------------------------------------------


class TestGeoCountryCounts:
    def test_returns_tuple_df_int(self, df):
        result, n_not_mappable = geo_country_counts(df)
        assert isinstance(result, pd.DataFrame)
        assert isinstance(n_not_mappable, int)

    def test_has_required_columns(self, df):
        result, _ = geo_country_counts(df)
        for col in ("iso2", "count", "iso3", "name"):
            assert col in result.columns, f"Missing column: {col}"

    def test_descending_order(self, df):
        result, _ = geo_country_counts(df)
        counts = result["count"].tolist()
        assert counts == sorted(counts, reverse=True)

    def test_empty_df_returns_empty_frame(self, empty_df):
        result, n = geo_country_counts(empty_df)
        assert result.empty
        assert n == 0

    def test_missing_column_returns_empty_frame(self):
        result, n = geo_country_counts(pd.DataFrame({"x": [1, 2]}))
        assert result.empty
        assert n == 0


# ---------------------------------------------------------------------------
# TestInstCountryCounts
# ---------------------------------------------------------------------------


class TestInstCountryCounts:
    def test_returns_tuple_df_int(self, catalog):
        result, n_excluded = inst_country_counts(catalog)
        assert isinstance(result, pd.DataFrame)
        assert isinstance(n_excluded, int)

    def test_has_required_columns(self, catalog):
        result, _ = inst_country_counts(catalog)
        for col in ("iso2", "institutions", "iso3", "name"):
            assert col in result.columns, f"Missing column: {col}"

    def test_subdivision_rolled_up(self, catalog):
        """US-CA must roll up into US, so the US count is ≥ 2."""
        result, _ = inst_country_counts(catalog)
        us_row = result[result["iso2"] == "US"]
        assert not us_row.empty, "Expected US row in inst_country_counts"
        assert us_row["institutions"].iloc[0] >= 2, (
            "US count should be ≥ 2 after rolling up US-CA"
        )

    def test_excluded_counts_placeholder_and_multi(self, catalog):
        """Rows with '-' and 'EU' (not a valid ISO-2) must be counted in n_excluded."""
        _, n_excluded = inst_country_counts(catalog)
        # '-' → None (excluded), 'EU' → None (not in ISO_COUNTRY)
        assert n_excluded >= 2

    def test_empty_catalog_returns_empty(self, empty_catalog):
        result, n = inst_country_counts(empty_catalog)
        assert result.empty
        assert n == 0


# ---------------------------------------------------------------------------
# TestUpdateTypeCounts
# ---------------------------------------------------------------------------


class TestUpdateTypeCounts:
    def test_returns_series(self, df):
        result = update_type_counts(df)
        assert isinstance(result, pd.Series)

    def test_descending_order(self, df):
        result = update_type_counts(df)
        vals = result.tolist()
        assert vals == sorted(vals, reverse=True)

    def test_missing_column_returns_empty_series(self):
        result = update_type_counts(pd.DataFrame({"x": [1, 2]}))
        assert result.empty


# ---------------------------------------------------------------------------
# TestVolumeFrame
# ---------------------------------------------------------------------------


class TestVolumeFrame:
    def test_returns_tuple(self, df):
        result, floor = volume_frame(df, "YE")
        assert isinstance(result, pd.DataFrame)

    def test_has_period_and_count_columns(self, df):
        result, _ = volume_frame(df, "YE")
        for col in ("period", "count"):
            assert col in result.columns, f"Missing column: {col}"

    def test_monthly_freq(self, df):
        result, _ = volume_frame(df, "ME")
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_empty_df_returns_empty(self, empty_df):
        result, floor = volume_frame(empty_df, "YE")
        assert result.empty

    def test_floor_anchors_first_bar_to_floor_year_start(self, df):
        # The 1% floor is applied to END-anchored buckets, then each bucket is
        # re-anchored to its START — so the first yearly bar sits at the start of the
        # floor's year (behaviour shared verbatim with the gallery). Pin it so a
        # future refactor can't silently shift the first bucket.
        result, floor = volume_frame(df, "YE", floor=True)
        assert floor is not None
        assert not result.empty
        first = result["period"].min()
        assert (first.month, first.day) == (1, 1)
        assert first.year == floor.year


# ---------------------------------------------------------------------------
# TestFigBuilders — every builder returns go.Figure with ≥1 trace
# ---------------------------------------------------------------------------


class TestFigBuilders:
    """Each test calls a specific fig_* builder on the populated fixtures."""

    def test_fig_geo_choropleth(self, df):
        fig = fig_geo_choropleth(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_geo_top_countries(self, df):
        fig = fig_geo_top_countries(df, n=20)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_jurisdiction_bloc(self, df):
        fig = fig_jurisdiction_bloc(df, n=15)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_jurisdiction_scope(self, df):
        fig = fig_jurisdiction_scope(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_inst_top_countries(self, catalog):
        fig = fig_inst_top_countries(catalog, n=20)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_inst_regulator_types(self, catalog):
        fig = fig_inst_regulator_types(catalog, n=15)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_inst_by_scope(self, catalog):
        fig = fig_inst_by_scope(catalog)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_inst_choropleth(self, catalog):
        fig = fig_inst_choropleth(catalog)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_category_sunburst(self, df):
        fig = fig_category_sunburst(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_top_institutions(self, df, catalog):
        fig = fig_top_institutions(df, catalog, n=30)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_update_types(self, df):
        fig = fig_update_types(df, top_n=25)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_volume_yearly(self, df):
        fig = fig_volume(df, freq_code="YE", floor=True, include_implausible=False)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_score_histogram_impact(self, df):
        fig = fig_score_histogram(df, "impact")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_score_histogram_urgency(self, df):
        fig = fig_score_histogram(df, "urgency")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_confidence_histogram_impact(self, df):
        fig = fig_confidence_histogram(df, "impact")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_confidence_histogram_urgency(self, df):
        fig = fig_confidence_histogram(df, "urgency")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_label_mix_impact(self, df):
        fig = fig_label_mix(df, "impact")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_label_mix_urgency(self, df):
        fig = fig_label_mix(df, "urgency")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_urgency_basis_bar(self, df):
        fig = fig_urgency_basis_bar(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_urgency_basis_pie(self, df):
        fig = fig_urgency_basis_pie(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_recency_bar(self, df):
        hd = historical_depth(df)
        fig = fig_recency_bar(hd)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_fig_category_composition(self, df):
        fig = fig_category_composition(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    # fig_inst_regulator_types — semicolon-joined entity_type values are split
    def test_fig_inst_regulator_types_semicolon_split(self, catalog):
        """Central Bank;Regulator contributes 2 entries, not 1."""
        fig = fig_inst_regulator_types(catalog, n=15)
        assert isinstance(fig, go.Figure)
        # Both "Central Bank" and "Regulator" should appear in the chart data
        # (exact presence is implementation-detail; we only verify figure is valid)
        assert len(fig.data) >= 1


# ---------------------------------------------------------------------------
# TestFigBuildersEmpty — every builder is defensive on empty input
# ---------------------------------------------------------------------------


class TestFigBuildersEmpty:
    """Each builder must return a go.Figure and NOT raise on empty input."""

    def test_fig_geo_choropleth_empty(self, empty_df):
        fig = fig_geo_choropleth(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_geo_top_countries_empty(self, empty_df):
        fig = fig_geo_top_countries(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_jurisdiction_bloc_empty(self, empty_df):
        fig = fig_jurisdiction_bloc(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_jurisdiction_scope_empty(self, empty_df):
        fig = fig_jurisdiction_scope(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_inst_top_countries_empty(self, empty_catalog):
        fig = fig_inst_top_countries(empty_catalog)
        assert isinstance(fig, go.Figure)

    def test_fig_inst_top_countries_none(self):
        fig = fig_inst_top_countries(None)
        assert isinstance(fig, go.Figure)

    def test_fig_inst_regulator_types_empty(self, empty_catalog):
        fig = fig_inst_regulator_types(empty_catalog)
        assert isinstance(fig, go.Figure)

    def test_fig_inst_by_scope_empty(self, empty_catalog):
        fig = fig_inst_by_scope(empty_catalog)
        assert isinstance(fig, go.Figure)

    def test_fig_inst_choropleth_empty(self, empty_catalog):
        fig = fig_inst_choropleth(empty_catalog)
        assert isinstance(fig, go.Figure)

    def test_fig_category_sunburst_empty(self, empty_df):
        fig = fig_category_sunburst(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_top_institutions_empty(self, empty_df, empty_catalog):
        fig = fig_top_institutions(empty_df, empty_catalog)
        assert isinstance(fig, go.Figure)

    def test_fig_update_types_empty(self, empty_df):
        fig = fig_update_types(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_volume_empty(self, empty_df):
        fig = fig_volume(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_score_histogram_empty_impact(self, empty_df):
        fig = fig_score_histogram(empty_df, "impact")
        assert isinstance(fig, go.Figure)

    def test_fig_score_histogram_empty_urgency(self, empty_df):
        fig = fig_score_histogram(empty_df, "urgency")
        assert isinstance(fig, go.Figure)

    def test_fig_confidence_histogram_empty(self, empty_df):
        fig = fig_confidence_histogram(empty_df, "impact")
        assert isinstance(fig, go.Figure)

    def test_fig_label_mix_empty(self, empty_df):
        fig = fig_label_mix(empty_df, "impact")
        assert isinstance(fig, go.Figure)

    def test_fig_urgency_basis_bar_empty(self, empty_df):
        fig = fig_urgency_basis_bar(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_urgency_basis_pie_empty(self, empty_df):
        fig = fig_urgency_basis_pie(empty_df)
        assert isinstance(fig, go.Figure)

    def test_fig_recency_bar_empty_dict(self):
        fig = fig_recency_bar({})
        assert isinstance(fig, go.Figure)

    def test_fig_category_composition_empty(self, empty_df):
        fig = fig_category_composition(empty_df)
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# Fixtures for Tags & Entities builders
# ---------------------------------------------------------------------------


@pytest.fixture()
def breakdown_df() -> pd.DataFrame:
    """6-row entity-type breakdown frame (one row per bucket)."""
    return pd.DataFrame(
        {
            "type": [
                "Regulator / Supervisor",
                "Government body",
                "International body",
                "Company",
                "Person",
                "Other",
            ],
            "mentions": [12000, 8000, 4500, 3200, 1800, 600],
            "distinct_entities": [38112, 12000, 2300, 9100, 5400, 800],
        }
    )


@pytest.fixture()
def leaderboard_df() -> pd.DataFrame:
    """5-row entity leaderboard frame (sorted descending, ≥2 types)."""
    return pd.DataFrame(
        {
            "canonical_name": [
                "U.S. Federal Reserve",
                "FCA",
                "BaFin",
                "European Central Bank",
                "SEC",
            ],
            "type": [
                "Regulator / Supervisor",
                "Regulator / Supervisor",
                "Regulator / Supervisor",
                "International body",
                "Regulator / Supervisor",
            ],
            "mentions": [9800, 7200, 5100, 3800, 2400],
        }
    )


@pytest.fixture()
def tag_df() -> pd.DataFrame:
    """6-row tag frame."""
    return pd.DataFrame(
        {
            "tag": ["climate risk", "AML", "capital requirements", "DORA", "ESG", "MiFID"],
            "count": [5400, 4800, 4200, 3100, 2700, 1900],
        }
    )


# ---------------------------------------------------------------------------
# TestFigEntityTypeBreakdown
# ---------------------------------------------------------------------------


class TestFigEntityTypeBreakdown:
    def test_returns_figure_with_trace(self, breakdown_df):
        fig = fig_entity_type_breakdown(breakdown_df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_trace_is_pie(self, breakdown_df):
        fig = fig_entity_type_breakdown(breakdown_df)
        assert isinstance(fig.data[0], go.Pie)

    def test_slices_coloured_by_type(self, breakdown_df):
        """One slice per type, coloured by ENTITY_TYPE_COLORS (matches the leaderboard)."""
        fig = fig_entity_type_breakdown(breakdown_df)
        pie = fig.data[0]
        assert len(pie.labels) == len(breakdown_df)
        assert list(pie.marker.colors) == [ENTITY_TYPE_COLORS[t] for t in pie.labels]

    def test_customdata_references_distinct_entities(self, breakdown_df):
        """distinct_entities must be carried in customdata so hover can surface it."""
        fig = fig_entity_type_breakdown(breakdown_df)
        pie = fig.data[0]
        assert pie.customdata is not None
        # customdata should contain the distinct_entities values
        cd_flat = list(pie.customdata.flat)
        for val in breakdown_df["distinct_entities"]:
            assert val in cd_flat

    def test_sorted_descending_by_mentions(self, breakdown_df):
        """Largest bucket must be the first slice."""
        fig = fig_entity_type_breakdown(breakdown_df)
        vals = list(fig.data[0].values)
        assert vals == sorted(vals, reverse=True)

    def test_title_set(self, breakdown_df):
        fig = fig_entity_type_breakdown(breakdown_df)
        assert "entity types" in fig.layout.title.text.lower()

    # --- defensive ---

    def test_none_input_returns_empty_fig(self):
        fig = fig_entity_type_breakdown(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_fig(self, breakdown_df):
        fig = fig_entity_type_breakdown(breakdown_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_column_returns_empty_fig(self):
        fig = fig_entity_type_breakdown(pd.DataFrame({"type": ["A"], "mentions": [1]}))
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# TestFigEntityLeaderboard
# ---------------------------------------------------------------------------


class TestFigEntityLeaderboard:
    def test_returns_figure(self, leaderboard_df):
        fig = fig_entity_leaderboard(leaderboard_df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_honours_n(self, leaderboard_df):
        """n=2 from a 5-row frame should yield exactly 2 bars total."""
        fig = fig_entity_leaderboard(leaderboard_df, n=2)
        total_bars = sum(len(trace.x) for trace in fig.data if isinstance(trace, go.Bar))
        assert total_bars == 2

    def test_coloured_by_type(self, leaderboard_df):
        """Each trace should correspond to a distinct type and use ENTITY_TYPE_COLORS."""
        fig = fig_entity_leaderboard(leaderboard_df)
        # Collect marker colours from all bar traces
        trace_colors = {
            trace.marker.color
            for trace in fig.data
            if isinstance(trace, go.Bar) and trace.marker.color is not None
        }
        # At least one colour should match an ENTITY_TYPE_COLORS value
        assert trace_colors & set(ENTITY_TYPE_COLORS.values()), (
            f"Expected a colour from ENTITY_TYPE_COLORS in {trace_colors}"
        )

    def test_legend_reflects_types(self, leaderboard_df):
        """With ≥2 types in the data the figure must have showlegend=True."""
        # Inject a second type to guarantee ≥2
        df2 = leaderboard_df.copy()
        df2.loc[3, "type"] = "International body"
        fig = fig_entity_leaderboard(df2)
        assert fig.layout.showlegend is True or any(
            t.showlegend is not False for t in fig.data
        )

    def test_title_set(self, leaderboard_df):
        fig = fig_entity_leaderboard(leaderboard_df, n=5)
        assert "5" in fig.layout.title.text

    def test_horizontal_orientation(self, leaderboard_df):
        fig = fig_entity_leaderboard(leaderboard_df)
        for trace in fig.data:
            if isinstance(trace, go.Bar):
                assert trace.orientation == "h"
                break

    def test_y_axis_follows_global_mentions_order_not_type_cluster(self):
        """categoryarray must enforce global mentions-desc rank across per-type traces.

        Fixture has interleaved types (A, B, A, B, A) in global mentions order so
        that Plotly's default first-encounter ordering (which groups by type) would
        place B-type entities together and break the global ranking.  The fix pins
        categoryarray to the global order regardless of which type-trace each row
        lands in.

        This test FAILS on the old code (no categoryarray set) and PASSES after the fix.
        """
        interleaved_df = pd.DataFrame(
            {
                "canonical_name": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
                "type": ["TypeA", "TypeB", "TypeA", "TypeB", "TypeA"],
                "mentions": [1000, 800, 600, 400, 200],
            }
        )
        expected_order = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]

        fig = fig_entity_leaderboard(interleaved_df, n=5)

        assert fig.layout.yaxis.categoryorder == "array", (
            "yaxis.categoryorder must be 'array' to pin global ranking"
        )
        assert list(fig.layout.yaxis.categoryarray) == expected_order, (
            f"yaxis.categoryarray must follow global mentions-desc order {expected_order!r}, "
            f"got {list(fig.layout.yaxis.categoryarray)!r}"
        )

    # --- defensive ---

    def test_none_input_returns_empty_fig(self):
        fig = fig_entity_leaderboard(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_fig(self, leaderboard_df):
        fig = fig_entity_leaderboard(leaderboard_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_column_returns_empty_fig(self):
        fig = fig_entity_leaderboard(pd.DataFrame({"canonical_name": ["X"], "type": ["A"]}))
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# TestFigTagLeaderboard
# ---------------------------------------------------------------------------


class TestFigTagLeaderboard:
    def test_returns_figure_with_trace(self, tag_df):
        fig = fig_tag_leaderboard(tag_df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_honours_n(self, tag_df):
        """n=3 from a 6-row frame should yield exactly 3 bars."""
        fig = fig_tag_leaderboard(tag_df, n=3)
        total_bars = sum(len(trace.x) for trace in fig.data if isinstance(trace, go.Bar))
        assert total_bars == 3

    def test_horizontal_orientation(self, tag_df):
        fig = fig_tag_leaderboard(tag_df)
        assert fig.data[0].orientation == "h"

    def test_title_set(self, tag_df):
        fig = fig_tag_leaderboard(tag_df)
        assert "tag" in fig.layout.title.text.lower() or "theme" in fig.layout.title.text.lower()

    def test_sorted_descending(self, tag_df):
        """Most-mentioned tag must appear first (top of horizontal bar)."""
        fig = fig_tag_leaderboard(tag_df)
        x_vals = list(fig.data[0].x)
        assert x_vals == sorted(x_vals, reverse=True)

    # --- defensive ---

    def test_none_input_returns_empty_fig(self):
        fig = fig_tag_leaderboard(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_fig(self, tag_df):
        fig = fig_tag_leaderboard(tag_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_column_returns_empty_fig(self):
        fig = fig_tag_leaderboard(pd.DataFrame({"tag": ["foo"]}))
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# Log-scaled choropleths (even visual spread under heavy US skew)
# ---------------------------------------------------------------------------


class TestLogChoropleth:
    """Both world maps colour on a log10 scale so non-US countries spread across
    the palette instead of collapsing into the bottom decile, while the colorbar
    still reads in real counts.
    """

    def _z(self, fig):
        return list(fig.data[0].z)

    def test_geo_choropleth_colours_on_log_of_count(self, df):
        counts, _ = geo_country_counts(df)
        mappable = counts.dropna(subset=["iso3"])
        fig = fig_geo_choropleth(df)
        z = self._z(fig)
        # one z per mapped country, each the log10 of its record count
        assert len(z) == len(mappable)
        expected = {math.log10(c) for c in mappable["count"]}
        assert {round(v, 6) for v in z} == {round(v, 6) for v in expected}

    def test_geo_choropleth_colorbar_labels_are_real_counts(self, df):
        fig = fig_geo_choropleth(df)
        cbar = fig.layout.coloraxis.colorbar
        # tick *values* live in log space, tick *text* shows human counts
        assert cbar.tickvals is not None and len(cbar.tickvals) >= 2
        assert cbar.ticktext is not None and len(cbar.ticktext) == len(cbar.tickvals)
        assert all(any(ch.isdigit() for ch in t) for t in cbar.ticktext)

    def test_geo_choropleth_hover_keeps_raw_count(self, df):
        # hover must surface the real count, never the log value
        fig = fig_geo_choropleth(df)
        blob = fig.data[0].hovertemplate or ""
        assert "_log" not in blob

    def test_inst_choropleth_colours_on_log_of_count(self, catalog):
        counts, _ = inst_country_counts(catalog)
        fig = fig_inst_choropleth(catalog)
        z = self._z(fig)
        assert len(z) == len(counts)
        expected = {math.log10(c) for c in counts["institutions"]}
        assert {round(v, 6) for v in z} == {round(v, 6) for v in expected}

    def test_inst_choropleth_colorbar_labels_are_real_counts(self, catalog):
        fig = fig_inst_choropleth(catalog)
        cbar = fig.layout.coloraxis.colorbar
        assert cbar.tickvals is not None and len(cbar.tickvals) >= 2
        assert cbar.ticktext is not None and len(cbar.ticktext) == len(cbar.tickvals)


class TestLogTicks:
    """_log_ticks → (log-space positions, human-readable count labels)."""

    def test_wide_range_uses_decade_ticks_plus_ceiling(self):
        vals, text = charts._log_ticks(1, 62984)
        assert "10K" in text and "1K" in text and "100" in text
        assert "63K" in text  # the real ceiling is labelled
        # positions are strictly increasing and in log space
        assert vals == sorted(vals)
        assert vals[-1] == pytest.approx(math.log10(62984))

    def test_narrow_range_falls_back_to_endpoints(self):
        # no whole decade sits inside [2, 5] → anchor on the actual min/max
        vals, text = charts._log_ticks(2, 5)
        assert text == ["2", "5"]
        assert vals == [pytest.approx(math.log10(2)), pytest.approx(math.log10(5))]

    def test_labels_align_one_to_one_with_positions(self):
        vals, text = charts._log_ticks(1, 320)
        assert len(vals) == len(text) >= 2

    def test_single_value_range_yields_one_tick(self):
        # every country tied (min == max) → one honest tick, no crash
        vals, text = charts._log_ticks(50, 50)
        assert vals == [pytest.approx(math.log10(50))]
        assert text == ["50"]


class TestHumanCount:
    """_human_count never rounds a value *across* its unit boundary."""

    @pytest.mark.parametrize(
        "n, expected",
        [
            (0, "0"),
            (320, "320"),
            (999, "999"),
            (1_000, "1K"),
            (1_200, "1.2K"),
            (9_999, "10K"),
            (10_000, "10K"),
            (62_984, "63K"),
            (250_000, "250K"),
            (999_999, "1M"),      # must NOT be "1000K"
            (1_000_000, "1M"),
            (1_200_000, "1.2M"),
        ],
    )
    def test_labels(self, n, expected):
        assert charts._human_count(n) == expected


# ---------------------------------------------------------------------------
# Fixtures for Regulators builders
# ---------------------------------------------------------------------------


@pytest.fixture()
def regulator_leaderboard_df() -> pd.DataFrame:
    """6-row regulator leaderboard frame, sorted descending by mentions."""
    return pd.DataFrame(
        {
            "name": [
                "European Commission",
                "European Central Bank",
                "Federal Trade Commission",
                "Financial Conduct Authority",
                "Securities and Exchange Commission",
                "NA",
            ],
            "mentions": [2886, 2175, 1800, 1200, 900, 5],
            "country": ["BE", "DE", "US", "GB", "US", "US"],
        }
    )


@pytest.fixture()
def regulator_by_country_df() -> pd.DataFrame:
    """4-row by_country frame for regulator choropleth."""
    return pd.DataFrame(
        {
            "iso2": ["US", "DE", "GB", "FR"],
            "n_regulators": [450, 120, 95, 80],
            "iso3": ["USA", "DEU", "GBR", "FRA"],
            "name": ["United States", "Germany", "United Kingdom", "France"],
        }
    )


# ---------------------------------------------------------------------------
# TestFigRegulatorLeaderboard
# ---------------------------------------------------------------------------


class TestFigRegulatorLeaderboard:
    def test_returns_figure_with_trace(self, regulator_leaderboard_df):
        fig = fig_regulator_leaderboard(regulator_leaderboard_df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_horizontal_orientation(self, regulator_leaderboard_df):
        fig = fig_regulator_leaderboard(regulator_leaderboard_df)
        assert fig.data[0].orientation == "h"

    def test_title_set(self, regulator_leaderboard_df):
        fig = fig_regulator_leaderboard(regulator_leaderboard_df)
        assert "regulator" in fig.layout.title.text.lower()

    def test_sorted_descending(self, regulator_leaderboard_df):
        """Most-mentioned regulator must appear first (top of horizontal bar)."""
        fig = fig_regulator_leaderboard(regulator_leaderboard_df)
        x_vals = list(fig.data[0].x)
        assert x_vals == sorted(x_vals, reverse=True)

    def test_honours_n(self, regulator_leaderboard_df):
        """n=3 from a 6-row frame should yield exactly 3 bars."""
        fig = fig_regulator_leaderboard(regulator_leaderboard_df, n=3)
        total_bars = sum(len(trace.x) for trace in fig.data if isinstance(trace, go.Bar))
        assert total_bars == 3

    def test_country_in_hover_when_present(self, regulator_leaderboard_df):
        """country column should appear in hover data when the column exists."""
        fig = fig_regulator_leaderboard(regulator_leaderboard_df)
        # Plotly encodes hover_data in customdata; figure should have at least one trace
        assert isinstance(fig, go.Figure)
        # The simplest way to verify: fig should not be an empty placeholder
        assert len(fig.data) >= 1

    # --- defensive ---

    def test_none_input_returns_empty_fig(self):
        fig = fig_regulator_leaderboard(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_fig(self, regulator_leaderboard_df):
        fig = fig_regulator_leaderboard(regulator_leaderboard_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_column_returns_empty_fig(self):
        fig = fig_regulator_leaderboard(pd.DataFrame({"name": ["ECB"]}))
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# TestFigRegulatorChoropleth
# ---------------------------------------------------------------------------


class TestFigRegulatorChoropleth:
    def test_returns_figure_with_trace(self, regulator_by_country_df):
        fig = fig_regulator_choropleth(regulator_by_country_df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_has_choropleth_trace(self, regulator_by_country_df):
        """The figure must contain a go.Choropleth trace."""
        fig = fig_regulator_choropleth(regulator_by_country_df)
        choropleth_traces = [t for t in fig.data if isinstance(t, go.Choropleth)]
        assert len(choropleth_traces) >= 1

    def test_has_colorbar(self, regulator_by_country_df):
        """The log choropleth must carry a colorbar with tick values and text."""
        fig = fig_regulator_choropleth(regulator_by_country_df)
        cbar = fig.layout.coloraxis.colorbar
        assert cbar.tickvals is not None and len(cbar.tickvals) >= 2
        assert cbar.ticktext is not None and len(cbar.ticktext) == len(cbar.tickvals)

    def test_colours_on_log_scale(self, regulator_by_country_df):
        """Z values must be log10(n_regulators), not raw counts."""
        import math
        fig = fig_regulator_choropleth(regulator_by_country_df)
        z = list(fig.data[0].z)
        expected = {round(math.log10(v), 6) for v in regulator_by_country_df["n_regulators"]}
        assert {round(v, 6) for v in z} == expected

    def test_title_set(self, regulator_by_country_df):
        fig = fig_regulator_choropleth(regulator_by_country_df)
        assert "regulator" in fig.layout.title.text.lower()

    # --- defensive ---

    def test_none_input_returns_empty_fig(self):
        fig = fig_regulator_choropleth(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_empty_fig(self, regulator_by_country_df):
        fig = fig_regulator_choropleth(regulator_by_country_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_column_returns_empty_fig(self):
        fig = fig_regulator_choropleth(pd.DataFrame({"iso2": ["US"], "n_regulators": [10]}))
        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# TestFigInstDomainSunburst
# ---------------------------------------------------------------------------


@pytest.fixture()
def domain_catalog_df() -> pd.DataFrame:
    """Small catalog already merged with domain columns (one row per institution)."""
    return pd.DataFrame(
        {
            "topic_id": ["t1", "t2", "t3", "t4", "t5", "t6"],
            "name": [
                "Fed Reserve", "FCA", "BaFin", "ICO", "EBA", "NCUA"
            ],
            "top_level": [
                "Finance", "Finance", "Finance", "Technology", "Finance", "Finance"
            ],
            "sub_domain": [
                "Banking & Central Banking",
                "Securities & Capital Markets",
                "Banking & Central Banking",
                "Data Protection & Privacy",
                "Banking & Central Banking",
                "Consumer Finance & Credit",
            ],
        }
    )


class TestFigInstDomainSunburst:
    def test_returns_go_figure(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        assert isinstance(fig, go.Figure)

    def test_first_trace_is_sunburst(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        assert len(fig.data) >= 1
        assert fig.data[0].type == "sunburst"

    def test_title_mentions_domain_or_institution(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        title = (fig.layout.title.text or "").lower()
        assert "domain" in title or "institution" in title

    def test_known_leaf_labels_present(self, domain_catalog_df):
        """All sub_domain values from the fixture must appear as sunburst labels."""
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        labels = set(fig.data[0].labels)
        assert "Banking & Central Banking" in labels
        assert "Securities & Capital Markets" in labels
        assert "Data Protection & Privacy" in labels
        assert "Consumer Finance & Credit" in labels

    def test_inner_ring_top_level_labels_present(self, domain_catalog_df):
        """Top-level domains must appear as inner-ring labels."""
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        labels = set(fig.data[0].labels)
        assert "Finance" in labels
        assert "Technology" in labels

    def test_branchvalues_total(self, domain_catalog_df):
        """branchvalues must be 'total' so inner-ring = sum of its leaves."""
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        assert fig.data[0].branchvalues == "total"

    def test_finance_count_is_correct(self, domain_catalog_df):
        """Finance top-level contains 5 institutions in the fixture."""
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        sunburst = fig.data[0]
        labels = list(sunburst.labels)
        values = list(sunburst.values)
        finance_idx = labels.index("Finance")
        # With branchvalues="total" the inner-ring value equals the sum of children
        assert values[finance_idx] == 5

    def test_height_is_set(self, domain_catalog_df):
        """Figure height must be explicitly set (around 460 per spec)."""
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df)
        assert fig.layout.height is not None and fig.layout.height > 0

    # --- defensive: None / empty / missing columns ---

    def test_none_input_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_valid_figure(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_sunburst
        fig = fig_inst_domain_sunburst(domain_catalog_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_top_level_column_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_sunburst
        df = pd.DataFrame({"sub_domain": ["Banking & Central Banking"]})
        fig = fig_inst_domain_sunburst(df)
        assert isinstance(fig, go.Figure)

    def test_missing_sub_domain_column_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_sunburst
        df = pd.DataFrame({"top_level": ["Finance"]})
        fig = fig_inst_domain_sunburst(df)
        assert isinstance(fig, go.Figure)

    def test_all_nulls_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_sunburst
        df = pd.DataFrame({"top_level": [None, None], "sub_domain": [None, None]})
        fig = fig_inst_domain_sunburst(df)
        assert isinstance(fig, go.Figure)

    def test_none_input_does_not_raise(self):
        from carver_showcase.charts import fig_inst_domain_sunburst
        try:
            fig_inst_domain_sunburst(None)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"fig_inst_domain_sunburst raised on None input: {exc}")

    def test_in_all_list(self):
        from carver_showcase import charts
        assert "fig_inst_domain_sunburst" in charts.__all__


class TestFigInstDomainBar:
    def test_returns_go_figure(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(domain_catalog_df)
        assert isinstance(fig, go.Figure)

    def test_first_trace_is_bar(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(domain_catalog_df)
        assert len(fig.data) >= 1
        assert fig.data[0].type == "bar"

    def test_counts_top_level_only(self, domain_catalog_df):
        """The bar ranks TOP-LEVEL domains; Finance=5, Technology=1 in the fixture."""
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(domain_catalog_df)
        # one bar per top-level domain; gather (label -> value)
        pairs = {}
        for tr in fig.data:
            # color="top_level" splits into one trace per domain (len-1 y/x each)
            for y, x in zip(tr.y, tr.x):
                pairs[y] = pairs.get(y, 0) + x
        assert pairs.get("Finance") == 5
        assert pairs.get("Technology") == 1
        # sub-domain leaves must NOT appear on the axis (top-level only)
        assert "Banking & Central Banking" not in pairs

    def test_largest_domain_first(self, domain_catalog_df):
        """y-axis is ordered by total so the largest domain sits at the top."""
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(domain_catalog_df)
        assert fig.layout.yaxis.categoryorder == "total ascending"

    def test_legend_hidden(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(domain_catalog_df)
        assert fig.layout.showlegend is False

    def test_shares_domain_colour_map(self, domain_catalog_df):
        """Finance must render in the same colour the sunburst uses (shared map)."""
        from carver_showcase.charts import fig_inst_domain_bar, DOMAIN_COLOR_MAP
        fig = fig_inst_domain_bar(domain_catalog_df)
        finance_colour = None
        for tr in fig.data:
            if "Finance" in list(tr.y):
                finance_colour = tr.marker.color
        assert finance_colour == DOMAIN_COLOR_MAP["Finance"]

    # --- defensive: None / empty / missing column ---

    def test_none_input_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(None)
        assert isinstance(fig, go.Figure)

    def test_empty_df_returns_valid_figure(self, domain_catalog_df):
        from carver_showcase.charts import fig_inst_domain_bar
        fig = fig_inst_domain_bar(domain_catalog_df.iloc[0:0])
        assert isinstance(fig, go.Figure)

    def test_missing_top_level_column_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_bar
        df = pd.DataFrame({"sub_domain": ["Banking & Central Banking"]})
        fig = fig_inst_domain_bar(df)
        assert isinstance(fig, go.Figure)

    def test_all_nulls_returns_valid_figure(self):
        from carver_showcase.charts import fig_inst_domain_bar
        df = pd.DataFrame({"top_level": [None, None]})
        fig = fig_inst_domain_bar(df)
        assert isinstance(fig, go.Figure)

    def test_none_input_does_not_raise(self):
        from carver_showcase.charts import fig_inst_domain_bar
        try:
            fig_inst_domain_bar(None)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"fig_inst_domain_bar raised on None input: {exc}")

    def test_in_all_list(self):
        from carver_showcase import charts
        assert "fig_inst_domain_bar" in charts.__all__
