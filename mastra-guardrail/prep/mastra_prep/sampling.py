"""Deterministic, seeded stratified ordering over the full candidate pool (spec §3).

`stratified_sample_sequence` returns a REORDERING of its whole input -- never a
subset. Callers who want a bounded probe/trial size take a PREFIX of the
returned list, which is what makes "sample and stop early" exactly "process
fewer elements of an already-fixed list" (spec §3's "Determinism & seeding":
same seed + same candidate list in the same extraction order -> identical
sequence, independent of how many elements a caller ultimately consumes).

Uses the same Hamilton/largest-remainder PRINCIPLE already proven in
`gics-topic-tagging::stratified_sample` (reimplemented here, not imported --
project isolation, spec §1) -- but adapted for a full-pool ORDERING rather than
a single fixed-size sample. `gics_tagging.stratified_sample(rows, n, seed)`
solves one apportionment problem for a fixed `n`. Re-solving that problem
independently at every candidate prefix length is NOT safe for building a
single sequence: Hamilton's method is famously non-monotonic in the number of
seats (the "Alabama paradox" -- a party's seat count can DECREASE when the
total number of seats increases), which would require "un-emitting" an item
already placed at an earlier position. `stratified_sample_sequence` instead
builds the sequence by always emitting NEXT from whichever stratum has the
largest deficit between its ideal proportional share of records-so-far and its
actual count-so-far -- the same quota+remainder idea, applied incrementally so
the result is monotonic by construction: every prefix is only ever extended,
never revised.

Every prefix's per-stratum count stays within 1 record of its exact
proportional target (`abs(count - position * size / total) < 1`) --
`tests/test_sampling.py` checks this directly for 3 strata (where it is
provable by a short counting argument) and empirically, via a many-strata
randomized/exhaustive stress case, for the 40+ -stratum regime this module
actually runs in during curation. No violation has been found in either
check; treat the bound as strongly empirically supported rather than as a
theorem proved in this docstring.

LEAF module: imports nothing else from `mastra_prep`
(`tests/test_imports.py::test_no_circular_imports` enforces this).
"""
from __future__ import annotations

import random

# The same top-10 jurisdiction codes goal.md itself measures (US/FR/CA/CN/AU/
# DE/GB/IT/CH/NL, by candidate-pool count) -- anything else buckets to "other".
# Codes, not names: matches `extract_record`'s flat `jurisdiction_country`/
# `jurisdiction_bloc` output (spec §2's FIELD_MAP), which is the shape every
# record reaching this function actually has.
_TOP_10_JURISDICTION_CODES = frozenset(
    {"US", "FR", "CA", "CN", "AU", "DE", "GB", "IT", "CH", "NL"}
)


def _jurisdiction_bucket(record: dict) -> str:
    """`jurisdiction_country`/`jurisdiction_bloc` collapsed to the top-10 codes
    or `"other"` -- keeps the stratum count small and stable regardless of how
    many distinct jurisdictions the corpus actually contains. A non-string
    code (corpus rot) falls back to `"other"` rather than raising -- sampling
    must never fail on a malformed field."""
    code = record.get("jurisdiction_country") or record.get("jurisdiction_bloc")
    if not isinstance(code, str):
        return "other"
    return code if code in _TOP_10_JURISDICTION_CODES else "other"


def _month_bucket(record: dict) -> str:
    """`YYYY-MM` of `reconciled_published_date` -- coarse enough to be a small,
    stable stratum axis; falls back to `"unknown"` for a missing/malformed
    date rather than raising (sampling must never fail on corpus rot)."""
    date = record.get("reconciled_published_date")
    if isinstance(date, str) and len(date) >= 7:
        return date[:7]
    return "unknown"


def _stratum_key(record: dict) -> tuple[str, str, str]:
    """`(update_type, jurisdiction_bucket, month_bucket)` -- spec §3."""
    return (
        record.get("update_type") or "unknown",
        _jurisdiction_bucket(record),
        _month_bucket(record),
    )


def stratified_sample_sequence(rows: list[dict], seed: int = 42) -> list[dict]:
    """Return the FULL input, reordered so that every prefix approximates the
    population's stratum proportions -- callers take prefixes for a bounded
    sample. Pure: never mutates `rows`. Deterministic: the same `seed` over the
    same input (in the same order) always yields the identical output
    sequence, independent of worker count or how many elements are consumed.
    """
    if not rows:
        return []

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault(_stratum_key(row), []).append(row)

    # Shuffle within each stratum, consuming ONE shared RNG in a fixed (sorted
    # key) order -- both facts together are what make the result depend only
    # on `seed` and the input's own order, never on dict/set iteration order.
    rng = random.Random(seed)
    keys = sorted(groups)
    for key in keys:
        rng.shuffle(groups[key])

    sizes = {key: len(groups[key]) for key in keys}
    total = len(rows)
    emitted = {key: 0 for key in keys}

    out: list[dict] = []
    for position in range(1, total + 1):
        # Largest-deficit-first: the stratum furthest below its ideal
        # proportional share (position * size / total) goes next. `keys` is
        # a fixed sorted list and `max()` returns the FIRST maximal element
        # it encounters on a tie (a documented Python guarantee), so ties
        # resolve to the smallest key -- the result never depends on
        # dict/set iteration order. At least one candidate always remains
        # (deficits across all not-yet-exhausted strata sum to exactly 1 at
        # every position), so `best_key` is never `None`.
        candidates = (key for key in keys if emitted[key] < sizes[key])
        best_key = max(candidates, key=lambda key: position * sizes[key] / total - emitted[key])
        out.append(groups[best_key][emitted[best_key]])
        emitted[best_key] += 1

    return out
