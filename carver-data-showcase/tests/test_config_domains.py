"""Structural invariant tests for the domain taxonomy constants in carver_showcase/config.py.

Catches silent breakage that is hard to spot in review:
  - A 1-leaf tuple written without the trailing comma becomes a str, not a tuple.
  - Duplicate leaves would be silently accepted by the LLM prompt but break the
    parent map (last-write wins) and inflate or collapse the sunburst.
  - Mismatches between INSTITUTION_DOMAIN_LEAVES and INSTITUTION_DOMAIN_PARENT
    would cause KeyErrors at runtime in build_domain_rows / the sunburst charts.
"""
from __future__ import annotations

from carver_showcase.config import (
    DOMAIN_FALLBACK_LEAF,
    INSTITUTION_DOMAIN_LEAVES,
    INSTITUTION_DOMAIN_PARENT,
    INSTITUTION_DOMAIN_TAXONOMY,
)


class TestDomainTaxonomyInvariants:
    def test_all_taxonomy_values_are_tuples(self):
        """Every value in INSTITUTION_DOMAIN_TAXONOMY must be a tuple.

        A single-leaf entry written as ("leaf") instead of ("leaf",) silently
        produces a str, which then iterates character-by-character.
        """
        for top_level, leaves in INSTITUTION_DOMAIN_TAXONOMY.items():
            assert isinstance(leaves, tuple), (
                f"INSTITUTION_DOMAIN_TAXONOMY[{top_level!r}] is {type(leaves).__name__}, "
                "expected tuple (did you forget a trailing comma?)"
            )

    def test_all_top_level_keys_are_non_empty_strings(self):
        """Every top-level key must be a non-empty str."""
        for key in INSTITUTION_DOMAIN_TAXONOMY:
            assert isinstance(key, str) and key, (
                f"Top-level key {key!r} is not a non-empty string"
            )

    def test_institution_domain_leaves_has_no_duplicates(self):
        """INSTITUTION_DOMAIN_LEAVES must contain no duplicate entries."""
        seen: set[str] = set()
        duplicates: list[str] = []
        for leaf in INSTITUTION_DOMAIN_LEAVES:
            if leaf in seen:
                duplicates.append(leaf)
            seen.add(leaf)
        assert not duplicates, f"Duplicate leaves found: {duplicates}"

    def test_leaves_and_parent_same_length(self):
        """INSTITUTION_DOMAIN_LEAVES and INSTITUTION_DOMAIN_PARENT must have
        the same number of entries."""
        assert len(INSTITUTION_DOMAIN_LEAVES) == len(INSTITUTION_DOMAIN_PARENT), (
            f"INSTITUTION_DOMAIN_LEAVES has {len(INSTITUTION_DOMAIN_LEAVES)} entries "
            f"but INSTITUTION_DOMAIN_PARENT has {len(INSTITUTION_DOMAIN_PARENT)} keys"
        )

    def test_leaves_and_parent_same_key_set(self):
        """set(INSTITUTION_DOMAIN_LEAVES) must equal set(INSTITUTION_DOMAIN_PARENT)."""
        leaves_set = set(INSTITUTION_DOMAIN_LEAVES)
        parent_keys = set(INSTITUTION_DOMAIN_PARENT)
        only_in_leaves = leaves_set - parent_keys
        only_in_parent = parent_keys - leaves_set
        assert not only_in_leaves and not only_in_parent, (
            f"Mismatch: only in LEAVES={only_in_leaves}, only in PARENT={only_in_parent}"
        )

    def test_fallback_leaf_in_parent(self):
        """DOMAIN_FALLBACK_LEAF must be present in INSTITUTION_DOMAIN_PARENT."""
        assert DOMAIN_FALLBACK_LEAF in INSTITUTION_DOMAIN_PARENT, (
            f"DOMAIN_FALLBACK_LEAF {DOMAIN_FALLBACK_LEAF!r} is not in INSTITUTION_DOMAIN_PARENT"
        )
