"""The hard spend ceiling (§3) — a LEAF module.

**This module imports NOTHING from `mastra_prep`, and must not start.** That is
structural, not stylistic: `probe.py`, `judge.py` and `curate.py` all need
`SpendBudget` while `curate.py` imports `probe`/`judge`. An earlier draft homed
`SpendBudget` in `curate.py` and produced a genuine circular import
(`probe -> curate -> probe`) — partially-initialized modules and order-dependent
`NameError`s. Everything here is pure computation over dicts and floats, so the
module can be a leaf by construction. `tests/test_imports.py` asserts its
intra-package import set is empty.

**What guards the ceiling, and what does not.** The two dollar figures a
reservation carries do different jobs, and conflating them is how three earlier
versions of this module ended up with a ceiling that could be breached:

  * `Reservation.amount_usd` = `max_call_cost(payload)` — the PROVIDER-guaranteed
    maximum for the call (context window x price_in + max_completion_tokens x
    price_out). Both terms are limits OpenAI itself enforces, so **no estimate of
    ours appears in it**. `reserve()` holds this against the ceiling BEFORE the
    call fires. This, and only this, enforces the ceiling.
  * `Reservation.expected_max_usd` = our tight estimate, from
    `reservation_basis_tokens()`. It guards nothing. It is the **anomaly
    tripwire**: `settle()` poisons the budget when a real bill beats it, which
    catches OUR bugs (a call site reserving against different text than it sent,
    framing outgrowing the allowance, a billing change).

The ceiling's proof therefore depends on nothing of ours — not on
`REQUEST_OVERHEAD_ALLOWANCE_TOKENS` being big enough, not on `json.dumps`
resembling the wire format, not on the byte-per-token argument. See §3's proof.

**Deviations from §3's pinned code — three, each deliberate and each flagged for
an orchestrator ruling in P1.11's report.** §3 pins this module almost
line-by-line and that fidelity is a feature; these are the only departures:

  1. `_log` binds stdlib `logging` directly instead of calling `logging_.log()`.
     §3's code calls `log()`, but `logging_` is an intra-package module and this
     module's whole point is having NO intra-package imports (`test_imports.py`
     asserts the set is empty). §1 states `logging_.log()` is a thin wrapper over
     `logging.getLogger("mastra_prep").info(...)`, so this is the same channel.
  2. `__init__` rejects non-finite `ceiling_usd`/prices. The pinned code checks
     neither, and NaN defeats every comparison gate here (see the comment there).
     Without this the ceiling can be removed entirely via a `config.yaml` value.
  3. `_open` tracks a monotonic `Reservation.seq` rather than `id(reservation)`.
     Nothing holds a reference to a leaked handle, so CPython frees it and the
     next `reserve()` reuses the address — measured at 4,999/5,000, which made
     `assert_no_open_reservations()` silently miss the leak it exists to catch.

Deviations 2 and 3 are additive: for finite inputs and non-leaked reservations,
behaviour is identical to the pinned code.
"""

import json
import logging
import math
from dataclasses import dataclass

# §3's code calls `log()` from `logging_.py`, but §1 pins this module's
# intra-package imports as **None** and `test_imports.py` asserts that set is
# empty — importing `logging_` would break the one property this module exists to
# have. `logging_.log()` is specified (§1) as a thin wrapper over
# `logging.getLogger("mastra_prep").info(...)`, so emitting on that same logger
# is byte-identical on the progress channel at zero structural cost. See the
# task report for the spec conflict this resolves.
_log = logging.getLogger("mastra_prep").info

# The provider's own input ceiling. The API REJECTS (rather than truncates) a request
# whose input exceeds the model's context window, so no BILLED call can ever report
# prompt_tokens above this value.
#
# It need only be an UPPER bound on what the provider will accept. Setting it too HIGH
# only makes the arithmetic below more conservative (a lower effective ceiling, so the
# run stops earlier); setting it BELOW the pinned model's real context window would make
# the proof false. It is therefore pinned to the LARGEST window published anywhere in the
# GPT-5 family (verified 2026-07-16: documented windows across this family range from a
# 272k configured limit up to 1M), specifically so it cannot be an underestimate. Raise
# it via code review if a future pinned model documents a larger window; never lower it
# below that model's documented window.
MODEL_MAX_CONTEXT_TOKENS = 1_000_000

# A CODE CONSTANT, not a config key — deliberately. reasoning_effort is a dial on
# BASELINE STRENGTH: "low" makes the same pinned model reason less, which makes more
# probes fail, which grows the cleared set. That is goal #9's named rigging mode reached
# through a lever goal #9 never anticipated. Mirrored in template/src/config.ts and
# locked by a drift test (§8, P6.15), so curation and the scoreboard cannot silently
# measure the same model at different strengths.
REASONING_EFFORT = "medium"

# The pinned model's DOCUMENTED knowledge cutoff (OpenAI's own docs, verified
# 2026-07-16). It lives here because every ClearedRecord must carry it (§5's
# `model_cutoff` literal). Mirrored by template/src/config.ts's MODEL_CUTOFF and locked
# to it by a drift check (§2), like MODEL_ID and JUDGE_CONFIDENCE_FLOOR.
#
# EDITING THIS? It is cross-checked against MODEL_CUTOFFS below on every run
# (`load_settings()`, orchestrator D14): this must equal the documented cutoff of the
# model `config.yaml` actually pins. Changing the model means changing BOTH, then
# re-deriving CANDIDATE_CUTOFF_DATE (goal #3) — see MODEL_CUTOFFS for the full
# procedure.
#
# THE DATE BELOW IS DUPLICATED IN MODEL_CUTOFFS, AND THE DUPLICATION IS THE MECHANISM
# — do not "DRY" it away. These are two INDEPENDENT facts: which model is pinned, and
# what that model's documented cutoff is. They are stated separately precisely so
# `load_settings()` can assert them against each other and catch a swap that moved one
# and forgot the other. Collapsing this into
# `MODEL_CUTOFF = MODEL_CUTOFFS["openai/gpt-5.6-sol"]` would make that assertion
# `x == x` — a guard that cannot fire, which is the exact defect class D14 exists to
# close (and the drift check would then pass tautologically).
MODEL_CUTOFF = "2026-02-16"

# Model-router string -> that model's PROVIDER-DOCUMENTED knowledge cutoff.
# Orchestrator D14 — the mechanism behind goal #3's "MUST be re-derived".
#
# WHY A TABLE AND NOT A SENTENCE. §13 pins `model_router_string`'s only constraint as
# "must start with `openai/`", and goal #9 ACTIVELY INVITES the one-line swap ("anyone
# forking this — including Mastra — can swap providers by editing one line"). Nothing
# tied MODEL_CUTOFF to the model it describes, so a forker could swap to a
# LATER-cutoff model, forget MODEL_CUTOFF, and pass every check — while the candidate
# filter admitted documents from inside the new model's own training data, silently
# corrupting the one experiment this project exists to run. Verified by execution
# against the pre-fix code: the swap loaded cleanly and a 2026-04-01 record was
# admitted against a notionally 2026-06-01-cutoff model. goal #3's MUST had no
# mechanism, which is this project's signature defect class (see D8, D9, D13).
#
# `load_settings()` (§13) asserts MODEL_CUTOFF == MODEL_CUTOFFS[model_router_string]
# and raises on a model absent from this table, so the swap now FAILS CLOSED: you
# cannot change the model without confronting the cutoff, and once the cutoff is
# right, `candidates.assert_cutoff_margin` derives the correct filter date on its own.
#
# THIS IS NOT A CATALOGUE OF EVERY MODEL THAT EXISTS — deliberately. An entry is a
# CLAIM that someone read that model's documented cutoff from the provider's own docs.
# Adding one is a reviewed code change; guessing a date here defeats the whole point.
# It is seeded with the single entry goal #9 verifies (OpenAI's own docs, 2026-07-16).
# Note that goal #9's other documented-valid router string, the bare alias
# `openai/gpt-5.6`, is deliberately ABSENT: it resolves to Sol today, but pinning an
# alias's cutoff is a claim about whatever the alias points at TOMORROW, which is
# exactly the assumption this table exists to refuse. A forker using it gets the
# unknown-model error — the conservative, fail-closed direction.
#
# A dict of str literals adds NO import: this module is a pinned-empty leaf (§1,
# enforced by tests/test_imports.py's PINNED_EMPTY_LEAVES) and stays one.
#
# A PLAIN, MUTABLE dict, accepted deliberately. `candidates.ACTIONABLE_UPDATE_TYPES`
# is a frozenset on the argument that widening must require a reviewed code change,
# and that argument transfers here — but D14 pins this type as `dict[str, str]`, and
# the threat model is a SOURCE EDIT (a forker who can edit this line can edit any
# line), which no runtime immutability stops. MappingProxyType would buy nothing real
# and would break the tests that patch it. NOTE for anyone patching it in a test:
# `config.py` does `from .budget import MODEL_CUTOFFS`, so it holds its own NAME
# bound to this same dict OBJECT — mutate the object (`monkeypatch.setitem`), or
# patch `mastra_prep.config.MODEL_CUTOFFS`; rebinding `mastra_prep.budget.MODEL_CUTOFFS`
# would not be seen by `config.py`.
MODEL_CUTOFFS: dict[str, str] = {
    "openai/gpt-5.6-sol": "2026-02-16",
}

# The margin goal #3 buys past that cutoff: FOURTEEN days, counted INCLUSIVELY of the
# cutoff date itself (the cutoff date is day 1, so the first eligible publication date is
# day 14 — 2026-02-16 + 13 days = 2026-03-01, reproducing goal #3's locked date exactly).
# candidates.py::assert_cutoff_margin derives the cutoff date from these two constants
# rather than hardcoding a literal, so a model swap cannot silently corrupt the filter.
CUTOFF_MARGIN_DAYS = 14
CUTOFF_MARGIN_IS_INCLUSIVE = True   # documents the convention AT the constant, not 40 lines away

# Covers everything between "the bytes we serialized" and "the tokens the provider
# counts": per-message chat framing, SDK-injected default fields, and protocol
# envelope. Chat framing is a few tokens per message and the SDK's defaults are a
# handful of short JSON keys, so 1,024 tokens is roughly two orders of magnitude more
# than the real gap. It is a DECLARED ALLOWANCE, not a measurement — and it does not
# guard the ceiling (max_call_cost does). Reservation.settle() checks the real usage
# against it on every call, so it functions as an anomaly tripwire rather than as a
# trusted assumption.
REQUEST_OVERHEAD_ALLOWANCE_TOKENS = 1024

# gpt-5.6-sol, OpenAI published rates, verified 2026-07-16 — CODE CONSTANT FLOORS.
# Only ever raise these, via a code-reviewed change, if OpenAI's published rate changes.
PINNED_PRICE_INPUT_USD_PER_MILLION = 5.00
PINNED_PRICE_OUTPUT_USD_PER_MILLION = 30.00

# HTTP statuses OpenAI returns BEFORE running inference. The provider has explicitly
# told us it did not process the request, so releasing the reservation is grounded in
# the provider's own response — not in our optimism about what probably happened.
UNBILLED_STATUS_CODES = frozenset({400, 401, 403, 404, 409, 422, 429})


class BudgetExhausted(Exception):
    """The one exception type callers catch to mean 'stop the run'.

    EXACT raiser/catch contract, stated once, here:
      - SpendBudget.reserve() raises BudgetExhausted when the ceiling gate fails, or
        when the budget is already poisoned.
      - Reservation.settle() raises BudgetPoisoned (the subclass below) when it detects
        an estimate anomaly, and Reservation.finalize_unusable_usage() raises it when a
        usage report cannot be booked at all.
      - run_curation() and decide_scenario() catch BudgetExhausted — which, by
        subclassing, also catches BudgetPoisoned — and stop with
        stop_reason="spend_ceiling". No other module catches either type.
    """


class BudgetPoisoned(BudgetExhausted):
    """Raised when a call's ACTUAL cost exceeded what the tight estimate predicted, or
    when its usage report could not be booked at all. A subclass so
    run_curation/decide_scenario catch both uniformly as BudgetExhausted, while a test
    can distinguish 'ran out of budget' from 'an estimate was wrong'. NOTE this is a BUG
    DETECTOR, not the ceiling's enforcement — the ceiling is enforced entirely by
    reserve()'s provider-cap gate (see the proof in §3)."""


def build_request_payload(model: str, system_text: str, user_text: str,
                          max_completion_tokens: int, reasoning_effort: str,
                          schema: dict | None) -> dict:
    """The COMPLETE, SDK-READY kwargs dict — exactly what every real call site in
    §2/§3/§4 unpacks into openai.OpenAI().chat.completions.create(**payload): model,
    the full messages array (system + user, with their real role/content structure),
    reasoning effort, max_completion_tokens, and response_format/json_schema when this
    is a structured-output call (Stage B, Judge).

    This is the SDK's INPUT, not the wire request — the SDK serializes it itself and
    may add fields of its own; this distinction is why the overhead allowance exists
    and is checked. What it does guarantee is that every content-bearing byte the call
    carries is inside this dict.

    Every real call site builds this dict FIRST and reserves against it BEFORE
    unpacking it into the actual SDK call — the dict passed to reserve() and the
    kwargs passed to the SDK are never allowed to diverge, since a divergence would
    silently break the accounting.
    """
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_text},
                     {"role": "user", "content": user_text}],
        "reasoning_effort": reasoning_effort,
        "max_completion_tokens": max_completion_tokens,
    }
    if schema is not None:
        payload["response_format"] = {"type": "json_schema", "json_schema": schema}
    return payload


def estimate_tokens(text: str) -> int:
    """The one MATHEMATICALLY GUARANTEED upper bound on token count for arbitrary
    UTF-8 text under any BPE-family tokenizer with byte-level fallback (which every
    modern OpenAI tokenizer has, precisely to guarantee it can encode arbitrary
    input): a single token can NEVER span more than one byte in the worst case (the
    byte-fallback vocabulary exists exactly so no input requires MORE than 1
    token-per-byte) — therefore token_count(text) <= len(text.encode("utf-8"))
    ALWAYS, with no assumption about average token density.
    """
    return len(text.encode("utf-8"))


def reservation_basis_tokens(payload: dict) -> int:
    """Our TIGHT estimate of the call's input tokens: one token per UTF-8 byte of the
    COMPLETE SDK-ready kwargs dict, plus a declared conservative overhead allowance.

    This does NOT guard the ceiling (max_call_cost does, from the provider's own caps).
    It feeds Reservation.expected_max_usd — the ANOMALY TRIPWIRE that settle() checks
    the real usage against. It is deliberately tight for exactly that reason: a bound
    loose enough to be unfalsifiable would detect no bugs.

    It is deliberately NOT claimed to equal the transmitted wire request (the SDK
    serializes independently and may add framing/default fields; json.dumps' rendering
    and the wire bytes are related, not identical). The claim is narrower:

      (1) every content-bearing byte of the call (system_text, user_text, and the
          schema when present) appears at least once inside json.dumps(payload), and
      (2) no byte ever costs more than one token (estimate_tokens' byte-fallback
          argument), so content_tokens <= content_bytes <= this term, and
      (3) REQUEST_OVERHEAD_ALLOWANCE_TOKENS covers the remaining gap — chat framing,
          SDK-injected defaults, protocol envelope — with ~2 orders of magnitude of
          headroom.

    (1) and (2) are proofs; (3) is an allowance. If (3) is ever wrong, settle() raises
    BudgetPoisoned and the run halts — which is the intended behavior for "our model of
    the request no longer matches reality", and costs nothing beyond a stopped run,
    since the ceiling never depended on it.
    """
    return (estimate_tokens(json.dumps(payload, ensure_ascii=False))
            + REQUEST_OVERHEAD_ALLOWANCE_TOKENS)


@dataclass
class Reservation:
    """A single call's hold on the budget. EXACTLY ONE terminal operation must be
    invoked on it — settle(), release(), finalize_unknown(), or (from inside settle)
    finalize_unusable_usage(). A second call on the same handle raises.

    Why this type exists at all: the previous draft's reserve() returned a float and
    relied on the caller remembering to call record_actual(). record_actual() only ever
    ran on a RESPONSE — so a timeout, connection reset, or API error left the
    worst-case reservation permanently counted as spend, and the specified retry then
    reserved AGAIN on top of it. Spend was over-stated without bound across retries,
    the ledger no longer meant what the proof said it meant, and a few transient
    failures could exhaust an otherwise healthy run. Making the handle explicit turns
    "did every call account for itself?" into something assert_no_open_reservations()
    can answer.
    """

    amount_usd: float          # max_call_cost(payload) — held against the ceiling
    expected_max_usd: float    # the tight estimate — the anomaly tripwire
    max_completion_tokens: int # from the payload — one of the two caps usage is validated against
    budget: "SpendBudget"
    seq: int                   # this handle's identity in budget._open — see DEVIATION 3
    _terminal: bool = False

    def _claim_terminal(self, op: str) -> None:
        if self._terminal:
            raise AssertionError(f"reservation already terminated; {op}() is a second terminal operation")
        self._terminal = True
        # DEVIATION 3 from §3's pinned code (see the module docstring): `seq`, not
        # `id(self)`. `budget._open` holds ints, never references, so a LEAKED handle —
        # exactly what this audit exists to catch — is freed by refcounting the moment
        # it goes out of scope, and the next reserve() allocates its Reservation at the
        # same address. `_open.add(id(r))` is then a no-op on a set that already holds
        # that id, and terminating the NEW handle discards the leaked one's entry too:
        # the audit passes and the leak is invisible. Measured at 4,999/5,000 through
        # the real reserve() path. A monotonic counter cannot be recycled, so the audit
        # answers the question §3 says it answers.
        self.budget._open.discard(self.seq)

    def _usage_is_bookable(self, usage: object) -> bool:
        """Can this usage report be turned into a real cost? Requires a mapping with
        both token counts present as non-negative ints (bool excluded — it subclasses
        int in Python and would silently book as 0/1), each within the cap the provider
        itself enforces for it."""
        if not isinstance(usage, dict):
            return False
        for key, cap in (("prompt_tokens", MODEL_MAX_CONTEXT_TOKENS),
                         ("completion_tokens", self.max_completion_tokens)):
            v = usage.get(key)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > cap:
                return False
        return True

    def settle(self, usage: dict | None) -> None:
        """TERMINAL — the normal path: a response arrived with a usable usage report.
        Replaces the held provider-maximum with the call's REAL cost, returning the
        difference to the budget. After this, the call contributes exactly its true
        bill to spend_so_far_usd.

        Validation happens BEFORE _claim_terminal. An earlier draft claimed the handle
        first and then indexed usage — so an absent or malformed report raised a bare
        KeyError with the handle already spent, the call classified as nothing at all,
        the hold silently retained, and no path left to terminate it correctly (a
        second terminal op raises). Invalid usage now routes to a dedicated
        conservative terminal operation instead.

        On a valid report it runs the anomaly check: actual <= expected_max_usd. That
        comparison is against the TIGHT estimate, not against amount_usd (which the
        provider's caps make unfalsifiable). A violation means our model of the request
        is wrong — a call site reserved against different text than it sent, framing
        outgrew the allowance, or OpenAI now bills for something uncounted. Each is a
        real bug; the run poisons and stops rather than continuing on a ledger that no
        longer predicts anything. The CEILING is unaffected either way (see the proof).
        """
        if not self._usage_is_bookable(usage):
            self.finalize_unusable_usage(usage)   # claims terminal, poisons, and RAISES
        self._claim_terminal("settle")
        actual = (usage["prompt_tokens"] * self.budget._price_in
                  + usage["completion_tokens"] * self.budget._price_out) / 1_000_000
        self.budget.spend_so_far_usd += actual - self.amount_usd   # release the hold, book the truth
        if actual > self.expected_max_usd:
            self.budget._poisoned = True
            raise BudgetPoisoned(f"call cost ${actual:.4f}, tight estimate predicted at most "
                                 f"${self.expected_max_usd:.4f} — our request model is wrong; "
                                 f"budget poisoned, no further calls permitted")

    def finalize_unusable_usage(self, usage: object) -> None:
        """TERMINAL — a response arrived, but its usage report cannot be booked: absent,
        non-mapping, missing/non-integer/negative counts, or counts ABOVE the provider
        caps. Keeps the full provider-maximum hold (conservative, exactly like
        finalize_unknown — the call was billed; we simply cannot say how much) AND
        poisons the budget.

        Poisoning is right for both sub-cases, which are worth separating:
          - Structurally unreadable usage means our model of the API's RESPONSE is
            wrong. It will recur on the very next call, so continuing would only spend
            budget to relearn it.
          - Counts ABOVE MODEL_MAX_CONTEXT_TOKENS / max_completion_tokens mean a
            PREMISE OF THE CEILING PROOF is false: the provider billed more than the
            limits it enforces. That is the single observation that would invalidate
            the guarantee, and the only safe response is to stop the instant it is
            seen rather than continue on a bound shown not to hold.
        """
        self._claim_terminal("finalize_unusable_usage")
        self.budget._poisoned = True
        _log(f"reservation finalized at provider maximum (${self.amount_usd:.4f}) — unusable usage: {usage!r}")
        raise BudgetPoisoned(f"unusable usage report ({usage!r}): cannot book a real cost. Hold of "
                             f"${self.amount_usd:.4f} retained; budget poisoned, no further calls permitted")

    def release(self, reason: str) -> None:
        """TERMINAL — the provider CONFIRMED it did not bill: an UNBILLED_STATUS_CODES
        response, i.e. it rejected the request before inference. Returns the hold in
        full. This is the ONLY terminal operation that reduces spend without evidence
        of a bill, and it is permitted ONLY on that explicit provider signal — never on
        a timeout or a 5xx, where the request may well have run."""
        self._claim_terminal("release")
        self.budget.spend_so_far_usd -= self.amount_usd
        _log(f"reservation released (${self.amount_usd:.4f}): {reason}")

    def finalize_unknown(self, reason: str) -> None:
        """TERMINAL — billing status UNKNOWN: timeout, connection reset, 5xx, or any
        error that is not an explicit pre-inference rejection. The request may have run
        and been billed; no usage came back to prove otherwise. KEEPS the full
        provider-maximum hold as spend.

        This is deliberately the pessimistic direction. Over-counting stops the run
        early — safe, visible, and reported via stop_reason="spend_ceiling".
        Under-counting would silently spend past the ceiling, which is the one outcome
        this whole module exists to prevent. It also self-limits: a run suffering many
        unknown-billing calls exhausts its budget and stops, which is the correct
        response to a provider we are no longer able to account for.
        """
        self._claim_terminal("finalize_unknown")
        _log(f"reservation finalized at provider maximum (${self.amount_usd:.4f}) — {reason}")


def terminal_for_exception(reservation: Reservation, exc: Exception) -> None:
    """The ONE place an exception is mapped to a terminal operation. Chosen by what the
    provider actually told us, never by what we hope happened."""
    status = getattr(exc, "status_code", None)
    if status in UNBILLED_STATUS_CODES:
        reservation.release(f"provider rejected pre-inference (HTTP {status})")
    else:
        reservation.finalize_unknown(f"billing status unknown ({type(exc).__name__})")


class SpendBudget:
    """The single, shared, hard-ceiling accumulator. ONE instance is constructed per
    run_prep.py invocation and threaded through BOTH §7's scenario-decision trial and
    the main curation sweep — there is no separate 'trial budget'."""

    def __init__(self, ceiling_usd: float, price_in: float, price_out: float) -> None:
        # A configured price BELOW the pinned verified rate would make the "hard"
        # ceiling meaningless (a user could set price_input_per_million_usd: 0.001
        # and reserve near-infinite headroom against a real, unchanged bill) — this
        # constructor is one enforcement point (load_settings(), §13, ALSO validates
        # this at config-load time, before a SpendBudget is even constructed; both
        # checks exist because SpendBudget must be safe to construct directly in a
        # test or script without going through load_settings()).
        # DEVIATION 2 from §3's pinned code (see the module docstring). NaN defeats
        # EVERY comparison gate in this class, because every comparison against NaN is
        # False: `nan < PINNED_PRICE_*` passes the floor below; `spend + nan > ceiling`
        # makes reserve()'s gate never fire; and spend_so_far_usd is NaN forever after,
        # so every later call passes too. A NaN price or ceiling therefore removes the
        # ceiling ENTIRELY — the one outcome this module exists to prevent. This is a
        # LIVE path, not a theoretical one: PyYAML resolves `.nan` in config.yaml to
        # float("nan"), and §13's load_settings() price check is the same `<` shape, so
        # a NaN price passes both enforcement points. Checked FIRST so a non-finite
        # value gets this error rather than silently passing the floor.
        if not math.isfinite(ceiling_usd) or ceiling_usd <= 0:
            raise ValueError(
                f"ceiling_usd={ceiling_usd!r} must be a finite, positive dollar amount — a "
                f"non-finite ceiling is not a ceiling at all (every comparison against NaN "
                f"is False, so reserve()'s gate would never fire)")
        if not math.isfinite(price_in) or not math.isfinite(price_out):
            raise ValueError(
                f"price_in={price_in!r}/price_out={price_out!r} per million tokens must be "
                f"finite numbers — a NaN price passes the floor below (nan < x is False) and "
                f"then defeats reserve()'s ceiling gate")
        if price_in < PINNED_PRICE_INPUT_USD_PER_MILLION or price_out < PINNED_PRICE_OUTPUT_USD_PER_MILLION:
            raise ValueError(
                f"price_in=${price_in}/price_out=${price_out} per million tokens is below the "
                f"pinned verified floor (${PINNED_PRICE_INPUT_USD_PER_MILLION}/"
                f"${PINNED_PRICE_OUTPUT_USD_PER_MILLION}) — only raise the floor itself, via a "
                f"code-reviewed change to PINNED_PRICE_*_USD_PER_MILLION, if OpenAI's actual "
                f"published rate changes; never lower a config value below it")
        self.ceiling_usd = ceiling_usd
        self.spend_so_far_usd = 0.0
        self._price_in, self._price_out = price_in, price_out
        self._poisoned = False
        self._open: set[int] = set()   # seq numbers of reservations awaiting a terminal operation
        self._next_seq = 0             # monotonic — see DEVIATION 3 in the module docstring

    def max_call_cost(self, payload: dict) -> float:
        """The PROVIDER-GUARANTEED maximum bill for this call. Both terms are limits
        OpenAI itself enforces, so no estimate of ours appears in it:
          input  <= MODEL_MAX_CONTEXT_TOKENS  (a larger request is REJECTED, not billed)
          output <= payload["max_completion_tokens"]  (the API cannot exceed it)
        """
        return (MODEL_MAX_CONTEXT_TOKENS * self._price_in
                + payload["max_completion_tokens"] * self._price_out) / 1_000_000

    def reserve(self, payload: dict) -> Reservation:
        """Holds this call's PROVIDER-GUARANTEED maximum cost against the ceiling and
        returns a Reservation handle. Every reserve() MUST be followed by exactly one
        terminal operation on that handle (settle / release / finalize_unknown) — see
        Reservation above; the whole point of returning a handle rather than a float is
        that an un-terminated reservation is now a visible, testable state instead of a
        silently mis-stated ledger.

        RAISES BudgetExhausted in exactly two cases, and no others:
          1. the budget is poisoned (permanently, for this instance's lifetime), or
          2. spend_so_far_usd + max_call_cost(payload) > ceiling_usd.
        Called before EVERY API call, including retries — a retry is a NEW call with its
        own payload, its own reservation, and its own terminal operation.
        """
        if self._poisoned:
            raise BudgetExhausted("budget is poisoned by a prior accounting anomaly — no further calls permitted")
        amount = self.max_call_cost(payload)
        if self.spend_so_far_usd + amount > self.ceiling_usd:
            raise BudgetExhausted(f"reserving this call's provider-maximum ${amount:.4f} would "
                                  f"exceed the ${self.ceiling_usd:.2f} ceiling "
                                  f"(${self.spend_so_far_usd:.2f} already spent)")
        expected_max = (reservation_basis_tokens(payload) * self._price_in
                        + payload["max_completion_tokens"] * self._price_out) / 1_000_000
        self.spend_so_far_usd += amount        # held in full until a terminal operation
        self._next_seq += 1
        r = Reservation(amount_usd=amount, expected_max_usd=expected_max,
                        max_completion_tokens=payload["max_completion_tokens"], budget=self,
                        seq=self._next_seq)
        self._open.add(r.seq)
        return r

    def assert_no_open_reservations(self) -> None:
        """Called by run_prep.py in a `finally`, so it runs on EVERY exit path. An open
        reservation means some code path reserved and then neither settled, released,
        nor finalized — a bug that would leave spend over-stated. It is safe
        (over-statement never breaks the ceiling) but it is still wrong, and silence
        would hide it."""
        if self._open:
            raise AssertionError(f"{len(self._open)} reservation(s) never reached a terminal "
                                 f"operation — spend_so_far_usd is over-stated")
