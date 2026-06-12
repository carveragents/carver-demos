"""Tests for carver_showcase.curate.drop_noise_update_types (gallery/deck only)."""

import pandas as pd
import pytest

from carver_showcase.curate import drop_noise_update_types


@pytest.fixture()
def df() -> pd.DataFrame:
    """20 rows: two real types, two one-off rare types, a denylisted type, one null."""
    update_types = (
        ["press release"] * 10
        + ["guidance"] * 5
        + ["rare_one"]            # 1 → below a 10% share of 20 (cutoff 2)
        + ["rare_two"]            # 1 → below threshold
        + ["website error"] * 2   # 2 → above threshold, but denylisted
        + [pd.NA]                 # null → always kept
    )
    return pd.DataFrame(
        {
            "update_type": pd.array(update_types, dtype="string"),
            "other_col": range(len(update_types)),
        }
    )


def test_drops_rare_and_denylisted_keeps_real_and_null(df):
    out = drop_noise_update_types(df, min_share=0.1, denylist={"website error"})
    kept = set(out["update_type"].dropna())
    assert kept == {"press release", "guidance"}
    # rare one-offs gone (rule), website error gone (denylist)
    assert "rare_one" not in kept and "rare_two" not in kept
    assert "website error" not in kept
    # null update_type rows are kept (a missing value isn't a noisy value)
    assert int(out["update_type"].isna().sum()) == 1
    assert len(out) == 16  # 10 + 5 + 1 null


def test_pure_does_not_mutate_input(df):
    before = len(df)
    drop_noise_update_types(df, min_share=0.1, denylist={"website error"})
    assert len(df) == before


def test_idempotent(df):
    once = drop_noise_update_types(df, min_share=0.1, denylist={"website error"})
    twice = drop_noise_update_types(once, min_share=0.1, denylist={"website error"})
    assert len(once) == len(twice)


def test_denylist_is_case_insensitive(df):
    out = drop_noise_update_types(df, min_share=0.0, denylist={"WEBSITE ERROR"})
    assert "website error" not in set(out["update_type"].dropna())


def test_default_denylist_drops_named_crawl_junk():
    types = ["press release"] * 5 + ["website error"] * 5 + ["other (invalid document)"] * 5
    frame = pd.DataFrame({"update_type": pd.array(types, dtype="string")})
    out = drop_noise_update_types(frame)  # default min_share + denylist
    kept = set(out["update_type"].dropna())
    assert kept == {"press release"}


def test_min_share_zero_keeps_everything_but_denylist(df):
    # No denylist, min_share 0 → nothing is "below" 0, so all rows survive.
    out = drop_noise_update_types(df, min_share=0.0, denylist=frozenset())
    assert len(out) == len(df)


def test_empty_df_returns_empty():
    empty = pd.DataFrame({"update_type": pd.array([], dtype="string")})
    assert drop_noise_update_types(empty).empty


def test_missing_column_returns_unchanged():
    frame = pd.DataFrame({"x": [1, 2, 3]})
    out = drop_noise_update_types(frame)
    assert len(out) == 3
