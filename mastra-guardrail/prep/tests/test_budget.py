"""Tests for `mastra_prep.budget` — §3's hard spend ceiling.

This module protects a real credit card, so the tests are written against §3's
*proof*, not just its API: **one test per row of §3's lifecycle table**, each
asserting BOTH invariants the proof claims unconditionally:

    spend_so_far_usd <= ceiling_usd        (the ceiling is never exceeded)
    spend_so_far_usd >= true_billed_total  (spend is never under-stated)

The two numbers `budget.py` computes do different jobs, and the tests keep them
apart deliberately:

  * `Reservation.amount_usd` = `max_call_cost(payload)` — the PROVIDER-guaranteed
    maximum (context window x price_in + max_completion_tokens x price_out).
    It **enforces the ceiling** and contains no estimate of ours.
  * `Reservation.expected_max_usd` = the tight estimate from
    `reservation_basis_tokens()`. It **detects our bugs** and nothing else;
    `settle()` poisons the budget when reality beats it.

`PROVIDER_MAX_CALL_COST_USD` below is computed BY HAND from the pinned rates
rather than re-derived from `budget.py`'s own formula — a test that recomputes
the implementation's arithmetic with the implementation's arithmetic proves
nothing.
"""

import gc
import json
import logging
from datetime import date

import pytest

from mastra_prep.budget import (
    CUTOFF_MARGIN_DAYS,
    CUTOFF_MARGIN_IS_INCLUSIVE,
    MODEL_CUTOFF,
    MODEL_CUTOFFS,
    MODEL_MAX_CONTEXT_TOKENS,
    PINNED_PRICE_INPUT_USD_PER_MILLION,
    PINNED_PRICE_OUTPUT_USD_PER_MILLION,
    REASONING_EFFORT,
    REQUEST_OVERHEAD_ALLOWANCE_TOKENS,
    UNBILLED_STATUS_CODES,
    BudgetExhausted,
    BudgetPoisoned,
    Reservation,
    SpendBudget,
    build_request_payload,
    estimate_tokens,
    reservation_basis_tokens,
    terminal_for_exception,
)

CEILING_USD = 120.0                 # config.yaml's total_spend_ceiling_usd (§3)
MAX_COMPLETION_TOKENS = 3_000       # §3's Stage A cap

# Hand-computed from the pinned published rates, NOT from budget.py's formula:
#   input  1,000,000 tokens x $5.00 / 1,000,000 = $5.00   (the provider's context window)
#   output     3,000 tokens x $30.00 / 1,000,000 = $0.09  (max_completion_tokens)
#                                                  ------
PROVIDER_MAX_CALL_COST_USD = 5.09

BOOKABLE_USAGE = {"prompt_tokens": 500, "completion_tokens": 200}

# IEEE-754 slack for the "spend >= true billed" invariant, and ONLY that one.
#
# `settle()` computes `spend += actual - amount_usd`, and the hold ($5.09) is ~3
# orders of magnitude larger than a typical real bill ($0.0085), so the cancellation
# leaves ~1e-16 relative error: booking $0.0085 lands on $0.00849999999999973.
#
# Which invariant the slack falls on matters, and it is worth being exact rather than
# hand-waving, because this module's correctness argument IS a proof:
#
#   * `spend <= ceiling` is EXACT in IEEE-754 — no tolerance, and the tests assert it
#     exactly. reserve()'s gate evaluates `fl(spend + amount)` and its `+=` recomputes
#     the identical expression, so the committed value is bit-for-bit the tested one.
#     settle() then adds a provably non-positive delta: _usage_is_bookable caps the
#     counts at the SAME constants max_call_cost multiplies, using the SAME prices and
#     the same formula shape, and IEEE rounding is monotone — so fl(actual) <=
#     fl(amount) holds exactly, hence fl(spend + (actual - amount)) <= spend.
#   * The slack falls ENTIRELY on `spend >= true_billed`. That is the direction that
#     can cost money: the real-money chain is `true_billed <= spend <= ceiling`, so a
#     ledger under-stating the true bill by d relaxes the gate to `true_billed <=
#     ceiling + d`. It is bounded by ulp(amount) ~ 9e-16 USD per call — ~1e-11 USD
#     over a 10,000-call run, a hundred-billionth of a cent against a $120 ceiling.
#
# So the real-money ceiling is $120.00 + O(1e-11), and it is immaterial BECAUSE that
# bound is tiny — not because rounding low "helps".
LEDGER_FLOAT_TOLERANCE_USD = 1e-9


def usd(prompt_tokens: int, completion_tokens: int) -> float:
    """The true bill for a usage report, at the pinned published rates."""
    return (prompt_tokens * 5.00 + completion_tokens * 30.00) / 1_000_000


def make_budget(ceiling_usd: float = CEILING_USD) -> SpendBudget:
    return SpendBudget(
        ceiling_usd,
        PINNED_PRICE_INPUT_USD_PER_MILLION,
        PINNED_PRICE_OUTPUT_USD_PER_MILLION,
    )


def make_payload(
    user_text: str = "Which obligations apply to this launch?",
    max_completion_tokens: int = MAX_COMPLETION_TOKENS,
    schema: dict | None = None,
) -> dict:
    return build_request_payload(
        model="gpt-5.6-sol",
        system_text="You are a compliance analyst.",
        user_text=user_text,
        max_completion_tokens=max_completion_tokens,
        reasoning_effort=REASONING_EFFORT,
        schema=schema,
    )


class StubStatusError(Exception):
    """Shaped like `openai.BadRequestError` & friends: carries `.status_code`."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class StubTimeout(Exception):
    """Shaped like `openai.APITimeoutError`: NO `.status_code` at all — the
    provider never told us whether it ran the request."""


class StubResponse:
    """The `else`-branch shape of the §3 lifecycle: a response with a usage report."""

    def __init__(self, usage: object) -> None:
        self.usage = usage


# --------------------------------------------------------------------------
# Pinned constants — the values the proof and the seam depend on
# --------------------------------------------------------------------------


def test_pinned_constants_have_their_specified_values():
    assert MODEL_MAX_CONTEXT_TOKENS == 1_000_000
    assert REQUEST_OVERHEAD_ALLOWANCE_TOKENS == 1024
    assert PINNED_PRICE_INPUT_USD_PER_MILLION == 5.00
    assert PINNED_PRICE_OUTPUT_USD_PER_MILLION == 30.00
    assert REASONING_EFFORT == "medium"
    assert MODEL_CUTOFF == "2026-02-16"
    assert CUTOFF_MARGIN_DAYS == 14
    assert CUTOFF_MARGIN_IS_INCLUSIVE is True


def test_model_cutoffs_pins_the_one_verified_entry():
    """The table orchestrator D14 adds: model-router string -> the PROVIDER-DOCUMENTED
    knowledge cutoff. Seeded with the single verified entry (goal #9: OpenAI's own
    docs, checked 2026-07-16). It is deliberately NOT a catalogue of every model that
    exists — an entry here is a claim that someone READ that model's documented cutoff.
    """
    assert MODEL_CUTOFFS == {"openai/gpt-5.6-sol": "2026-02-16"}


def test_model_cutoff_agrees_with_the_table_for_the_shipped_model():
    """The invariant `load_settings()` enforces (D14), pinned here at the constants
    themselves so the two cannot drift apart in this file either.
    """
    assert MODEL_CUTOFF == MODEL_CUTOFFS["openai/gpt-5.6-sol"]


def test_model_cutoffs_values_are_parseable_iso_dates():
    """Every value feeds `date.fromisoformat` via `candidates._derived_floor()`.

    The key check pins that no table entry can be dead by construction against §13's
    `openai/` prefix rule — an entry that could never be reached would be a cutoff
    nobody enforces.
    """
    for router_string, cutoff in MODEL_CUTOFFS.items():
        assert router_string.startswith("openai/"), router_string
        # The assertion is that this does not RAISE; `assert date.fromisoformat(...)`
        # would be unfalsifiable, since a date object is always truthy.
        date.fromisoformat(cutoff)


def test_unbilled_status_codes_are_pre_inference_rejections_only():
    # Exactly §3's set: statuses OpenAI returns BEFORE running inference. A 5xx or a
    # timeout is NOT here — the request may well have run and been billed.
    assert UNBILLED_STATUS_CODES == frozenset({400, 401, 403, 404, 409, 422, 429})
    assert isinstance(UNBILLED_STATUS_CODES, frozenset)
    for billed_or_unknown in (500, 502, 503, 504, 200):
        assert billed_or_unknown not in UNBILLED_STATUS_CODES


def test_budget_poisoned_is_caught_as_budget_exhausted():
    # §3's raiser/catch contract: run_curation/decide_scenario catch BudgetExhausted
    # and must thereby catch BudgetPoisoned too.
    assert issubclass(BudgetPoisoned, BudgetExhausted)


# --------------------------------------------------------------------------
# build_request_payload / estimate_tokens / reservation_basis_tokens
# --------------------------------------------------------------------------


def test_build_request_payload_is_the_complete_sdk_ready_kwargs():
    payload = build_request_payload(
        model="gpt-5.6-sol",
        system_text="sys text",
        user_text="user text",
        max_completion_tokens=1_500,
        reasoning_effort=REASONING_EFFORT,
        schema=None,
    )
    assert payload == {
        "model": "gpt-5.6-sol",
        "messages": [
            {"role": "system", "content": "sys text"},
            {"role": "user", "content": "user text"},
        ],
        "reasoning_effort": "medium",
        "max_completion_tokens": 1_500,
    }
    assert "response_format" not in payload


def test_build_request_payload_carries_the_schema_on_structured_calls():
    schema = {"name": "stage_b", "schema": {"type": "object", "properties": {}}}
    payload = make_payload(schema=schema)
    assert payload["response_format"] == {"type": "json_schema", "json_schema": schema}


def test_estimate_tokens_is_a_utf8_byte_upper_bound():
    # The one mathematically guaranteed bound: byte-level fallback means no token
    # ever spans less than one byte, so token_count <= utf-8 byte count, always.
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 3
    assert estimate_tokens("é") == 2        # 2 UTF-8 bytes, 1 code point
    assert estimate_tokens("日本語") == 9   # 3 bytes each


def test_reservation_includes_overhead_allowance():
    payload = make_payload()
    expected = (
        len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        + REQUEST_OVERHEAD_ALLOWANCE_TOKENS
    )
    assert reservation_basis_tokens(payload) == expected
    assert reservation_basis_tokens(payload) > REQUEST_OVERHEAD_ALLOWANCE_TOKENS


def test_reservation_basis_counts_utf8_bytes_not_escaped_ascii():
    # Pins `ensure_ascii=False`. Every other payload in this suite is ASCII, where
    # json.dumps(x) and json.dumps(x, ensure_ascii=False) are byte-identical — so
    # without this case, dropping the kwarg passes the whole suite.
    #
    # It is worth pinning deliberately, because §14's restatement of this assertion
    # omits the kwarg while §3's pinned code (the authoritative site) has it. §3 is
    # right: the wire carries UTF-8, so ensure_ascii=False is both the tighter and the
    # still-valid bound. Escaping would inflate the estimate ("日" -> 日, 6 bytes
    # instead of 3), which cannot breach the ceiling but WEAKENS the anomaly tripwire.
    payload = make_payload(user_text="日本語")
    assert reservation_basis_tokens(payload) == (
        len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        + REQUEST_OVERHEAD_ALLOWANCE_TOKENS
    )
    assert reservation_basis_tokens(payload) < (
        len(json.dumps(payload).encode("utf-8")) + REQUEST_OVERHEAD_ALLOWANCE_TOKENS
    )


def test_budget_logs_on_the_shared_mastra_prep_channel(caplog):
    # budget.py is a LEAF: it cannot import logging_.log() (that would be an
    # intra-package import, and test_imports.py asserts its set is empty), so it binds
    # stdlib logging directly. The entire defence of that deviation is "it is the same
    # channel logging_.log() writes to" — §1 pins logging_.log as a thin wrapper over
    # logging.getLogger("mastra_prep").info(...). This asserts it rather than trusting it.
    with caplog.at_level(logging.INFO, logger="mastra_prep"):
        make_budget().reserve(make_payload()).release("a released reservation logs")
    assert [r.name for r in caplog.records] == ["mastra_prep"]
    assert caplog.records[0].levelno == logging.INFO
    assert "reservation released" in caplog.records[0].message


def test_reservation_basis_counts_every_content_bearing_byte():
    # Claim (1) of reservation_basis_tokens' docstring: system_text, user_text and the
    # schema each appear inside the basis. Growing any of them grows the estimate.
    empty_user = reservation_basis_tokens(make_payload(user_text=""))
    longer_user = reservation_basis_tokens(make_payload(user_text="x" * 5_000))
    assert longer_user >= empty_user + 5_000
    with_schema = reservation_basis_tokens(
        make_payload(schema={"name": "s", "schema": {"type": "object"}})
    )
    assert with_schema > reservation_basis_tokens(make_payload())


# --------------------------------------------------------------------------
# The price floor — enforced in SpendBudget.__init__, independently of load_settings()
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "price_in, price_out",
    [
        pytest.param(0.001, 30.00, id="input_far_below_floor"),
        pytest.param(5.00, 0.001, id="output_far_below_floor"),
        pytest.param(0.001, 0.001, id="both_far_below_floor"),
        pytest.param(4.99, 30.00, id="input_just_below_floor"),
        pytest.param(5.00, 29.99, id="output_just_below_floor"),
    ],
)
def test_price_below_the_pinned_floor_is_rejected(price_in, price_out):
    # A configured price below the verified rate would make the "hard" ceiling
    # meaningless — reserve near-infinite headroom against a real, unchanged bill.
    # This is the SECOND enforcement point: load_settings() (§13) also checks, but
    # SpendBudget must be safe to construct directly, as these tests do.
    with pytest.raises(ValueError, match="pinned verified floor"):
        SpendBudget(CEILING_USD, price_in, price_out)


@pytest.mark.parametrize(
    "price_in, price_out",
    [
        pytest.param(float("nan"), 30.00, id="nan_input_price"),
        pytest.param(5.00, float("nan"), id="nan_output_price"),
        pytest.param(float("inf"), 30.00, id="inf_input_price"),
        pytest.param(5.00, float("inf"), id="inf_output_price"),
    ],
)
def test_non_finite_price_is_rejected(price_in, price_out):
    # DEVIATION 2 from §3's pinned code. NaN passes the floor check unnoticed
    # (`nan < 5.00` is False) and then defeats reserve()'s gate (`spend + nan > ceiling`
    # is also False), removing the ceiling entirely. PyYAML resolves `.nan` from
    # config.yaml, and §13's load_settings() check has the same `<` shape — so without
    # this guard a one-word config edit buys unbounded spend on a real card.
    with pytest.raises(ValueError, match="finite"):
        SpendBudget(CEILING_USD, price_in, price_out)


@pytest.mark.parametrize(
    "ceiling",
    [
        pytest.param(float("nan"), id="nan_ceiling"),
        pytest.param(float("inf"), id="inf_ceiling"),
        pytest.param(0.0, id="zero_ceiling"),
        pytest.param(-1.0, id="negative_ceiling"),
    ],
)
def test_non_finite_or_non_positive_ceiling_is_rejected(ceiling):
    # A non-finite ceiling is not a ceiling: `spend + amount > nan` is False forever.
    with pytest.raises(ValueError, match="finite, positive"):
        SpendBudget(ceiling, PINNED_PRICE_INPUT_USD_PER_MILLION, PINNED_PRICE_OUTPUT_USD_PER_MILLION)


def test_a_nan_price_cannot_defeat_the_ceiling_gate():
    # The end-to-end statement of what DEVIATION 2 buys: the NaN never reaches the gate.
    with pytest.raises(ValueError):
        budget = SpendBudget(CEILING_USD, float("nan"), PINNED_PRICE_OUTPUT_USD_PER_MILLION)
        for _ in range(100):
            budget.reserve(make_payload())   # unreachable: would never raise, spend -> NaN


def test_price_at_or_above_the_pinned_floor_is_accepted():
    at_floor = make_budget()
    assert at_floor.ceiling_usd == CEILING_USD
    assert at_floor.spend_so_far_usd == 0.0
    # A price RISE is always safe — it only makes the arithmetic more conservative.
    SpendBudget(CEILING_USD, 10.00, 60.00)


# --------------------------------------------------------------------------
# The gate: the ceiling REFUSES the call; it does not detect the overspend after
# --------------------------------------------------------------------------


def test_max_call_cost_is_the_provider_guaranteed_maximum_not_an_estimate():
    budget = make_budget()
    assert budget.max_call_cost(make_payload()) == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    # It does not depend on the prompt at all — only on the provider's two caps. A
    # 100k-character prompt reserves exactly the same amount as a 40-character one.
    assert budget.max_call_cost(make_payload(user_text="x" * 100_000)) == pytest.approx(
        PROVIDER_MAX_CALL_COST_USD
    )
    # The output term IS the caller's cap, so a smaller cap reserves strictly less.
    assert budget.max_call_cost(make_payload(max_completion_tokens=1_200)) == pytest.approx(
        5.00 + 1_200 * 30.00 / 1_000_000
    )


def test_reserve_holds_the_provider_maximum_before_the_call_fires():
    budget = make_budget()
    res = budget.reserve(make_payload())
    # The hold is booked by reserve() itself — i.e. BEFORE any call could be issued.
    assert res.amount_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    assert budget.spend_so_far_usd <= budget.ceiling_usd


def test_tiny_ceiling_rejects_every_call():
    budget = make_budget(ceiling_usd=1.00)   # below one call's provider maximum ($5.09)
    with pytest.raises(BudgetExhausted, match="ceiling"):
        budget.reserve(make_payload())
    assert budget.spend_so_far_usd == 0.0
    budget.assert_no_open_reservations()     # a refused reserve() leaves no handle


def test_ceiling_refuses_the_call_rather_than_detecting_it_afterwards():
    # The property an earlier draft did NOT have: the gate runs before the billable
    # call, so an over-ceiling call is never issued at all. A post-call ledger check
    # can only detect an overspend; it cannot un-spend the money.
    budget = make_budget(ceiling_usd=2 * PROVIDER_MAX_CALL_COST_USD + 0.01)
    first, second = budget.reserve(make_payload()), budget.reserve(make_payload())
    spend_at_capacity = budget.spend_so_far_usd
    assert spend_at_capacity <= budget.ceiling_usd

    with pytest.raises(BudgetExhausted, match="provider-maximum"):
        budget.reserve(make_payload())

    # The refused call moved nothing and left nothing behind.
    assert budget.spend_so_far_usd == spend_at_capacity
    first.settle(BOOKABLE_USAGE)
    second.settle(BOOKABLE_USAGE)
    budget.assert_no_open_reservations()
    assert budget.spend_so_far_usd <= budget.ceiling_usd


def test_reserve_refuses_once_the_budget_is_poisoned():
    budget = make_budget()
    res = budget.reserve(make_payload())
    with pytest.raises(BudgetPoisoned):
        res.settle(None)                     # poisons via finalize_unusable_usage
    with pytest.raises(BudgetExhausted, match="poisoned"):
        budget.reserve(make_payload())       # a retry gets a clean stop, not a call


# --------------------------------------------------------------------------
# §3's lifecycle table — one test per row
# --------------------------------------------------------------------------


def test_settle_books_actual_and_returns_headroom():
    """Row 1: settle(usage) — bookable report. spend becomes spend_before + b."""
    budget = make_budget()
    res = budget.reserve(make_payload())
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)

    res.settle(BOOKABLE_USAGE)

    # (500 x $5.00 + 200 x $30.00) / 1e6 = $0.0085, computed on paper.
    true_bill = 0.0085
    assert usd(500, 200) == pytest.approx(true_bill)
    assert budget.spend_so_far_usd == pytest.approx(true_bill)
    assert budget.spend_so_far_usd <= budget.ceiling_usd                          # invariant 1
    assert budget.spend_so_far_usd >= true_bill - LEDGER_FLOAT_TOLERANCE_USD      # invariant 2
    budget.assert_no_open_reservations()


def test_release_returns_the_full_hold():
    """Row 2: release(...) — the provider CONFIRMED it did not bill (HTTP 400)."""
    budget = make_budget()
    spend_before = budget.spend_so_far_usd
    res = budget.reserve(make_payload())
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)

    terminal_for_exception(res, StubStatusError(400))

    assert budget.spend_so_far_usd == pytest.approx(spend_before)   # back to zero
    assert budget.spend_so_far_usd <= budget.ceiling_usd            # invariant 1
    assert budget.spend_so_far_usd >= 0.0                           # invariant 2: b == 0
    budget.assert_no_open_reservations()


def test_finalize_unknown_keeps_the_full_hold():
    """Row 3: finalize_unknown(...) — timeout/5xx. The call MAY have been billed."""
    budget = make_budget()
    res = budget.reserve(make_payload())

    terminal_for_exception(res, StubTimeout())

    # The hold stays: we cannot prove b == 0, so we assume the worst (b <= A).
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    assert budget.spend_so_far_usd <= budget.ceiling_usd                    # invariant 1
    # invariant 2: whatever the unknown true bill b was, the provider's caps put it at
    # or below the hold we kept — so the ledger cannot be under-stating it.
    assert budget.spend_so_far_usd >= res.amount_usd
    budget.assert_no_open_reservations()


def test_ceiling_holds_at_provider_maximum():
    """The largest bill the provider can physically produce settles cleanly.

    For the provider to bill MODEL_MAX_CONTEXT_TOKENS of input, the request must
    actually CARRY that many tokens — and no token spans less than one byte, so a
    payload serializing to ~1M bytes is what makes such a usage report consistent
    with the tight estimate. (A 300-byte payload reporting 1M prompt tokens is
    itself the anomaly settle() exists to catch — see
    test_settle_poisons_when_tight_estimate_is_beaten.)
    """
    budget = make_budget()
    payload = make_payload(user_text="x" * MODEL_MAX_CONTEXT_TOKENS)
    res = budget.reserve(payload)
    assert res.amount_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)

    res.settle(
        {"prompt_tokens": MODEL_MAX_CONTEXT_TOKENS, "completion_tokens": MAX_COMPLETION_TOKENS}
    )

    true_bill = usd(MODEL_MAX_CONTEXT_TOKENS, MAX_COMPLETION_TOKENS)   # $5.09
    assert budget.spend_so_far_usd == pytest.approx(true_bill)
    assert budget.spend_so_far_usd <= budget.ceiling_usd
    assert budget.spend_so_far_usd >= true_bill
    # No exception, and no poisoning: this is exactly what was reserved.
    budget.reserve(make_payload())            # the budget still works


def test_retry_does_not_double_count():
    """The exact leak the Reservation type exists to prevent.

    A first attempt that times out, then a successful retry, leaves spend equal to
    the retry's TRUE cost plus the first attempt's provider-maximum hold — never
    two full holds, and never the first hold forever with a second stacked on it.
    """
    budget = make_budget()
    first = budget.reserve(make_payload())
    terminal_for_exception(first, StubTimeout())          # keeps its own hold, terminally

    retry = budget.reserve(make_payload())                # a NEW call: fresh reservation
    retry.settle({"prompt_tokens": 400, "completion_tokens": 100})

    retry_bill = usd(400, 100)
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD + retry_bill)
    assert budget.spend_so_far_usd < 2 * PROVIDER_MAX_CALL_COST_USD   # not two full holds
    assert budget.spend_so_far_usd <= budget.ceiling_usd
    # invariant 2: true billed <= (unknown first bill <= $5.09) + retry's real bill
    assert budget.spend_so_far_usd >= retry_bill
    budget.assert_no_open_reservations()


def test_assert_no_open_reservations():
    """Row 5: a reserve() with no terminal op is caught at end of run."""
    budget = make_budget()
    res = budget.reserve(make_payload())

    with pytest.raises(AssertionError, match="never reached a terminal"):
        budget.assert_no_open_reservations()

    # Row 5's invariants while the reservation is open: the hold is kept, so spend is
    # <= ceiling and >= the true bill (b <= A) — over-stated, which is safe, not unsafe.
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)   # invariant 1
    assert budget.spend_so_far_usd <= budget.ceiling_usd
    assert budget.spend_so_far_usd >= res.amount_usd                              # invariant 2

    res.settle(BOOKABLE_USAGE)
    budget.assert_no_open_reservations()      # clean once terminated


def test_assert_no_open_reservations_passes_on_a_fresh_budget():
    make_budget().assert_no_open_reservations()


def test_leak_is_still_caught_after_the_handle_is_garbage_collected():
    """DEVIATION 3: the audit must survive the leaked handle being freed and its
    address recycled.

    `_open` holds ints, never references, so a leaked Reservation — precisely what
    this audit exists to catch — is freed by refcounting the instant it goes out of
    scope, and the next reserve() allocates at the same address. Under the pinned
    `id(self)` scheme, `_open.add(id(r))` was then a no-op on a set already holding
    that id, and terminating the NEW handle discarded the leaked one's entry with it:
    the audit passed and the leak vanished. Measured at 4,999/5,000 through the real
    reserve() path — i.e. the audit almost never worked in the one scenario it is for.
    A monotonic seq cannot be recycled.
    """
    budget = make_budget()

    def leak() -> None:
        budget.reserve(make_payload())        # handle dropped, never terminated

    leak()
    gc.collect()
    second = budget.reserve(make_payload())   # may land on the freed address
    second.settle(BOOKABLE_USAGE)

    with pytest.raises(AssertionError, match="1 reservation"):
        budget.assert_no_open_reservations()


def test_every_reservation_gets_a_distinct_seq():
    budget = make_budget()
    handles = [budget.reserve(make_payload(max_completion_tokens=1)) for _ in range(5)]
    assert len({r.seq for r in handles}) == 5
    assert budget._open == {r.seq for r in handles}


# --------------------------------------------------------------------------
# Exactly ONE terminal operation per handle
# --------------------------------------------------------------------------


def _terminate(res: Reservation, op: str) -> None:
    if op == "settle":
        res.settle(BOOKABLE_USAGE)
    elif op == "release":
        res.release("test")
    elif op == "finalize_unknown":
        res.finalize_unknown("test")
    else:                                     # pragma: no cover - guards a typo in the params
        raise ValueError(op)


@pytest.mark.parametrize("first_op", ["settle", "release", "finalize_unknown"])
@pytest.mark.parametrize("second_op", ["settle", "release", "finalize_unknown"])
def test_double_terminal_raises(first_op, second_op):
    budget = make_budget()
    res = budget.reserve(make_payload())
    _terminate(res, first_op)
    spend_after_first = budget.spend_so_far_usd

    with pytest.raises(AssertionError, match="second terminal operation"):
        _terminate(res, second_op)

    # The rejected second op changed nothing.
    assert budget.spend_so_far_usd == pytest.approx(spend_after_first)
    assert budget.spend_so_far_usd <= budget.ceiling_usd


def test_double_terminal_raises_after_finalize_unusable_usage():
    budget = make_budget()
    res = budget.reserve(make_payload())
    with pytest.raises(BudgetPoisoned):
        res.settle(None)
    spend_after_first = budget.spend_so_far_usd

    with pytest.raises(AssertionError, match="second terminal operation"):
        res.finalize_unknown("a second terminal op on a poisoned handle")
    assert budget.spend_so_far_usd == pytest.approx(spend_after_first)


# --------------------------------------------------------------------------
# terminal_for_exception — routed by what the provider actually reported
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", sorted(UNBILLED_STATUS_CODES))
def test_terminal_for_exception_releases_on_every_unbilled_status(status):
    budget = make_budget()
    res = budget.reserve(make_payload())
    terminal_for_exception(res, StubStatusError(status))
    assert budget.spend_so_far_usd == pytest.approx(0.0)
    budget.assert_no_open_reservations()


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(StubTimeout(), id="timeout_no_status_attr"),
        pytest.param(ConnectionError("reset by peer"), id="connection_error"),
        pytest.param(StubStatusError(500), id="http_500_may_have_run"),
        pytest.param(StubStatusError(503), id="http_503_may_have_run"),
        pytest.param(StubStatusError(None), id="status_attr_present_but_none"),
    ],
)
def test_terminal_for_exception_finalizes_unknown_when_billing_is_unknown(exc):
    budget = make_budget()
    res = budget.reserve(make_payload())
    terminal_for_exception(res, exc)
    # Conservative: the hold is KEPT, because the request may have run and been billed.
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    assert budget.spend_so_far_usd <= budget.ceiling_usd
    budget.assert_no_open_reservations()


# --------------------------------------------------------------------------
# The anomaly tripwire — settle() vs the TIGHT estimate
# --------------------------------------------------------------------------


def test_settle_poisons_when_tight_estimate_is_beaten():
    """A bill above expected_max_usd but below amount_usd: the tripwire fires and
    the run stops — while the ceiling was never at risk."""
    budget = make_budget()
    res = budget.reserve(make_payload())      # small payload: expected_max ~ $0.10
    assert res.expected_max_usd < res.amount_usd

    with pytest.raises(BudgetPoisoned, match="our request model is wrong"):
        res.settle({"prompt_tokens": 500_000, "completion_tokens": MAX_COMPLETION_TOKENS})

    actual = usd(500_000, MAX_COMPLETION_TOKENS)     # $2.59 — above the estimate, below the hold
    assert actual > res.expected_max_usd
    assert actual < res.amount_usd
    assert budget.spend_so_far_usd == pytest.approx(actual)   # the truth is still booked
    assert budget.spend_so_far_usd <= budget.ceiling_usd      # the ceiling held throughout
    with pytest.raises(BudgetExhausted):                      # and the run stops
        budget.reserve(make_payload())
    budget.assert_no_open_reservations()


def test_settle_does_not_poison_when_the_bill_is_within_the_estimate():
    budget = make_budget()
    res = budget.reserve(make_payload())
    res.settle(BOOKABLE_USAGE)
    budget.reserve(make_payload())            # not poisoned — reserve still works


# --------------------------------------------------------------------------
# The unbookable-usage battery — §3's finalize_unusable_usage
# --------------------------------------------------------------------------

UNBOOKABLE_USAGE = [
    pytest.param(None, id="no_usage_at_all"),
    pytest.param({}, id="both_keys_missing"),
    pytest.param({"prompt_tokens": 10}, id="completion_key_missing"),
    pytest.param({"completion_tokens": 10}, id="prompt_key_missing"),
    pytest.param({"prompt_tokens": "12", "completion_tokens": 10}, id="non_numeric_string"),
    pytest.param({"prompt_tokens": 12.5, "completion_tokens": 10}, id="float_not_int"),
    pytest.param({"prompt_tokens": None, "completion_tokens": 10}, id="explicit_none"),
    pytest.param({"prompt_tokens": True, "completion_tokens": 10}, id="bool_is_int_trap"),
    pytest.param({"prompt_tokens": 10, "completion_tokens": False}, id="bool_is_int_trap_output"),
    pytest.param({"prompt_tokens": -1, "completion_tokens": 10}, id="negative_prompt"),
    pytest.param({"prompt_tokens": 10, "completion_tokens": -1}, id="negative_completion"),
    pytest.param("not-a-mapping", id="non_mapping_string"),
    pytest.param([500, 200], id="non_mapping_list"),
]


@pytest.mark.parametrize("usage", UNBOOKABLE_USAGE)
def test_unbookable_usage_poisons_and_retains_the_hold(usage):
    budget = make_budget()
    res = budget.reserve(make_payload())

    with pytest.raises(BudgetPoisoned, match="unusable usage report"):
        res.settle(usage)

    # The full provider-maximum hold is retained — the call WAS billed; we simply
    # cannot say how much.
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    assert budget.spend_so_far_usd <= budget.ceiling_usd      # invariant 1
    assert budget.spend_so_far_usd >= res.amount_usd          # invariant 2 (b <= A)
    # The handle was claimed exactly once — not left danglingly re-terminable.
    budget.assert_no_open_reservations()
    with pytest.raises(AssertionError, match="second terminal operation"):
        res.finalize_unknown("second terminal op")
    # And the budget is poisoned: no further calls are permitted.
    with pytest.raises(BudgetExhausted, match="poisoned"):
        budget.reserve(make_payload())


@pytest.mark.parametrize(
    "usage",
    [
        pytest.param(
            {"prompt_tokens": MODEL_MAX_CONTEXT_TOKENS + 1, "completion_tokens": 10},
            id="prompt_tokens_above_context_window",
        ),
        pytest.param(
            {"prompt_tokens": 10, "completion_tokens": MAX_COMPLETION_TOKENS + 1},
            id="completion_tokens_above_requested_cap",
        ),
    ],
)
def test_usage_above_provider_cap_poisons(usage):
    """The single observation that would FALSIFY the ceiling proof's own premise.

    The proof rests on two provider-enforced caps. A usage report above either one
    says the provider billed more than the limits it enforces — so the bound is not
    holding, and the only safe response is to stop the instant it is seen rather
    than continue on a bound shown not to hold.
    """
    budget = make_budget()
    res = budget.reserve(make_payload())

    with pytest.raises(BudgetPoisoned, match="unusable usage report"):
        res.settle(usage)

    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    assert budget.spend_so_far_usd <= budget.ceiling_usd
    with pytest.raises(BudgetExhausted, match="poisoned"):
        budget.reserve(make_payload())
    budget.assert_no_open_reservations()


def test_usage_exactly_at_the_provider_caps_is_bookable():
    # The boundary: AT the cap is legal (the provider's own limit), ABOVE it is not.
    budget = make_budget()
    res = budget.reserve(make_payload(user_text="x" * MODEL_MAX_CONTEXT_TOKENS))
    res.settle(
        {"prompt_tokens": MODEL_MAX_CONTEXT_TOKENS, "completion_tokens": MAX_COMPLETION_TOKENS}
    )
    assert budget.spend_so_far_usd == pytest.approx(
        usd(MODEL_MAX_CONTEXT_TOKENS, MAX_COMPLETION_TOKENS)
    )


def test_zero_token_usage_is_bookable():
    budget = make_budget()
    res = budget.reserve(make_payload())
    res.settle({"prompt_tokens": 0, "completion_tokens": 0})
    assert budget.spend_so_far_usd == pytest.approx(0.0)
    budget.assert_no_open_reservations()


def test_extra_usage_keys_are_ignored():
    # Real CompletionUsage.model_dump() carries total_tokens and details blocks.
    budget = make_budget()
    res = budget.reserve(make_payload())
    res.settle(
        {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
            "completion_tokens_details": {"reasoning_tokens": 150},
        }
    )
    assert budget.spend_so_far_usd == pytest.approx(usd(500, 200))


# --------------------------------------------------------------------------
# The lifecycle's `else` block is load-bearing, not stylistic
# --------------------------------------------------------------------------


def test_settle_failure_does_not_reach_terminal_for_exception():
    """§3's lifecycle puts settle() in an `else`, and that placement is asserted here.

    Python does not route an exception raised in an `else` block to that same
    `try`'s `except` clauses, so a BudgetPoisoned out of settle() cannot reach
    terminal_for_exception and double-terminate an already-terminal handle.
    """
    budget = make_budget()
    payload = make_payload()
    routed_to_except = []

    def stub_create(**kwargs):
        return StubResponse(usage=None)       # a response arrived, carrying no usage

    res = budget.reserve(payload)
    with pytest.raises(BudgetPoisoned):
        try:
            response = stub_create(**payload)
        except Exception as exc:              # pragma: no cover - the stub never raises
            routed_to_except.append(exc)
            terminal_for_exception(res, exc)
            raise
        else:
            res.settle(response.usage)

    # The `except` never ran, so the handle was terminated exactly once.
    assert routed_to_except == []
    budget.assert_no_open_reservations()
    assert budget.spend_so_far_usd == pytest.approx(PROVIDER_MAX_CALL_COST_USD)
    # A retry now reserves afresh against an already-poisoned budget and is stopped.
    with pytest.raises(BudgetExhausted, match="poisoned"):
        budget.reserve(make_payload())


def test_full_lifecycle_on_the_happy_path():
    """The §3 lifecycle verbatim: build once, reserve that exact dict, unpack the
    SAME dict into the call, terminate on every path."""
    budget = make_budget()
    seen_kwargs = {}

    def stub_create(**kwargs):
        seen_kwargs.update(kwargs)
        return StubResponse(usage=dict(BOOKABLE_USAGE))

    payload = build_request_payload(
        model="gpt-5.6-sol",
        system_text="sys",
        user_text="usr",
        max_completion_tokens=1_200,
        reasoning_effort=REASONING_EFFORT,
        schema=None,
    )
    res = budget.reserve(payload)
    try:
        response = stub_create(**payload)
    except Exception as exc:                  # pragma: no cover - the stub never raises
        terminal_for_exception(res, exc)
        raise
    else:
        res.settle(response.usage)

    # The dict reserved against and the kwargs sent are the SAME dict, never divergent.
    # Asserted by identity, not equality: value-equality would also pass against a
    # second, independently-built payload, which is exactly what §3 forbids ("never a
    # second, independently-built payload that could drift from what was reserved").
    assert seen_kwargs == payload
    assert seen_kwargs["messages"] is payload["messages"]
    assert budget.spend_so_far_usd == pytest.approx(usd(500, 200))
    budget.assert_no_open_reservations()
