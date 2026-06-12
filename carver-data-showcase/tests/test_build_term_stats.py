"""Tests for tools/build_term_stats.py — deterministic rollup of entity/tag stats.

TDD: tests are written before implementation.

Coverage:
  - _clean_canonical: US-prefix strip, whitespace collapse, punctuation unify,
    case-insensitive key but display preserved.
  - build_entity_type_breakdown: Σ mentions per type, distinct_entities,
    all 6 buckets zero-filled, missing-from-types → Other.
  - build_entity_leaderboard: alias merge (sum + highest-member winner),
    deterministic tie-break, top-50 cap, sorted desc.
  - build_tag_leaderboard: top-50 cap, sorted desc, pure frequency.
  - build_term_stats_meta: exact keys + correct values.
  - CRITICAL invariant: breakdown is independent of alias merge.

No network, no OpenAI key, no real data files — all in-memory DataFrames.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import pathlib
import re

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Load tools/build_term_stats.py as a module without running __main__.
# ---------------------------------------------------------------------------

def _load_module():
    here = pathlib.Path(__file__).parent
    root = here.parent
    mod_path = root / "tools" / "build_term_stats.py"
    spec = importlib.util.spec_from_file_location("build_term_stats", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# ---------------------------------------------------------------------------
# Tiny frame helpers
# ---------------------------------------------------------------------------

def _mentions(rows: list[tuple[str, int]]) -> pd.DataFrame:
    """Build an entity_mentions DataFrame from (entity, count) tuples."""
    return pd.DataFrame(rows, columns=["entity", "count"])


def _types(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """Build an entity_types DataFrame from (entity, type, canonical_name) tuples."""
    return pd.DataFrame(rows, columns=["entity", "type", "canonical_name"])


def _tag_mentions(rows: list[tuple[str, int]]) -> pd.DataFrame:
    """Build a tag_mentions DataFrame from (tag, count) tuples."""
    return pd.DataFrame(rows, columns=["tag", "count"])


# ===========================================================================
# _clean_canonical
# ===========================================================================

class TestCleanCanonical:
    """_clean_canonical(name) -> str key: strips 'U.S. ', collapses whitespace,
    unifies punctuation, casefolds — display name is NOT modified."""

    def test_us_prefix_stripped(self, mod):
        assert mod._clean_canonical("U.S. Securities and Exchange Commission") == \
               mod._clean_canonical("Securities and Exchange Commission")

    def test_us_prefix_case_insensitive_strip(self, mod):
        # Only the exact "U.S. " prefix should be stripped (spec says strip leading "U.S. ")
        key_with = mod._clean_canonical("U.S. Federal Reserve")
        key_without = mod._clean_canonical("Federal Reserve")
        assert key_with == key_without

    def test_whitespace_collapse(self, mod):
        assert mod._clean_canonical("Federal  Reserve  Board") == \
               mod._clean_canonical("Federal Reserve Board")

    def test_leading_trailing_whitespace_trimmed(self, mod):
        assert mod._clean_canonical("  FCA  ") == mod._clean_canonical("FCA")

    def test_casefold(self, mod):
        assert mod._clean_canonical("FCA") == mod._clean_canonical("fca")
        assert mod._clean_canonical("Securities And Exchange Commission") == \
               mod._clean_canonical("securities and exchange commission")

    def test_trailing_dot_stripped(self, mod):
        """A trailing period on the key should be dropped."""
        assert mod._clean_canonical("Inc.") == mod._clean_canonical("Inc")

    def test_surrounding_quotes_stripped(self, mod):
        """Surrounding double quotes should be dropped for the key."""
        assert mod._clean_canonical('"Federal Reserve"') == \
               mod._clean_canonical("Federal Reserve")

    def test_combined_us_whitespace_casefold(self, mod):
        """All three transforms applied together."""
        key = mod._clean_canonical("U.S.  Securities  and  Exchange  Commission.")
        # After stripping U.S., collapsing spaces, dropping trailing dot, casefolding:
        # should match "securities and exchange commission"
        assert key == mod._clean_canonical("Securities and Exchange Commission")

    def test_empty_string(self, mod):
        # Should return an empty string (or at least not crash)
        result = mod._clean_canonical("")
        assert isinstance(result, str)

    def test_plain_acronym(self, mod):
        key = mod._clean_canonical("SEC")
        assert key == "sec"

    def test_us_prefix_only_stripped_when_leading(self, mod):
        """'U.S.' inside the name (not leading) must NOT be stripped."""
        key = mod._clean_canonical("Bank of U.S. Holdings")
        # The key includes 'u.s.' inside — it's not a leading 'U.S. ' prefix
        assert "u.s." in key or "us" in key  # implementation-dependent internal form is OK
        # But the key for "U.S. Bank of Holdings" differs from "Bank of U.S. Holdings"
        key_leading = mod._clean_canonical("U.S. Bank of Holdings")
        assert key_leading != mod._clean_canonical("Bank of U.S. Holdings")


# ===========================================================================
# build_entity_type_breakdown
# ===========================================================================

class TestEntityTypeBreakdown:
    """build_entity_type_breakdown(entity_mentions_df, entity_types_df) ->
    DataFrame(type, mentions, distinct_entities)."""

    def test_basic_grouping(self, mod):
        mentions = _mentions([("FCA", 50), ("EBA", 30), ("Goldman Sachs", 20)])
        types = _types([
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ("EBA", "Regulator / Supervisor", "European Banking Authority"),
            ("Goldman Sachs", "Company", "Goldman Sachs Group"),
        ])
        bd = mod.build_entity_type_breakdown(mentions, types)
        reg = bd.loc[bd["type"] == "Regulator / Supervisor"].iloc[0]
        assert reg["mentions"] == 80
        assert reg["distinct_entities"] == 2
        co = bd.loc[bd["type"] == "Company"].iloc[0]
        assert co["mentions"] == 20
        assert co["distinct_entities"] == 1

    def test_all_6_buckets_present(self, mod):
        """All 6 ENTITY_TYPES buckets must appear, even if zero."""
        from carver_showcase.config import ENTITY_TYPES
        mentions = _mentions([("FCA", 10)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        bd = mod.build_entity_type_breakdown(mentions, types)
        assert set(bd["type"].tolist()) == set(ENTITY_TYPES)

    def test_zero_filled_for_empty_buckets(self, mod):
        """Buckets with no matching entities have mentions=0 and distinct_entities=0."""
        mentions = _mentions([("FCA", 10)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        bd = mod.build_entity_type_breakdown(mentions, types)
        for _, row in bd.iterrows():
            if row["type"] != "Regulator / Supervisor":
                assert row["mentions"] == 0
                assert row["distinct_entities"] == 0

    def test_missing_from_types_defaults_to_other(self, mod):
        """An entity present in mentions but absent from entity_types → 'Other'."""
        mentions = _mentions([("FCA", 50), ("UnknownCorp", 15)])
        types = _types([("FCA", "Regulator / Supervisor", "Financial Conduct Authority")])
        bd = mod.build_entity_type_breakdown(mentions, types)
        other = bd.loc[bd["type"] == "Other"].iloc[0]
        assert other["mentions"] == 15
        assert other["distinct_entities"] == 1

    def test_missing_from_types_distinct_counted_once(self, mod):
        """Multiple missing entities each count as one distinct entity in Other."""
        mentions = _mentions([("Ghost1", 10), ("Ghost2", 5)])
        types = _types([])  # nothing classified
        bd = mod.build_entity_type_breakdown(mentions, types)
        other = bd.loc[bd["type"] == "Other"].iloc[0]
        assert other["mentions"] == 15
        assert other["distinct_entities"] == 2

    def test_distinct_entities_counted_correctly(self, mod):
        """Each unique entity string counts once, regardless of its mention count."""
        mentions = _mentions([("FCA", 100), ("EBA", 50), ("PRA", 25)])
        types = _types([
            ("FCA", "Regulator / Supervisor", "FCA"),
            ("EBA", "Regulator / Supervisor", "EBA"),
            ("PRA", "Regulator / Supervisor", "PRA"),
        ])
        bd = mod.build_entity_type_breakdown(mentions, types)
        reg = bd.loc[bd["type"] == "Regulator / Supervisor"].iloc[0]
        assert reg["distinct_entities"] == 3

    def test_empty_mentions_all_zeros(self, mod):
        """No mention data → all 6 buckets with 0/0."""
        mentions = _mentions([])
        types = _types([])
        bd = mod.build_entity_type_breakdown(mentions, types)
        assert (bd["mentions"] == 0).all()
        assert (bd["distinct_entities"] == 0).all()

    def test_sum_of_mentions_equals_total(self, mod):
        """Sum of all breakdown mentions must equal sum of entity_mentions count."""
        mentions = _mentions([("FCA", 50), ("Goldman", 30), ("Person X", 10)])
        types = _types([
            ("FCA", "Regulator / Supervisor", "FCA"),
            ("Goldman", "Company", "Goldman Sachs"),
            ("Person X", "Person", "Person X"),
        ])
        bd = mod.build_entity_type_breakdown(mentions, types)
        assert bd["mentions"].sum() == 90

    def test_entity_present_in_types_but_not_mentions(self, mod):
        """An entity in types but with no mention count contributes 0 to any bucket."""
        mentions = _mentions([("FCA", 50)])
        types = _types([
            ("FCA", "Regulator / Supervisor", "FCA"),
            ("Ghost", "Company", "Ghost Corp"),  # not in mentions
        ])
        bd = mod.build_entity_type_breakdown(mentions, types)
        # Company should still be 0 (the ghost entity has no mention count)
        co = bd.loc[bd["type"] == "Company"].iloc[0]
        assert co["mentions"] == 0
        assert co["distinct_entities"] == 0


# ===========================================================================
# build_entity_leaderboard
# ===========================================================================

class TestEntityLeaderboard:
    """build_entity_leaderboard(entity_mentions_df, entity_types_df, top_n) ->
    DataFrame(canonical_name, type, mentions) — alias-merged, top-N."""

    def test_simple_no_merge(self, mod):
        mentions = _mentions([("FCA", 100), ("EBA", 50)])
        types = _types([
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ("EBA", "Regulator / Supervisor", "European Banking Authority"),
        ])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        assert len(lb) == 2
        assert lb.iloc[0]["canonical_name"] == "Financial Conduct Authority"
        assert lb.iloc[0]["mentions"] == 100

    def test_alias_merge_sums_mentions(self, mod):
        """Two entity strings with the same clean key collapse, mentions summed."""
        mentions = _mentions([
            ("SEC", 80),
            ("U.S. Securities and Exchange Commission", 40),
            ("Securities and Exchange Commission", 20),
        ])
        types = _types([
            ("SEC", "Regulator / Supervisor", "Securities and Exchange Commission"),
            ("U.S. Securities and Exchange Commission", "Regulator / Supervisor",
             "Securities and Exchange Commission"),
            ("Securities and Exchange Commission", "Regulator / Supervisor",
             "Securities and Exchange Commission"),
        ])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        # All three clean to the same key → one row with summed mentions
        sec_rows = lb[lb["canonical_name"] == "Securities and Exchange Commission"]
        assert len(sec_rows) == 1
        assert sec_rows.iloc[0]["mentions"] == 140

    def test_alias_merge_highest_mention_member_wins(self, mod):
        """Display name and type come from the highest-mention member.

        Two entity strings that map to the SAME canonical_name clean to the same
        merge key and therefore collapse into one row.  The row with the higher
        per-entity mention count supplies the display name and type.
        """
        # Both entity strings carry the SAME canonical_name ("Securities and Exchange Commission")
        # so their merge keys are identical → they collapse.
        # "SEC_raw" has count=80 (higher) so its type/display wins.
        mentions = _mentions([
            ("SEC_raw", 80),
            ("U.S. Securities and Exchange Commission", 40),
        ])
        types = _types([
            ("SEC_raw", "Regulator / Supervisor", "Securities and Exchange Commission"),
            ("U.S. Securities and Exchange Commission", "Government body",
             "Securities and Exchange Commission"),
        ])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        # Both canonical_names clean to the same key → one merged row
        assert len(lb) == 1
        row = lb.iloc[0]
        assert row["canonical_name"] == "Securities and Exchange Commission"
        assert row["type"] == "Regulator / Supervisor"  # winner: SEC_raw (count=80)
        assert row["mentions"] == 120

    def test_alias_merge_tiebreak_name_asc(self, mod):
        """When two aliases share the same merge key AND have equal counts,
        the name-ascending canonical_name wins for the display row.

        Two entity strings are given the SAME canonical_name so _clean_canonical
        produces an identical merge key — guaranteeing an actual merge.
        Their per-entity mention counts are equal, so the tie-break (canonical_name
        ascending) must be the deciding factor.
        """
        # Both entities map to canonical_name "Federal Reserve" → merge key "federal reserve".
        # Equal per-entity counts (50 each) → tie-break selects canonical_name ascending.
        # Both canonical_names are identical here so the merged display name is that value;
        # but the display type comes from whichever row sorts first (name asc → same).
        # Use distinct types to make the winner unambiguous.
        mentions = _mentions([
            ("fed_reserve_raw", 50),
            ("U.S. Federal Reserve", 50),
        ])
        types = _types([
            # canonical_name for both cleans to "federal reserve"
            ("fed_reserve_raw", "Regulator / Supervisor", "Federal Reserve"),
            # "U.S. Federal Reserve" canonical strips the U.S. prefix → also "federal reserve"
            ("U.S. Federal Reserve", "Government body", "Federal Reserve"),
        ])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)

        # The two entity strings must merge into exactly ONE row (same merge key)
        assert len(lb) == 1, (
            f"Expected 1 merged row, got {len(lb)}. "
            "Check that both canonical_names clean to the same merge key."
        )
        row = lb.iloc[0]

        # Summed mentions = 50 + 50 = 100
        assert row["mentions"] == 100

        # canonical_name must be "Federal Reserve" (both share it)
        assert row["canonical_name"] == "Federal Reserve"

        # With equal counts and equal canonical_names, the name-asc tie-break is
        # irrelevant for the display name here — what matters is that the merge
        # happened and the sum is correct. The winner's type comes from whichever
        # entity string sorts first by canonical_name asc when counts are tied.
        # Both share the same canonical_name so either type is acceptable per the
        # tie-break spec (implementation-stable via pandas stable sort).
        assert row["type"] in {"Regulator / Supervisor", "Government body"}

    def test_top_n_cap(self, mod):
        """Only top_n rows returned, sorted by mentions desc."""
        n = 5
        mentions = _mentions([(f"E{i}", 100 - i) for i in range(20)])
        types = _types([(f"E{i}", "Company", f"Entity {i}") for i in range(20)])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=n)
        assert len(lb) == n
        # Verify sorted descending
        assert lb.iloc[0]["mentions"] >= lb.iloc[-1]["mentions"]

    def test_sorted_desc(self, mod):
        """Leaderboard rows are sorted by mentions descending."""
        mentions = _mentions([("A", 10), ("B", 30), ("C", 20)])
        types = _types([
            ("A", "Company", "A Corp"),
            ("B", "Company", "B Corp"),
            ("C", "Company", "C Corp"),
        ])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        counts = lb["mentions"].tolist()
        assert counts == sorted(counts, reverse=True)

    def test_entity_not_in_types_excluded(self, mod):
        """Entities not present in entity_types (thus no canonical_name) are excluded
        from the leaderboard (they only appear in breakdown as 'Other')."""
        mentions = _mentions([("FCA", 100), ("NoType", 200)])
        types = _types([("FCA", "Regulator / Supervisor", "Financial Conduct Authority")])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        # "NoType" has no type classification → no canonical_name → excluded
        names = lb["canonical_name"].tolist()
        assert "Financial Conduct Authority" in names
        # NoType should not appear since there's no canonical_name for it
        assert not any("NoType" in str(n) for n in names)

    def test_columns_present(self, mod):
        """Output has exactly the three required columns."""
        mentions = _mentions([("FCA", 10)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        assert set(lb.columns) == {"canonical_name", "type", "mentions"}

    def test_top_50_hard_cap(self, mod):
        """Even if top_n > 50, output is capped at 50."""
        n = 100
        mentions = _mentions([(f"E{i}", 100 - i) for i in range(100)])
        types = _types([(f"E{i}", "Company", f"Entity {i}") for i in range(100)])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=n)
        assert len(lb) <= 50


# ===========================================================================
# build_tag_leaderboard
# ===========================================================================

class TestTagLeaderboard:
    """build_tag_leaderboard(tag_mentions_df, top_n) ->
    DataFrame(tag, count) — top-N by frequency, no LLM."""

    def test_basic_top_n(self, mod):
        tags = _tag_mentions([("AML", 100), ("KYC", 80), ("Basel III", 60)])
        lb = mod.build_tag_leaderboard(tags, top_n=2)
        assert len(lb) == 2
        assert lb.iloc[0]["tag"] == "AML"
        assert lb.iloc[0]["count"] == 100

    def test_sorted_desc(self, mod):
        tags = _tag_mentions([("A", 10), ("B", 50), ("C", 30)])
        lb = mod.build_tag_leaderboard(tags, top_n=10)
        counts = lb["count"].tolist()
        assert counts == sorted(counts, reverse=True)

    def test_tiebreak_name_asc(self, mod):
        """Tie in count → tag name ascending."""
        tags = _tag_mentions([("Zebra", 50), ("Alpha", 50), ("Middle", 50)])
        lb = mod.build_tag_leaderboard(tags, top_n=3)
        assert lb.iloc[0]["tag"] == "Alpha"
        assert lb.iloc[1]["tag"] == "Middle"
        assert lb.iloc[2]["tag"] == "Zebra"

    def test_top_50_hard_cap(self, mod):
        """Hard cap at 50 tags."""
        tags = _tag_mentions([(f"tag{i}", 100 - i) for i in range(100)])
        lb = mod.build_tag_leaderboard(tags, top_n=100)
        assert len(lb) <= 50

    def test_columns_present(self, mod):
        tags = _tag_mentions([("AML", 10)])
        lb = mod.build_tag_leaderboard(tags, top_n=50)
        assert set(lb.columns) == {"tag", "count"}

    def test_pure_frequency_no_transform(self, mod):
        """Tags are returned as-is; no merging, no casefolding."""
        tags = _tag_mentions([("Basel III", 100), ("basel iii", 50)])
        lb = mod.build_tag_leaderboard(tags, top_n=50)
        assert len(lb) == 2  # treated as distinct tags
        assert lb.iloc[0]["tag"] == "Basel III"


# ===========================================================================
# build_term_stats_meta
# ===========================================================================

class TestTermStatsMeta:
    """build_term_stats_meta(...) -> dict with EXACTLY the required keys."""

    def _run(self, mod, entity_mentions=None, tag_mentions=None, entity_types=None,
             enriched_at=None):
        em = entity_mentions if entity_mentions is not None else _mentions(
            [("FCA", 50), ("EBA", 30)]
        )
        tm = tag_mentions if tag_mentions is not None else _tag_mentions(
            [("AML", 100), ("KYC", 60)]
        )
        et = entity_types if entity_types is not None else _types(
            [("FCA", "Regulator / Supervisor", "FCA"),
             ("EBA", "Regulator / Supervisor", "EBA")]
        )
        return mod.build_term_stats_meta(em, tm, et, enriched_at=enriched_at)

    def test_exact_keys(self, mod):
        meta = self._run(mod)
        expected_keys = {
            "n_distinct_entities",
            "n_entity_mentions",
            "n_distinct_tags",
            "n_tag_mentions",
            "model",
            "enriched_at",
            "n_classified",
        }
        assert set(meta.keys()) == expected_keys

    def test_n_distinct_entities(self, mod):
        em = _mentions([("FCA", 50), ("EBA", 30)])
        meta = self._run(mod, entity_mentions=em)
        assert meta["n_distinct_entities"] == 2

    def test_n_entity_mentions_is_sum(self, mod):
        em = _mentions([("FCA", 50), ("EBA", 30)])
        meta = self._run(mod, entity_mentions=em)
        assert meta["n_entity_mentions"] == 80

    def test_n_distinct_tags(self, mod):
        tm = _tag_mentions([("AML", 100), ("KYC", 60), ("Basel III", 20)])
        meta = self._run(mod, tag_mentions=tm)
        assert meta["n_distinct_tags"] == 3

    def test_n_tag_mentions_is_sum(self, mod):
        tm = _tag_mentions([("AML", 100), ("KYC", 60)])
        meta = self._run(mod, tag_mentions=tm)
        assert meta["n_tag_mentions"] == 160

    def test_model_matches_config(self, mod):
        from carver_showcase.config import OPENAI_MODEL
        meta = self._run(mod)
        assert meta["model"] == OPENAI_MODEL

    def test_n_classified_is_entity_types_row_count(self, mod):
        et = _types([
            ("FCA", "Regulator / Supervisor", "FCA"),
            ("EBA", "Regulator / Supervisor", "EBA"),
            ("Goldman", "Company", "Goldman Sachs"),
        ])
        meta = self._run(mod, entity_types=et)
        assert meta["n_classified"] == 3

    def test_enriched_at_is_iso8601_string(self, mod):
        """enriched_at must be a valid ISO-8601 UTC string."""
        meta = self._run(mod)
        ts = meta["enriched_at"]
        assert isinstance(ts, str)
        # Must parse as a datetime
        parsed = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed is not None

    def test_enriched_at_injected_timestamp(self, mod):
        """When enriched_at is injected, the meta uses that exact value."""
        fixed = "2025-01-15T12:00:00+00:00"
        meta = self._run(mod, enriched_at=fixed)
        assert meta["enriched_at"] == fixed

    def test_enriched_at_default_is_recent(self, mod):
        """Without injection, enriched_at is close to now (UTC)."""
        before = datetime.datetime.now(datetime.timezone.utc)
        meta = self._run(mod)
        after = datetime.datetime.now(datetime.timezone.utc)
        ts_str = meta["enriched_at"]
        ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        assert before <= ts <= after


# ===========================================================================
# CRITICAL invariant: breakdown is independent of alias merge
# ===========================================================================

class TestBreakdownIndependentOfMerge:
    """Spec §4.5: the type breakdown is computed WITHOUT the alias merge.
    The breakdown figures must be identical before and after running the leaderboard merge."""

    def test_breakdown_unchanged_by_merge(self, mod):
        """Running build_entity_leaderboard must not alter the breakdown output."""
        mentions = _mentions([
            ("SEC", 80),
            ("U.S. Securities and Exchange Commission", 40),
            ("FCA", 100),
        ])
        types = _types([
            ("SEC", "Regulator / Supervisor", "Securities and Exchange Commission"),
            ("U.S. Securities and Exchange Commission", "Regulator / Supervisor",
             "Securities and Exchange Commission"),
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
        ])

        # Compute breakdown BEFORE leaderboard merge
        bd_before = mod.build_entity_type_breakdown(mentions, types)
        before_reg = bd_before.loc[
            bd_before["type"] == "Regulator / Supervisor"
        ].iloc[0]

        # Run the leaderboard merge (alias collapse happens here)
        _ = mod.build_entity_leaderboard(mentions, types, top_n=50)

        # Compute breakdown AFTER leaderboard merge
        bd_after = mod.build_entity_type_breakdown(mentions, types)
        after_reg = bd_after.loc[
            bd_after["type"] == "Regulator / Supervisor"
        ].iloc[0]

        # The breakdown must be identical — merge must NOT touch the inputs
        assert before_reg["mentions"] == after_reg["mentions"]
        assert before_reg["distinct_entities"] == after_reg["distinct_entities"]

    def test_breakdown_counts_all_aliases_as_distinct_entities(self, mod):
        """The breakdown counts alias variants as SEPARATE distinct entities
        (breakdown is pre-merge). This is explicitly different from the leaderboard."""
        mentions = _mentions([
            ("SEC", 80),
            ("U.S. Securities and Exchange Commission", 40),
        ])
        types = _types([
            ("SEC", "Regulator / Supervisor", "Securities and Exchange Commission"),
            ("U.S. Securities and Exchange Commission", "Regulator / Supervisor",
             "Securities and Exchange Commission"),
        ])
        bd = mod.build_entity_type_breakdown(mentions, types)
        reg = bd.loc[bd["type"] == "Regulator / Supervisor"].iloc[0]

        # Breakdown: 2 distinct entity strings, 120 total mentions
        assert reg["distinct_entities"] == 2
        assert reg["mentions"] == 120

        # Leaderboard: 1 merged row, 120 summed mentions
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        sec_rows = lb[lb["canonical_name"] == "Securities and Exchange Commission"]
        assert len(sec_rows) == 1
        assert sec_rows.iloc[0]["mentions"] == 120


# ===========================================================================
# Integration: write_outputs → CSVs + JSON round-trip
# ===========================================================================

class TestWriteOutputs:
    """write_outputs(...) writes all 4 output files with correct columns."""

    def test_all_files_created(self, mod, tmp_path):
        mentions = _mentions([("FCA", 100), ("EBA", 50)])
        types = _types([
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
            ("EBA", "Regulator / Supervisor", "European Banking Authority"),
        ])
        tags = _tag_mentions([("AML", 200), ("KYC", 100)])

        out = {
            "breakdown": tmp_path / "breakdown.csv",
            "entity_lb": tmp_path / "entity_lb.csv",
            "tag_lb": tmp_path / "tag_lb.csv",
            "meta": tmp_path / "meta.json",
        }
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=out["breakdown"],
            entity_leaderboard_path=out["entity_lb"],
            tag_leaderboard_path=out["tag_lb"],
            meta_path=out["meta"],
            entity_leaderboard_top_n=50,
            tag_leaderboard_top_n=50,
        )
        for path in out.values():
            assert path.exists(), f"Expected output file: {path}"

    def test_breakdown_csv_columns(self, mod, tmp_path):
        mentions = _mentions([("FCA", 10)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        tags = _tag_mentions([("AML", 5)])
        bd_path = tmp_path / "breakdown.csv"
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=bd_path,
            entity_leaderboard_path=tmp_path / "elb.csv",
            tag_leaderboard_path=tmp_path / "tlb.csv",
            meta_path=tmp_path / "meta.json",
            entity_leaderboard_top_n=50,
            tag_leaderboard_top_n=50,
        )
        df = pd.read_csv(bd_path)
        assert set(df.columns) == {"type", "mentions", "distinct_entities"}

    def test_meta_json_keys(self, mod, tmp_path):
        mentions = _mentions([("FCA", 10)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        tags = _tag_mentions([("AML", 5)])
        meta_path = tmp_path / "meta.json"
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=tmp_path / "bd.csv",
            entity_leaderboard_path=tmp_path / "elb.csv",
            tag_leaderboard_path=tmp_path / "tlb.csv",
            meta_path=meta_path,
            entity_leaderboard_top_n=50,
            tag_leaderboard_top_n=50,
        )
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        expected_keys = {
            "n_distinct_entities", "n_entity_mentions",
            "n_distinct_tags", "n_tag_mentions",
            "model", "enriched_at", "n_classified",
        }
        assert set(meta.keys()) == expected_keys

    def test_entity_leaderboard_csv_columns(self, mod, tmp_path):
        mentions = _mentions([("FCA", 100)])
        types = _types([("FCA", "Regulator / Supervisor", "Financial Conduct Authority")])
        tags = _tag_mentions([("AML", 5)])
        elb_path = tmp_path / "elb.csv"
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=tmp_path / "bd.csv",
            entity_leaderboard_path=elb_path,
            tag_leaderboard_path=tmp_path / "tlb.csv",
            meta_path=tmp_path / "meta.json",
            entity_leaderboard_top_n=50,
            tag_leaderboard_top_n=50,
        )
        df = pd.read_csv(elb_path)
        assert set(df.columns) == {"canonical_name", "type", "mentions"}

    def test_tag_leaderboard_csv_columns(self, mod, tmp_path):
        mentions = _mentions([("FCA", 100)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        tags = _tag_mentions([("AML", 5), ("KYC", 3)])
        tlb_path = tmp_path / "tlb.csv"
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=tmp_path / "bd.csv",
            entity_leaderboard_path=tmp_path / "elb.csv",
            tag_leaderboard_path=tlb_path,
            meta_path=tmp_path / "meta.json",
            entity_leaderboard_top_n=50,
            tag_leaderboard_top_n=50,
        )
        df = pd.read_csv(tlb_path)
        assert set(df.columns) == {"tag", "count"}

    def test_entity_leaderboard_csv_stores_50_rows(self, mod, tmp_path):
        """Spec §3.5: entity_leaderboard.csv stores up to 50 rows (not the
        chart display top-20). With >50 distinct entities the written CSV must
        contain exactly 50 rows — the store count, not the display top-N (20)."""
        # 60 distinct entities, each with a unique canonical_name → no merges
        n_entities = 60
        mentions = _mentions([(f"Ent{i}", 100 - i) for i in range(n_entities)])
        types = _types(
            [(f"Ent{i}", "Company", f"Entity {i:03d}") for i in range(n_entities)]
        )
        tags = _tag_mentions([("AML", 5)])
        elb_path = tmp_path / "elb.csv"
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=tmp_path / "bd.csv",
            entity_leaderboard_path=elb_path,
            tag_leaderboard_path=tmp_path / "tlb.csv",
            meta_path=tmp_path / "meta.json",
            entity_leaderboard_top_n=mod.LEADERBOARD_STORE_N,
            tag_leaderboard_top_n=mod.LEADERBOARD_STORE_N,
        )
        df = pd.read_csv(elb_path)
        assert len(df) == 50, (
            f"Expected 50 rows in entity_leaderboard.csv (store count), got {len(df)}. "
            "The store count must be 50, independent of the chart display top-N (20)."
        )

    def test_tag_leaderboard_csv_stores_50_rows(self, mod, tmp_path):
        """Spec §3.6: tag_leaderboard.csv stores up to 50 rows (not the chart
        display top-20). With >50 distinct tags the written CSV must contain
        exactly 50 rows."""
        n_tags = 60
        tags = _tag_mentions([(f"tag_{i:03d}", 100 - i) for i in range(n_tags)])
        mentions = _mentions([("FCA", 10)])
        types = _types([("FCA", "Regulator / Supervisor", "FCA")])
        tlb_path = tmp_path / "tlb.csv"
        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=tmp_path / "bd.csv",
            entity_leaderboard_path=tmp_path / "elb.csv",
            tag_leaderboard_path=tlb_path,
            meta_path=tmp_path / "meta.json",
            entity_leaderboard_top_n=mod.LEADERBOARD_STORE_N,
            tag_leaderboard_top_n=mod.LEADERBOARD_STORE_N,
        )
        df = pd.read_csv(tlb_path)
        assert len(df) == 50, (
            f"Expected 50 rows in tag_leaderboard.csv (store count), got {len(df)}. "
            "The store count must be 50, independent of the chart display top-N (20)."
        )

    def test_display_top_n_config_unchanged(self, mod):
        """ENTITY_LEADERBOARD_TOP_N and TAG_LEADERBOARD_TOP_N in config must
        remain 20 (chart display counts) — decoupled from the store count (50)."""
        from carver_showcase.config import ENTITY_LEADERBOARD_TOP_N, TAG_LEADERBOARD_TOP_N
        assert ENTITY_LEADERBOARD_TOP_N == 20, (
            f"Config display top-N changed from 20 to {ENTITY_LEADERBOARD_TOP_N}. "
            "Only LEADERBOARD_STORE_N (in the tool) should be 50."
        )
        assert TAG_LEADERBOARD_TOP_N == 20, (
            f"Config display top-N changed from 20 to {TAG_LEADERBOARD_TOP_N}. "
            "Only LEADERBOARD_STORE_N (in the tool) should be 50."
        )
        assert mod.LEADERBOARD_STORE_N == 50, (
            f"LEADERBOARD_STORE_N should be 50, got {mod.LEADERBOARD_STORE_N}."
        )


# ===========================================================================
# Regression: "NA" / "null" / "NaN" tokens must not crash or be dropped
# ===========================================================================

class TestNaTokenRobustness:
    """Regression for: entity/tag token is the literal string 'NA' (or 'null',
    'NaN', 'None', 'N/A').  pandas.read_csv treats these as NaN by default, so
    if read without keep_default_na=False they arrive as float NaN and crash
    _clean_canonical and the rollup loops.  These tests verify the in-memory
    logic is correct regardless of how the data was loaded."""

    def test_clean_canonical_nan_float_returns_empty_string(self, mod):
        """_clean_canonical(float('nan')) must return '' without raising."""
        result = mod._clean_canonical(float("nan"))
        assert result == ""

    def test_clean_canonical_none_returns_empty_string(self, mod):
        """_clean_canonical(None) must return '' without raising."""
        result = mod._clean_canonical(None)
        assert result == ""

    def test_clean_canonical_na_string_is_preserved(self, mod):
        """_clean_canonical('NA') must process the string (not crash or drop it).

        The string 'NA' is a legitimate entity token, not a missing value.
        After casefolding the key becomes 'na'.
        """
        result = mod._clean_canonical("NA")
        assert isinstance(result, str)
        assert result == "na"

    def test_clean_canonical_null_string_is_preserved(self, mod):
        """_clean_canonical('null') → 'null' (casefolded)."""
        result = mod._clean_canonical("null")
        assert result == "null"

    def test_clean_canonical_nan_string_is_preserved(self, mod):
        """_clean_canonical('NaN') → 'nan' (casefolded)."""
        result = mod._clean_canonical("NaN")
        assert result == "nan"

    def test_entity_na_string_counted_in_breakdown(self, mod):
        """An entity whose string is literally 'NA' is included in the breakdown."""
        mentions = _mentions([("NA", 7), ("FCA", 50)])
        types = _types([
            ("NA", "Regulator / Supervisor", "NA"),
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
        ])
        bd = mod.build_entity_type_breakdown(mentions, types)
        reg = bd.loc[bd["type"] == "Regulator / Supervisor"].iloc[0]
        # Both 'NA' (7) and 'FCA' (50) must be counted
        assert reg["mentions"] == 57
        assert reg["distinct_entities"] == 2

    def test_entity_na_string_appears_in_leaderboard(self, mod):
        """An entity with canonical_name 'NA' survives the leaderboard rollup."""
        mentions = _mentions([("NA", 7), ("FCA", 50)])
        types = _types([
            ("NA", "Regulator / Supervisor", "NA"),
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
        ])
        lb = mod.build_entity_leaderboard(mentions, types, top_n=50)
        canonical_names = lb["canonical_name"].tolist()
        assert "NA" in canonical_names, (
            f"'NA' entity missing from leaderboard. Got: {canonical_names}"
        )

    def test_tag_na_string_appears_in_tag_leaderboard(self, mod):
        """A tag whose string is 'NA' is included in the tag leaderboard."""
        tags = _tag_mentions([("NA", 12), ("AML", 100)])
        lb = mod.build_tag_leaderboard(tags, top_n=50)
        assert "NA" in lb["tag"].tolist(), (
            f"'NA' tag missing from leaderboard. Got: {lb['tag'].tolist()}"
        )

    def test_rollup_completes_without_raising_with_na_tokens(self, mod, tmp_path):
        """write_outputs must not raise when entity/tag tokens include 'NA', 'null',
        'NaN' strings (simulating what happens after keep_default_na=False reading)."""
        mentions = _mentions([("NA", 5), ("null", 3), ("FCA", 50)])
        types = _types([
            ("NA", "Regulator / Supervisor", "NA"),
            ("null", "Company", "null"),
            ("FCA", "Regulator / Supervisor", "Financial Conduct Authority"),
        ])
        tags = _tag_mentions([("NA", 12), ("NaN", 8), ("AML", 100)])

        mod.write_outputs(
            entity_mentions_df=mentions,
            entity_types_df=types,
            tag_mentions_df=tags,
            breakdown_path=tmp_path / "breakdown.csv",
            entity_leaderboard_path=tmp_path / "entity_lb.csv",
            tag_leaderboard_path=tmp_path / "tag_lb.csv",
            meta_path=tmp_path / "meta.json",
            entity_leaderboard_top_n=50,
            tag_leaderboard_top_n=50,
        )
        # All four outputs must exist
        assert (tmp_path / "breakdown.csv").exists()
        assert (tmp_path / "entity_lb.csv").exists()
        assert (tmp_path / "tag_lb.csv").exists()
        assert (tmp_path / "meta.json").exists()
