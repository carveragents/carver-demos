"""Structural invariant tests for the public-deployment constants in carver_showcase/config.py.

Covers:
  - CARVER_DATA_DIR env override changes DATA_DIR and all derived paths.
  - PUBLIC_KEEP_COLUMNS: no duplicates; every member ∈ schema.NORMALIZED_COLUMNS.
  - PUBLIC_KEEP_COLUMNS ∩ PUBLIC_CONTENT_DENYLIST == ∅ (allowlist and denylist are disjoint).
  - Numeric constants are in valid ranges.

The config-reload test uses monkeypatch + importlib.reload to mutate and restore
module-level state.  The fixture always reloads back to defaults so the override
cannot bleed into other tests.
"""
from __future__ import annotations

import importlib

import carver_showcase.config as config
import carver_showcase.schema as schema


class TestDataDirOverride:
    """CARVER_DATA_DIR env var overrides DATA_DIR and all derived path constants."""

    def test_env_override_changes_data_dir(self, monkeypatch, tmp_path):
        """Setting CARVER_DATA_DIR re-roots DATA_DIR to the given path."""
        monkeypatch.setenv("CARVER_DATA_DIR", str(tmp_path))
        try:
            importlib.reload(config)
            assert config.DATA_DIR == tmp_path
        finally:
            monkeypatch.delenv("CARVER_DATA_DIR", raising=False)
            importlib.reload(config)

    def test_env_override_propagates_to_derived_paths(self, monkeypatch, tmp_path):
        """Derived path constants (e.g. ANNOTATIONS_PARQUET) sit under the override."""
        monkeypatch.setenv("CARVER_DATA_DIR", str(tmp_path))
        try:
            importlib.reload(config)
            assert str(config.ANNOTATIONS_PARQUET).startswith(str(tmp_path))
            assert str(config.TOPIC_CATALOG_CSV).startswith(str(tmp_path))
            assert str(config.SNAPSHOT_META_JSON).startswith(str(tmp_path))
        finally:
            monkeypatch.delenv("CARVER_DATA_DIR", raising=False)
            importlib.reload(config)

    def test_no_env_uses_repo_data_dir(self, monkeypatch):
        """Without the env var DATA_DIR resolves to the repo's data/ directory."""
        monkeypatch.delenv("CARVER_DATA_DIR", raising=False)
        try:
            importlib.reload(config)
            assert config.DATA_DIR.name == "data"
        finally:
            importlib.reload(config)


class TestPublicKeepColumns:
    """PUBLIC_KEEP_COLUMNS is a valid, non-redundant subset of NORMALIZED_COLUMNS."""

    def test_is_tuple(self):
        assert isinstance(config.PUBLIC_KEEP_COLUMNS, tuple)

    def test_no_duplicates(self):
        seen: set[str] = set()
        duplicates: list[str] = []
        for col in config.PUBLIC_KEEP_COLUMNS:
            if col in seen:
                duplicates.append(col)
            seen.add(col)
        assert not duplicates, f"Duplicate columns in PUBLIC_KEEP_COLUMNS: {duplicates}"

    def test_all_members_in_normalized_columns(self):
        """Every column in PUBLIC_KEEP_COLUMNS must exist in schema.NORMALIZED_COLUMNS."""
        normalized = set(schema.NORMALIZED_COLUMNS)
        unknown = [c for c in config.PUBLIC_KEEP_COLUMNS if c not in normalized]
        assert not unknown, (
            f"Columns in PUBLIC_KEEP_COLUMNS not found in schema.NORMALIZED_COLUMNS: {unknown}"
        )

    def test_expected_length(self):
        """PUBLIC_KEEP_COLUMNS contains exactly the expected number of columns."""
        assert len(config.PUBLIC_KEEP_COLUMNS) == 15, (
            f"Expected 15 columns, got {len(config.PUBLIC_KEEP_COLUMNS)}: "
            f"{list(config.PUBLIC_KEEP_COLUMNS)}"
        )

    def test_required_columns_present(self):
        """Spot-check that key columns from the spec are present."""
        keep = set(config.PUBLIC_KEEP_COLUMNS)
        required = {
            "topic_id",
            "impact_score", "impact_label", "impact_confidence",
            "urgency_score", "urgency_label", "urgency_confidence",
            "reconciled_published_date",
            "richness_score",
            "n_entities", "n_tags",
        }
        missing = required - keep
        assert not missing, f"Required columns missing from PUBLIC_KEEP_COLUMNS: {missing}"


class TestPublicContentDenylist:
    """PUBLIC_CONTENT_DENYLIST is a frozenset of forbidden column names."""

    def test_is_frozenset(self):
        assert isinstance(config.PUBLIC_CONTENT_DENYLIST, frozenset)

    def test_keep_and_denylist_are_disjoint(self):
        """PUBLIC_KEEP_COLUMNS and PUBLIC_CONTENT_DENYLIST must not share any names."""
        overlap = set(config.PUBLIC_KEEP_COLUMNS) & config.PUBLIC_CONTENT_DENYLIST
        assert not overlap, (
            f"PUBLIC_KEEP_COLUMNS and PUBLIC_CONTENT_DENYLIST overlap: {overlap}"
        )

    def test_denylist_contains_expected_names(self):
        """Spot-check that key forbidden names are in the denylist."""
        expected = {
            "title", "summary", "feed_url", "base_url",
            "jurisdiction_reasoning",
            "regulator_name", "regulator_division", "regulator_other_agency",
            "artifact_id", "entry_id", "source_id",
        }
        missing = expected - config.PUBLIC_CONTENT_DENYLIST
        assert not missing, (
            f"Expected names missing from PUBLIC_CONTENT_DENYLIST: {missing}"
        )

    def test_denylist_non_empty(self):
        assert len(config.PUBLIC_CONTENT_DENYLIST) > 0


class TestPublicNumericConstants:
    """Numeric and string public-deployment constants are in valid ranges."""

    def test_public_string_maxlen_positive(self):
        assert isinstance(config.PUBLIC_STRING_MAXLEN, int)
        assert config.PUBLIC_STRING_MAXLEN > 0

    def test_rowcount_drop_tolerance_in_range(self):
        assert isinstance(config.PUBLIC_ROWCOUNT_DROP_TOLERANCE, float)
        assert 0 < config.PUBLIC_ROWCOUNT_DROP_TOLERANCE < 1

    def test_upstream_record_tolerance_in_range(self):
        assert isinstance(config.UPSTREAM_RECORD_TOLERANCE, float)
        assert 0 < config.UPSTREAM_RECORD_TOLERANCE < 1

    def test_public_orphan_topic_tolerance_in_range(self):
        assert isinstance(config.PUBLIC_ORPHAN_TOPIC_TOLERANCE, float)
        assert 0 < config.PUBLIC_ORPHAN_TOPIC_TOLERANCE < 1

    def test_public_deck_min_bytes_positive(self):
        assert isinstance(config.PUBLIC_DECK_MIN_BYTES, int)
        assert config.PUBLIC_DECK_MIN_BYTES > 0

    def test_upstream_freshness_max_age_days_positive(self):
        assert isinstance(config.UPSTREAM_FRESHNESS_MAX_AGE_DAYS, int)
        assert config.UPSTREAM_FRESHNESS_MAX_AGE_DAYS > 0

    def test_public_data_subdir_non_empty_string(self):
        assert isinstance(config.PUBLIC_DATA_SUBDIR, str)
        assert config.PUBLIC_DATA_SUBDIR
