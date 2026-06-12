"""Tests for carver_showcase.config term stats and enrichment constants."""

import pathlib

import pytest

from carver_showcase import config


def test_entity_types_exact_tuple():
    """ENTITY_TYPES is a 6-tuple with exact order and spelling."""
    assert config.ENTITY_TYPES == (
        "Regulator / Supervisor",
        "Government body",
        "International body",
        "Company",
        "Person",
        "Other",
    )
    assert isinstance(config.ENTITY_TYPES, tuple)
    assert len(config.ENTITY_TYPES) == 6


def test_entity_type_definitions_has_all_keys():
    """ENTITY_TYPE_DEFINITIONS has a key for every ENTITY_TYPES bucket."""
    assert isinstance(config.ENTITY_TYPE_DEFINITIONS, dict)
    assert set(config.ENTITY_TYPE_DEFINITIONS.keys()) == set(config.ENTITY_TYPES)
    # Each definition is a non-empty string
    for entity_type, definition in config.ENTITY_TYPE_DEFINITIONS.items():
        assert isinstance(definition, str)
        assert len(definition) > 0


def test_entity_type_definitions_exact_values():
    """ENTITY_TYPE_DEFINITIONS has exact one-line definitions."""
    expected = {
        "Regulator / Supervisor": "A body that regulates or supervises a sector, including central banks.",
        "Government body": "A government organ that is not primarily a financial supervisor: ministries, executive departments, legislatures, courts, law-enforcement.",
        "International body": "Intergovernmental and standard-setting organisations.",
        "Company": "A commercial firm or private-sector organisation.",
        "Person": "A named individual (official, executive, etc.).",
        "Other": "Places, and anything genuinely unclassifiable.",
    }
    assert config.ENTITY_TYPE_DEFINITIONS == expected


def test_entity_type_colors_has_all_keys():
    """ENTITY_TYPE_COLORS has a hex colour for every ENTITY_TYPES bucket."""
    assert isinstance(config.ENTITY_TYPE_COLORS, dict)
    assert set(config.ENTITY_TYPE_COLORS.keys()) == set(config.ENTITY_TYPES)
    # Each value is a valid hex colour string
    for entity_type, color in config.ENTITY_TYPE_COLORS.items():
        assert isinstance(color, str)
        assert color.startswith("#")
        assert len(color) == 7  # #RRGGBB


def test_path_constants_are_pathlib_paths():
    """All path constants are pathlib.Path instances under DATA_DIR."""
    paths = [
        config.ENTITY_MENTIONS_CSV,
        config.TAG_MENTIONS_CSV,
        config.ENTITY_TYPES_CSV,
        config.ENTITY_TYPE_BREAKDOWN_CSV,
        config.ENTITY_LEADERBOARD_CSV,
        config.TAG_LEADERBOARD_CSV,
        config.TERM_STATS_META_JSON,
        config.ENTITY_BATCH_REQUESTS_JSONL,
        config.ENTITY_BATCH_OUTPUT_JSONL,
        config.ENTITY_BATCH_STATE_JSON,
    ]
    for path in paths:
        assert isinstance(path, pathlib.Path)
        # Check that each path is under DATA_DIR
        assert config.DATA_DIR in path.parents or path.parent == config.DATA_DIR


def test_enrichment_constants():
    """Enrichment constants have expected types and values."""
    assert config.OPENAI_MODEL == "gpt-4o-mini"
    assert isinstance(config.OPENAI_MODEL, str)

    assert config.ENTITY_CHUNK_SIZE == 50
    assert isinstance(config.ENTITY_CHUNK_SIZE, int)

    assert config.MAX_RETRIES == 2
    assert isinstance(config.MAX_RETRIES, int)
    assert config.MAX_RETRIES > 0

    assert config.ENTITY_LEADERBOARD_TOP_N == 20
    assert isinstance(config.ENTITY_LEADERBOARD_TOP_N, int)
    assert config.ENTITY_LEADERBOARD_TOP_N > 0

    assert config.TAG_LEADERBOARD_TOP_N == 20
    assert isinstance(config.TAG_LEADERBOARD_TOP_N, int)
    assert config.TAG_LEADERBOARD_TOP_N > 0
