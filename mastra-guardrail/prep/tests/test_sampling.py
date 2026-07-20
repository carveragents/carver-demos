"""Tests for `mastra_prep.sampling` (spec §3 "Sampling & cost control").

`stratified_sample_sequence` returns the FULL deterministic reordering of its
input -- never a subset -- so that "sample and stop early" is just "process
fewer elements of an already-fixed list" (spec §3's determinism guarantee:
same seed + same candidate list in the same extraction order -> identical
sequence, independent of how many elements a caller ultimately consumes or how
many workers process them).
"""
from __future__ import annotations

from mastra_prep.sampling import stratified_sample_sequence


def _record(artifact_id: str, update_type: str, country: str | None, date: str,
            bloc: str | None = None) -> dict:
    return {
        "artifact_id": artifact_id,
        "update_type": update_type,
        "jurisdiction_country": country,
        "jurisdiction_bloc": bloc,
        "reconciled_published_date": date,
    }


def _make_pool(n: int, update_type: str, country: str, month: str) -> list[dict]:
    return [
        _record(f"{update_type}-{country}-{month}-{i}", update_type, country, f"{month}-{(i % 27) + 1:02d}")
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Full-pool coverage
# ---------------------------------------------------------------------------

def test_full_pool_coverage_length_matches():
    """`len(sequence) == len(candidates)` -- it returns the WHOLE deterministic
    order, never a subset. Callers take prefixes."""
    pool = _make_pool(37, "guidance", "US", "2026-04")

    sequence = stratified_sample_sequence(pool, seed=42)

    assert len(sequence) == len(pool)


def test_returns_a_permutation_not_a_new_or_dropped_set():
    pool = (
        _make_pool(20, "guidance", "US", "2026-04")
        + _make_pool(15, "enforcement", "DE", "2026-05")
        + _make_pool(10, "advisory", "MT", "2026-03")
    )

    sequence = stratified_sample_sequence(pool, seed=42)

    assert {r["artifact_id"] for r in sequence} == {r["artifact_id"] for r in pool}
    assert sorted(r["artifact_id"] for r in sequence) == sorted(r["artifact_id"] for r in pool)


def test_empty_input_returns_empty_list():
    assert stratified_sample_sequence([], seed=42) == []


def test_does_not_mutate_input_list():
    pool = _make_pool(10, "guidance", "US", "2026-04")
    original_order = [r["artifact_id"] for r in pool]

    stratified_sample_sequence(pool, seed=42)

    assert [r["artifact_id"] for r in pool] == original_order


# ---------------------------------------------------------------------------
# Determinism -- same seed, same input order -> identical sequence, TWICE.
# ---------------------------------------------------------------------------

def test_determinism_same_seed_identical_order_twice():
    pool = (
        _make_pool(25, "guidance", "US", "2026-04")
        + _make_pool(18, "enforcement", "DE", "2026-05")
        + _make_pool(12, "advisory", "MT", "2026-03")
        + _make_pool(9, "bulletin", "FR", "2026-06")
    )

    first_run = [r["artifact_id"] for r in stratified_sample_sequence(pool, seed=42)]
    second_run = [r["artifact_id"] for r in stratified_sample_sequence(pool, seed=42)]

    assert first_run == second_run


def test_different_seeds_can_produce_different_orders():
    pool = (
        _make_pool(25, "guidance", "US", "2026-04")
        + _make_pool(18, "enforcement", "DE", "2026-05")
        + _make_pool(12, "advisory", "MT", "2026-03")
    )

    seed_42 = [r["artifact_id"] for r in stratified_sample_sequence(pool, seed=42)]
    seed_7 = [r["artifact_id"] for r in stratified_sample_sequence(pool, seed=7)]

    assert seed_42 != seed_7


def test_default_seed_is_42():
    pool = _make_pool(15, "guidance", "US", "2026-04") + _make_pool(15, "enforcement", "DE", "2026-05")

    default_call = [r["artifact_id"] for r in stratified_sample_sequence(pool)]
    explicit_42 = [r["artifact_id"] for r in stratified_sample_sequence(pool, seed=42)]

    assert default_call == explicit_42


# ---------------------------------------------------------------------------
# Proportionality -- ANY prefix should approximate the population's stratum mix,
# not just the full sequence (that's the whole point of stratifying rather than
# plain-shuffling: an early-stopped run must still be representative).
# ---------------------------------------------------------------------------

def test_proportionality_every_prefix_tracks_population_ratio():
    """Three strata (by update_type/jurisdiction/month) at a 50/30/20 population
    split. For EVERY prefix length, each stratum's count-so-far must stay
    within 1 record of its exact proportional target -- the defining property
    of the largest-deficit-first interleaving (never merely true of the full
    sequence, which would be true of a plain shuffle too)."""
    strata = {
        "A": _make_pool(50, "guidance", "US", "2026-04"),
        "B": _make_pool(30, "enforcement", "DE", "2026-05"),
        "C": _make_pool(20, "advisory", "MT", "2026-03"),
    }
    pool = strata["A"] + strata["B"] + strata["C"]
    total = len(pool)
    sizes = {label: len(rows) for label, rows in strata.items()}

    def label_of(artifact_id: str) -> str:
        for label, rows in strata.items():
            if artifact_id in {r["artifact_id"] for r in rows}:
                return label
        raise AssertionError(artifact_id)

    sequence = stratified_sample_sequence(pool, seed=42)

    running_counts = {label: 0 for label in strata}
    for position, record in enumerate(sequence, start=1):
        running_counts[label_of(record["artifact_id"])] += 1
        for label in strata:
            target = position * sizes[label] / total
            assert abs(running_counts[label] - target) < 1.0 + 1e-9, (
                f"prefix {position}: stratum {label} count={running_counts[label]} "
                f"target={target:.2f}"
            )


def test_proportionality_final_counts_match_population_exactly():
    """At the full sequence (prefix == whole pool), every stratum's count must
    equal its population size exactly -- the largest-deficit rule degenerates
    to full coverage once every element has been placed."""
    strata_sizes = {"guidance/US": 12, "enforcement/DE": 7, "advisory/MT": 5}
    pool = (
        _make_pool(12, "guidance", "US", "2026-04")
        + _make_pool(7, "enforcement", "DE", "2026-05")
        + _make_pool(5, "advisory", "MT", "2026-03")
    )

    sequence = stratified_sample_sequence(pool, seed=42)

    counts = {"guidance/US": 0, "enforcement/DE": 0, "advisory/MT": 0}
    for record in sequence:
        key = f"{record['update_type']}/{record['jurisdiction_country']}"
        counts[key] += 1

    assert counts == strata_sizes


def test_proportionality_holds_across_many_awkwardly_sized_strata():
    """The 3-strata case above is provable by a short counting argument (each
    stratum's deficit is bounded because there are few competitors). Real
    curation stratifies on (update_type, jurisdiction_bucket, month_bucket)
    over an 8,260-record pool -- dozens of strata, not 3 -- so this test
    stress-checks the SAME `< 1` bound over 40 strata of awkward, unequal
    sizes (fixed-seed pseudo-random generation for reproducibility, not
    fixture hand-authorship). A regression here would only ever show up at
    this scale, never in the 3-stratum case."""
    import random as _random

    gen = _random.Random(20260716)  # fixed generation seed -- deterministic fixture, not a flaky test
    strata_sizes: dict[str, int] = {}
    pool: list[dict] = []
    for i in range(40):
        size = gen.randint(1, 17)
        update_type = f"synthetic-type-{i % 8}"
        country = f"Z{i:02d}"  # deliberately outside the top-10 codes -- exercises the "other" bucket too
        month = f"2026-{(i % 9) + 1:02d}"
        label = f"{update_type}|{country}|{month}"
        strata_sizes[label] = size
        pool.extend(
            _record(f"{label}-{j}", update_type, country, f"{month}-{(j % 27) + 1:02d}")
            for j in range(size)
        )

    total = len(pool)
    prefix_to_label = {f"{label}-": label for label in strata_sizes}

    def label_of(artifact_id: str) -> str:
        for prefix, label in prefix_to_label.items():
            if artifact_id.startswith(prefix):
                return label
        raise AssertionError(artifact_id)

    sequence = stratified_sample_sequence(pool, seed=42)
    assert len(sequence) == total

    running_counts = {label: 0 for label in strata_sizes}
    for position, record in enumerate(sequence, start=1):
        running_counts[label_of(record["artifact_id"])] += 1
        for label, size in strata_sizes.items():
            target = position * size / total
            assert abs(running_counts[label] - target) < 1.0 + 1e-9, (
                f"prefix {position}: stratum {label} count={running_counts[label]} "
                f"target={target:.2f}"
            )
