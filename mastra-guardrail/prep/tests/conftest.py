"""Shared pytest fixtures — spec §1.

The stub CLIENT CLASSES live in `tests/stubs.py`, importable, for the reason
given there (the `tests/` self-import trap in `docs/LESSONS.md`). This module
holds only thin fixtures wrapping them and defines no stub of its own: two
definitions of `StubOpenAIClient` — one importable, one fixture-injected — would
drift apart silently between test files.
"""
from __future__ import annotations

import pytest

from mastra_prep.budget import (
    PINNED_PRICE_INPUT_USD_PER_MILLION,
    PINNED_PRICE_OUTPUT_USD_PER_MILLION,
    SpendBudget,
)
from stubs import RecordingStubClient, StubOpenAIClient


@pytest.fixture
def budget() -> SpendBudget:
    """A SpendBudget at the pinned verified prices with generous headroom.

    Tests that exercise the ceiling construct their own with a tight ceiling;
    this one exists so the majority, which only need a budget to thread through
    a call, do not have to care.
    """
    return SpendBudget(
        ceiling_usd=1000.0,
        price_in=PINNED_PRICE_INPUT_USD_PER_MILLION,
        price_out=PINNED_PRICE_OUTPUT_USD_PER_MILLION,
    )


@pytest.fixture
def stub_client() -> StubOpenAIClient:
    """A client returning an empty JSON object to every call."""
    return StubOpenAIClient("{}")


@pytest.fixture
def recording_client() -> RecordingStubClient:
    """A client that captures kwargs and asserts the call's shape."""
    return RecordingStubClient("{}")
