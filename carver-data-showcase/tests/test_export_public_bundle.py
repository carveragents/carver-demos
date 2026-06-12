"""Tests for tools/export_public_bundle.py — public bundle export (Task 4).

Covers:
  - slim_frame: keeps exactly PUBLIC_KEEP_COLUMNS in order, drops content columns,
    preserves row count.
  - slim_frame: raises ValueError naming missing keep columns when upstream schema
    is missing a required column.
  - copy_sidecars: returns correct (copied, missing) split; files land in out_dir.
  - build_public_bundle end-to-end: writes slim parquet (15 cols), copies sidecars,
    returns a sane summary dict.
  - None of PUBLIC_CONTENT_DENYLIST columns appear in the written slim parquet.
"""
from __future__ import annotations

import pathlib
import shutil

import pandas as pd
import pytest

from carver_showcase.config import (
    GALLERY_UPDATE_TYPE_DENYLIST,
    PUBLIC_CONTENT_DENYLIST,
    PUBLIC_KEEP_COLUMNS,
)


# ---------------------------------------------------------------------------
# Helpers for building fixture DataFrames
# ---------------------------------------------------------------------------

_KEEP_COLS = list(PUBLIC_KEEP_COLUMNS)

# Content-only columns that are NOT in PUBLIC_KEEP_COLUMNS and should be dropped.
_CONTENT_COLS = ["title", "regulator_name", "artifact_id"]


def _make_keep_df(n_rows: int = 5) -> pd.DataFrame:
    """Build a DataFrame containing exactly the 15 keep columns with dummy data."""
    data = {col: [f"{col}_{i}" for i in range(n_rows)] for col in _KEEP_COLS}
    return pd.DataFrame(data)


def _make_full_df(n_rows: int = 5) -> pd.DataFrame:
    """Build a DataFrame with the 15 keep columns PLUS extra content columns."""
    df = _make_keep_df(n_rows)
    for col in _CONTENT_COLS:
        df[col] = [f"{col}_{i}" for i in range(n_rows)]
    return df


# ---------------------------------------------------------------------------
# Import under test (deferred so test collection succeeds even if module absent)
# ---------------------------------------------------------------------------

def _import_module():
    import importlib
    import sys
    # Ensure the repo root is on sys.path
    root = pathlib.Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return importlib.import_module("tools.export_public_bundle")


# ---------------------------------------------------------------------------
# Tests: slim_frame
# ---------------------------------------------------------------------------

class TestSlimFrame:
    """slim_frame is a pure helper that selects PUBLIC_KEEP_COLUMNS."""

    def test_returns_exactly_keep_columns_in_order(self):
        """slim_frame returns exactly the 15 keep columns in order."""
        mod = _import_module()
        df = _make_full_df(10)

        slim = mod.slim_frame(df)

        assert list(slim.columns) == _KEEP_COLS

    def test_content_columns_are_dropped(self):
        """Content columns (title, regulator_name, artifact_id) are not in the result."""
        mod = _import_module()
        df = _make_full_df(10)

        slim = mod.slim_frame(df)

        for col in _CONTENT_COLS:
            assert col not in slim.columns, f"Content column {col!r} must not appear in slim frame"

    def test_row_count_preserved(self):
        """Row count is identical before and after slimming."""
        mod = _import_module()
        n = 7
        df = _make_full_df(n)

        slim = mod.slim_frame(df)

        assert len(slim) == n

    def test_raises_value_error_when_keep_column_missing(self):
        """slim_frame raises ValueError naming the missing column when schema changed."""
        mod = _import_module()

        # Build a df that has all keep cols EXCEPT "richness_score"
        df = _make_full_df(3)
        df = df.drop(columns=["richness_score"])

        with pytest.raises(ValueError, match="richness_score"):
            mod.slim_frame(df)

    def test_raises_value_error_lists_all_missing_columns(self):
        """ValueError message lists ALL missing columns, not just the first."""
        mod = _import_module()

        # Drop two keep columns
        df = _make_full_df(3)
        df = df.drop(columns=["richness_score", "n_tags"])

        with pytest.raises(ValueError) as exc_info:
            mod.slim_frame(df)

        msg = str(exc_info.value)
        assert "richness_score" in msg
        assert "n_tags" in msg

    def test_exact_keep_columns_no_extras_no_content(self):
        """When df has exactly the keep columns, slim_frame returns them unchanged."""
        mod = _import_module()
        df = _make_keep_df(4)

        slim = mod.slim_frame(df)

        assert list(slim.columns) == _KEEP_COLS
        assert len(slim) == 4


# ---------------------------------------------------------------------------
# Tests: copy_sidecars
# ---------------------------------------------------------------------------

class TestCopySidecars:
    """copy_sidecars copies present sidecars and reports missing ones leniently."""

    def _make_src_sidecars(self, tmp_path: pathlib.Path, names: list[str]) -> list[pathlib.Path]:
        """Create dummy sidecar files in a src subdir and return their Paths."""
        src = tmp_path / "src"
        src.mkdir()
        paths = []
        for name in names:
            p = src / name
            p.write_text(f"dummy {name}")
            paths.append(p)
        return paths

    def test_copies_present_files_into_out_dir(self, tmp_path: pathlib.Path):
        """Files that exist on disk are copied into out_dir."""
        mod = _import_module()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        sidecars = self._make_src_sidecars(tmp_path, ["a.csv", "b.json"])

        copied, missing = mod.copy_sidecars(sidecars, out_dir)

        assert "a.csv" in copied
        assert "b.json" in copied
        assert (out_dir / "a.csv").exists()
        assert (out_dir / "b.json").exists()

    def test_missing_files_reported_not_raised(self, tmp_path: pathlib.Path):
        """Non-existent sidecars are reported in 'missing' list, not raised."""
        mod = _import_module()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        present = self._make_src_sidecars(tmp_path, ["real.csv"])
        ghost = tmp_path / "src" / "ghost.pdf"  # does not exist

        sidecars = present + [ghost]

        copied, missing = mod.copy_sidecars(sidecars, out_dir)

        assert "real.csv" in copied
        assert "ghost.pdf" in missing
        assert len(copied) == 1
        assert len(missing) == 1

    def test_correct_split_some_present_some_missing(self, tmp_path: pathlib.Path):
        """copy_sidecars correctly partitions present vs missing."""
        mod = _import_module()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        present = self._make_src_sidecars(tmp_path, ["x.csv", "y.json"])
        ghosts = [tmp_path / "src" / "ghost1.csv", tmp_path / "src" / "ghost2.pdf"]

        sidecars = present + ghosts

        copied, missing = mod.copy_sidecars(sidecars, out_dir)

        assert set(copied) == {"x.csv", "y.json"}
        assert set(missing) == {"ghost1.csv", "ghost2.pdf"}

    def test_all_missing_returns_empty_copied(self, tmp_path: pathlib.Path):
        """When no sidecar exists, copied is empty and missing has all."""
        mod = _import_module()
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        ghosts = [tmp_path / "g1.csv", tmp_path / "g2.json"]
        copied, missing = mod.copy_sidecars(ghosts, out_dir)

        assert copied == []
        assert set(missing) == {"g1.csv", "g2.json"}


# ---------------------------------------------------------------------------
# Tests: build_public_bundle (end-to-end)
# ---------------------------------------------------------------------------

class TestBuildPublicBundle:
    """build_public_bundle end-to-end: writes slim parquet, copies sidecars,
    returns a sane summary dict."""

    def _write_normalized_parquet(self, path: pathlib.Path, n_rows: int = 8) -> pathlib.Path:
        """Write a tiny normalized-shaped parquet (keep cols + content cols) at path."""
        df = _make_full_df(n_rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, engine="pyarrow", index=False)
        return path

    def _make_sidecars(self, tmp_path: pathlib.Path, names: list[str]) -> list[pathlib.Path]:
        """Create dummy sidecar files and return their Paths."""
        src = tmp_path / "sidecars"
        src.mkdir(exist_ok=True)
        paths = []
        for name in names:
            p = src / name
            p.write_text(f"dummy {name}")
            paths.append(p)
        return paths

    def test_writes_slim_parquet_with_only_keep_columns(self, tmp_path: pathlib.Path):
        """build_public_bundle writes annotations.parquet with exactly 15 keep cols."""
        mod = _import_module()

        src_parquet = tmp_path / "src" / "annotations.parquet"
        self._write_normalized_parquet(src_parquet)

        out_dir = tmp_path / "public"
        sidecars = self._make_sidecars(tmp_path, ["topic_catalog.csv", "snapshot_meta.json"])

        mod.build_public_bundle(src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars)

        written = pd.read_parquet(out_dir / "annotations.parquet")
        assert list(written.columns) == _KEEP_COLS

    def test_written_parquet_row_count_preserved_when_no_noise(self, tmp_path: pathlib.Path):
        """When the source has no noise update_types, row count is preserved."""
        mod = _import_module()

        n = 8
        src_parquet = tmp_path / "src" / "annotations.parquet"
        self._write_normalized_parquet(src_parquet, n_rows=n)

        out_dir = tmp_path / "public"
        sidecars = self._make_sidecars(tmp_path, ["topic_catalog.csv"])

        summary = mod.build_public_bundle(
            src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars
        )

        written = pd.read_parquet(out_dir / "annotations.parquet")
        # No noise rows → curated == full
        assert len(written) == n
        assert summary["curated_rows"] == summary["full_rows"]

    def test_sidecars_are_copied_into_out_dir(self, tmp_path: pathlib.Path):
        """Present sidecars are copied into out_dir by their basename."""
        mod = _import_module()

        src_parquet = tmp_path / "src" / "annotations.parquet"
        self._write_normalized_parquet(src_parquet)

        out_dir = tmp_path / "public"
        sidecars = self._make_sidecars(tmp_path, ["topic_catalog.csv", "entity_leaderboard.csv"])

        mod.build_public_bundle(src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars)

        assert (out_dir / "topic_catalog.csv").exists()
        assert (out_dir / "entity_leaderboard.csv").exists()

    def test_returns_sane_summary_dict(self, tmp_path: pathlib.Path):
        """build_public_bundle returns a dict with expected keys and sane values."""
        mod = _import_module()

        n = 5
        src_parquet = tmp_path / "src" / "annotations.parquet"
        self._write_normalized_parquet(src_parquet, n_rows=n)

        out_dir = tmp_path / "public"
        sidecars = self._make_sidecars(tmp_path, ["topic_catalog.csv", "snapshot_meta.json"])

        summary = mod.build_public_bundle(
            src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars
        )

        assert summary["rows"] == n
        assert summary["columns"] == len(_KEEP_COLS)
        assert summary["out_dir"] == out_dir
        assert "full_rows" in summary
        assert "curated_rows" in summary
        assert "sidecars_copied" in summary
        assert "sidecars_missing" in summary
        assert isinstance(summary["sidecars_copied"], list)
        assert isinstance(summary["sidecars_missing"], list)

    def test_curation_drops_noise_rows(self, tmp_path: pathlib.Path):
        """build_public_bundle ships the curated frame: noise update_types are absent and
        curated_rows < full_rows when the source contains noise rows."""
        mod = _import_module()

        # Build a source parquet with some denylist update_types injected
        n_clean = 8
        df_clean = _make_full_df(n_clean)
        # Add rows whose update_type is in the denylist — they should be dropped
        noise_update_type = next(iter(GALLERY_UPDATE_TYPE_DENYLIST))
        df_noise = _make_full_df(3)
        df_noise["update_type"] = noise_update_type
        df_source = pd.concat([df_clean, df_noise], ignore_index=True)

        src_parquet = tmp_path / "src" / "annotations.parquet"
        src_parquet.parent.mkdir(parents=True, exist_ok=True)
        df_source.to_parquet(src_parquet, engine="pyarrow", index=False)

        out_dir = tmp_path / "public"
        sidecars = self._make_sidecars(tmp_path, ["topic_catalog.csv"])

        summary = mod.build_public_bundle(
            src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars
        )

        written = pd.read_parquet(out_dir / "annotations.parquet")
        # Curated row count must be less than the full row count
        assert summary["curated_rows"] < summary["full_rows"], (
            "curated_rows must be < full_rows when noise rows are present"
        )
        # The written parquet must not contain any denylist update_type values
        if "update_type" in written.columns:
            for deny_val in GALLERY_UPDATE_TYPE_DENYLIST:
                assert deny_val not in written["update_type"].values, (
                    f"Noise update_type {deny_val!r} must not appear in the public bundle"
                )

    def test_no_denylist_columns_in_written_parquet(self, tmp_path: pathlib.Path):
        """None of PUBLIC_CONTENT_DENYLIST columns appear in the written slim parquet."""
        mod = _import_module()

        src_parquet = tmp_path / "src" / "annotations.parquet"
        self._write_normalized_parquet(src_parquet)

        out_dir = tmp_path / "public"
        sidecars = self._make_sidecars(tmp_path, ["topic_catalog.csv"])

        mod.build_public_bundle(src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars)

        written = pd.read_parquet(out_dir / "annotations.parquet")
        leaked = set(written.columns) & PUBLIC_CONTENT_DENYLIST
        assert not leaked, f"Denylist columns leaked into public bundle: {leaked}"

    def test_missing_sidecars_reported_in_summary(self, tmp_path: pathlib.Path):
        """Sidecars that don't exist are reported in sidecars_missing without raising."""
        mod = _import_module()

        src_parquet = tmp_path / "src" / "annotations.parquet"
        self._write_normalized_parquet(src_parquet)

        out_dir = tmp_path / "public"
        present = self._make_sidecars(tmp_path, ["topic_catalog.csv"])
        ghost = tmp_path / "sidecars" / "nonexistent.pdf"  # does not exist
        sidecars = present + [ghost]

        summary = mod.build_public_bundle(
            src_parquet=src_parquet, out_dir=out_dir, sidecars=sidecars
        )

        assert "nonexistent.pdf" in summary["sidecars_missing"]
        assert "topic_catalog.csv" in summary["sidecars_copied"]
