"""Tests for `mastra_prep.config` — spec §13's config schema.

`load_settings()` is one of this project's two **enforcement points**, and the
tests are written against that job rather than against the API's shape. Every
constraint here exists because `config.yaml` is a user-editable file that sits
upstream of a real credit card and of the dataset's experimental validity:

  * **Non-finite guards (orchestrator D8 — a LIVE vulnerability, not a theory).**
    Every comparison against NaN returns `False`, so `if price < FLOOR: raise`
    *passes* a NaN price, and `spend + nan > ceiling` is then also `False` — the
    ceiling gate never fires and the run bills without bound. PyYAML resolves
    `.nan`/`.inf`/`-.inf` to real floats, so one word in a config file reaches
    the float. `SpendBudget.__init__` guards this (P1.11); `load_settings()` is
    the second enforcement point and must guard it too. **These tests load the
    non-finite values as literal `config.yaml` TEXT through PyYAML**, never as
    Python floats — the point is that a config edit reaches the float.
  * **The cutoff is DERIVED, never a literal** — `assert_cutoff_margin` (§2/P1.4).
  * **`snapshot_date` and `reasoning_effort` are NOT keys** (§13). Both are code
    constants precisely because they are levers on the date-rot gate and on
    baseline strength; an unknown key must be a hard `ValueError` so neither can
    be quietly reintroduced as a tunable.
  * **`target_set_size <= 200`** (goal #11's ceiling — may shrink, never grow) and
    **`judge_confidence_floor >= 0.7`** (the near-miss guard).

Also holds the **cross-language drift checks** (§8, §2 — P6.15, bottom of file):
`template/src/config.ts` and `template/src/judge/contract.ts` duplicate several of
`prep/`'s constants by design (goal #1 forbids importing across the language
boundary), and these are the only tests keeping the two copies equal.
"""
from __future__ import annotations

import math
import re
import textwrap
from datetime import date
from pathlib import Path

import pytest
import yaml

from mastra_prep.budget import (
    MODEL_CUTOFF,
    MODEL_CUTOFFS,
    PINNED_PRICE_INPUT_USD_PER_MILLION,
    PINNED_PRICE_OUTPUT_USD_PER_MILLION,
    REASONING_EFFORT,
)
from mastra_prep.config import Settings, load_settings

# The shipped config.yaml's own values (§13), used as the base for every case so
# that a test overriding ONE key is testing exactly that key.
BASE_CONFIG = {
    "model_router_string": "openai/gpt-5.6-sol",
    "annotations_path": "../../../carver-showcase/data/annotations.jsonl",
    "candidate_cutoff_date": '"2026-03-01"',
    "sample_seed": 42,
    "probe_batch_size": 40,
    "target_set_size": 200,
    "probe_max_records": 400,
    "scenario_trial_size": 30,
    "scenario_trial_min": 10,
    "price_input_per_million_usd": 5.00,
    "price_output_per_million_usd": 30.00,
    "total_spend_ceiling_usd": 120.0,
    "judge_confidence_floor": 0.7,
    "dotenv_path": ".env",
    "cleared_dir": "data/cleared",
    "scratch_dir": "data/scratch",
}

_PREP_DIR = Path(__file__).resolve().parents[1]
REPO_CONFIG_PATH = _PREP_DIR / "config.yaml"

# ── Cross-language drift checks (§8, §2, P6.15) — path constants ──
#
# `_PREP_DIR` is `prep/`; its parent is the project root that holds BOTH
# `prep/` and `template/`. These are read as plain TEXT below — never
# imported, never executed — which is the only safe crossing between two
# different languages and two different runtimes (goal #1/#13).
_PROJECT_ROOT = _PREP_DIR.parent
TEMPLATE_CONFIG_TS_PATH = _PROJECT_ROOT / "template" / "src" / "config.ts"
TEMPLATE_JUDGE_CONTRACT_TS_PATH = _PROJECT_ROOT / "template" / "src" / "judge" / "contract.ts"
JUDGE_SYSTEM_PROMPT_MD_PATH = _PREP_DIR / "prompts" / "judge_system.md"


_OMIT = object()  # sentinel: drop a key entirely


def write_config(tmp_path: Path, **overrides) -> str:
    """Render a real `config.yaml` TEXT file with `overrides` applied.

    Values are written as literal YAML text (not `yaml.dump`ed Python objects) so
    that a case like `price_input_per_million_usd=".nan"` exercises the exact
    path a hand-edited config takes: PyYAML's resolver turning the token `.nan`
    into a real float. A test that passed `float("nan")` directly would prove
    nothing about what a config edit can do.
    """
    values = {**BASE_CONFIG, **overrides}
    lines = [f"{key}: {value}" for key, value in values.items() if value is not _OMIT]
    path = tmp_path / "config.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


# ── The happy path — the SHIPPED config must load, or every negative test is vacuous ──


def test_shipped_config_yaml_loads(tmp_path):
    cfg = load_settings(write_config(tmp_path))

    assert isinstance(cfg, Settings)
    assert cfg.model_router_string == "openai/gpt-5.6-sol"
    assert cfg.candidate_cutoff_date == "2026-03-01"
    assert cfg.target_set_size == 200
    assert cfg.judge_confidence_floor == 0.7
    assert cfg.total_spend_ceiling_usd == 120.0


def test_the_real_repo_config_yaml_loads():
    """The actual `prep/config.yaml` this project ships — not a fixture copy.

    If a shipped value ever violates a floor this module enforces, the run fails
    at startup; this test says so at development time instead.
    """
    cfg = load_settings(str(REPO_CONFIG_PATH))

    assert cfg.candidate_cutoff_date == "2026-03-01"
    assert cfg.price_input_per_million_usd >= PINNED_PRICE_INPUT_USD_PER_MILLION
    assert cfg.price_output_per_million_usd >= PINNED_PRICE_OUTPUT_USD_PER_MILLION
    assert cfg.judge_confidence_floor >= 0.7
    assert cfg.target_set_size <= 200


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_settings(str(tmp_path / "nope.yaml"))


# ══ D8 — the non-finite guard. THE reason this module is an enforcement point. ══


def test_ieee754_premise_nan_defeats_every_bare_comparison():
    """The vulnerability D8 records, demonstrated rather than asserted.

    **This is a PREMISE PIN, not coverage.** It asserts IEEE-754 semantics and
    touches no project code, so it cannot fail from a `config.py` regression — the
    real coverage is the `.nan`/`.inf` battery below. It exists so that nobody
    deletes the `isfinite` guard as "redundant" without confronting why a `<` floor
    cannot do the job: **every** comparison against NaN is False, so the spec's
    `if price < PINNED_PRICE_INPUT: raise` shape passes a NaN price, and
    `spend + nan > ceiling` is False too — the ceiling gate never fires either.
    """
    nan = float("nan")

    assert (nan < PINNED_PRICE_INPUT_USD_PER_MILLION) is False   # the floor passes it
    assert (0.0 + nan > 120.0) is False                          # the ceiling never fires
    assert math.isfinite(nan) is False                           # ...but isfinite catches it


@pytest.mark.parametrize(
    "literal",
    [
        ".nan", ".inf", "-.inf", ".NaN", ".Inf", "+.inf", ".NAN",
        "!!float nan", "!!float inf",   # the EXPLICIT-TAG route to the same floats
        "1.0e+400", "-1.0e+400",        # overflow-to-inf: does not LOOK non-finite
    ],
)
@pytest.mark.parametrize(
    "key",
    ["price_input_per_million_usd", "price_output_per_million_usd", "total_spend_ceiling_usd"],
)
def test_non_finite_money_values_are_rejected_from_real_yaml_text(tmp_path, key, literal):
    """PyYAML resolves each of these tokens to a real float (verified by execution).
    A NaN price or ceiling removes the spend ceiling entirely (D8), so
    `load_settings()` must reject it before `SpendBudget` is ever constructed.

    The battery deliberately spans all three routes a non-finite float can take
    into the config, because only the first is obvious:
      * the plain tokens (`.nan`, `.inf`, and their case/sign variants);
      * the explicit YAML tag (`!!float nan`), which bypasses the plain resolver;
      * **exponent overflow** (`1.0e+400` -> `inf`), which does not look non-finite
        at all — a plausible fat-finger, not an attack. (Note PyYAML's own quirk:
        `1e999` without a `.` and a signed exponent stays a *string*, so it is
        caught by the type check instead. The guard must not depend on which.)
    """
    path = write_config(tmp_path, **{key: literal})

    with pytest.raises(ValueError, match="finite"):
        load_settings(path)


@pytest.mark.parametrize(
    "key",
    ["price_input_per_million_usd", "price_output_per_million_usd", "total_spend_ceiling_usd",
     "judge_confidence_floor"],
)
def test_int_too_large_for_float_raises_value_error_not_overflow_error(tmp_path, key):
    """An int YAML resolves happily but `float()` cannot represent: `float(10**400)`
    raises **OverflowError**, which is NOT a subclass of ValueError and would
    escape `load_settings()` as an unhandled traceback rather than the named
    startup error this module's contract promises.

    Found by probing the guard with adversarial input rather than by reading it —
    the same method that found D8. Not a spend risk (the run dies either way, and
    dies before any call), but a guard that raises the wrong exception type is a
    guard whose contract is not what it says.
    """
    path = write_config(tmp_path, **{key: "9" * 400})

    with pytest.raises(ValueError, match=key):
        load_settings(path)


@pytest.mark.parametrize(
    "literal", [".nan", ".inf", "-.inf", ".NaN", ".Inf", "+.inf", ".NAN", "1.0e+400", "-1.0e+400"]
)
def test_the_yaml_tokens_really_do_become_non_finite_floats(tmp_path, literal):
    """Guards the guard: if PyYAML stopped resolving these to floats, the battery
    above would pass vacuously against plain strings rejected by the type check —
    green for the wrong reason, with the isfinite branch never exercised.
    """
    loaded = yaml.safe_load(
        Path(write_config(tmp_path, price_input_per_million_usd=literal)).read_text()
    )
    value = loaded["price_input_per_million_usd"]

    assert isinstance(value, float), f"{literal!r} must reach the float, not stop at str"
    assert not math.isfinite(value)


@pytest.mark.parametrize("literal", [".nan", ".inf", "-.inf"])
def test_non_finite_judge_confidence_floor_is_rejected(tmp_path, literal):
    """Not named in D8, but the same class: a NaN floor makes every
    `confidence >= floor` comparison False. It fails in the SAFE direction (it
    admits nothing), but a meaningless float has no business reaching the judge.
    """
    with pytest.raises(ValueError, match="finite"):
        load_settings(write_config(tmp_path, judge_confidence_floor=literal))


# ══ Prices — the pinned floor (goal: never shrink the effective ceiling) ══


@pytest.mark.parametrize("price", [4.99, 0.001, 0.0, -5.0])
def test_price_input_below_the_pinned_floor_raises(tmp_path, price):
    # match= names the FLOOR message, not just the key: the key name also appears
    # in the type error, so a looser regex would pass even if the floor vanished.
    with pytest.raises(ValueError, match="below the pinned floor"):
        load_settings(write_config(tmp_path, price_input_per_million_usd=price))


@pytest.mark.parametrize("price", [29.99, 0.001, 0.0, -30.0])
def test_price_output_below_the_pinned_floor_raises(tmp_path, price):
    with pytest.raises(ValueError, match="below the pinned floor"):
        load_settings(write_config(tmp_path, price_output_per_million_usd=price))


def test_prices_at_and_above_the_pinned_floor_pass(tmp_path):
    """The one legitimate override: OpenAI's published rate going UP."""
    at_floor = load_settings(write_config(tmp_path))
    above = load_settings(
        write_config(tmp_path, price_input_per_million_usd=7.5, price_output_per_million_usd=45.0)
    )

    assert at_floor.price_input_per_million_usd == PINNED_PRICE_INPUT_USD_PER_MILLION
    assert at_floor.price_output_per_million_usd == PINNED_PRICE_OUTPUT_USD_PER_MILLION
    assert above.price_input_per_million_usd == 7.5


# ══ The spend ceiling ══


@pytest.mark.parametrize("ceiling", [0.0, -1.0, -120.0])
def test_non_positive_spend_ceiling_raises(tmp_path, ceiling):
    with pytest.raises(ValueError, match="must be > 0"):
        load_settings(write_config(tmp_path, total_spend_ceiling_usd=ceiling))


def test_lowering_the_spend_ceiling_is_allowed(tmp_path):
    """A lower ceiling only ever stops a run earlier, which is always safe (§13)."""
    cfg = load_settings(write_config(tmp_path, total_spend_ceiling_usd=10.0))

    assert cfg.total_spend_ceiling_usd == 10.0


# ══ candidate_cutoff_date — the DERIVATION, via assert_cutoff_margin (P1.4) ══


def test_candidate_cutoff_date_at_the_derived_floor_passes(tmp_path):
    cfg = load_settings(write_config(tmp_path, candidate_cutoff_date='"2026-03-01"'))

    assert cfg.candidate_cutoff_date == "2026-03-01"


@pytest.mark.parametrize("earlier", ['"2026-02-28"', '"2026-02-16"', '"2026-01-01"'])
def test_candidate_cutoff_date_below_the_derived_floor_raises(tmp_path, earlier):
    """goal #3's "NEVER loosen it to grow the pool", enforced at startup."""
    with pytest.raises(ValueError, match="candidate_cutoff_date"):
        load_settings(write_config(tmp_path, candidate_cutoff_date=earlier))


def test_config_cutoff_must_equal_the_code_constant(tmp_path):
    """`is_candidate(rec)`'s pinned signature cannot receive the config value, so
    the filter reads `CANDIDATE_CUTOFF_DATE` and this key is otherwise INERT.

    An earlier version of this file asserted that a *more conservative* cutoff
    (`2026-04-01`) "is allowed", on the reasoning that the floor permits
    tightening. It does — but tightening the config key tightened **nothing**: the
    pool was still selected on 2026-03-01, and the test asserted only that a
    dataclass field held a string. That is this project's signature defect (a
    claim standing over no mechanism) inside a test written to prevent it.

    Tightening is still permitted; it just requires moving BOTH, which is a
    reviewed code change — the anti-padding posture goal #11 asks for anyway.
    """
    with pytest.raises(ValueError, match="CANDIDATE_CUTOFF_DATE"):
        load_settings(write_config(tmp_path, candidate_cutoff_date='"2026-04-01"'))


def test_tightening_both_the_constant_and_the_config_is_allowed(tmp_path, monkeypatch):
    """The FLOOR's asymmetry (goal #3), demonstrated properly: more conservative is
    always fine — provided the value the filter uses moves with it.
    """
    monkeypatch.setattr("mastra_prep.config.CANDIDATE_CUTOFF_DATE", "2026-04-01")

    cfg = load_settings(write_config(tmp_path, candidate_cutoff_date='"2026-04-01"'))

    assert cfg.candidate_cutoff_date == "2026-04-01"


def test_load_settings_delegates_the_cutoff_to_assert_cutoff_margin(monkeypatch, tmp_path):
    """The floor must come from `candidates.assert_cutoff_margin` — i.e. from
    `MODEL_CUTOFF + CUTOFF_MARGIN_DAYS` — and not be re-implemented here as a
    literal. Simulating §8's advertised one-line model swap to a LATER cutoff must
    make the unchanged shipped date raise; a `config.py` carrying its own hardcoded
    "2026-03-01" would sail straight through this.
    """
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2026-06-01")

    with pytest.raises(ValueError, match="re-deriv"):
        load_settings(write_config(tmp_path, candidate_cutoff_date='"2026-03-01"'))


# ══ MODEL_CUTOFF <-> MODEL_ID — V9's true residual (orchestrator D14) ══
#
# §13 pins `model_router_string`'s ONLY constraint as "must start with `openai/`",
# and goal #9 ACTIVELY INVITES the one-line swap ("anyone forking this — including
# Mastra — can swap providers by editing one line"). goal #3 says the candidate date
# "MUST be re-derived from the new model's documented cutoff". Nothing connected the
# two: a forker could swap to a LATER-cutoff model, forget `MODEL_CUTOFF`, and every
# check passed while the filter admitted documents from inside the new model's own
# training data. D13 wired the config key to the constant the filter reads; this is
# the other half — wiring the cutoff to the MODEL.
#
# Verified against the pre-fix code, not argued: `load_settings()` accepted
# `model_router_string: openai/gpt-9-future` with `candidate_cutoff_date: 2026-03-01`
# and `is_candidate()` then ADMITTED a 2026-04-01 record — inside a 2026-06-01-cutoff
# model's training window.


def test_shipped_model_and_its_documented_cutoff_pass_unchanged(tmp_path):
    """TIGHTEN-ONLY, pinned: D14 must change no shipping value. The shipped pairing
    (`openai/gpt-5.6-sol` + `MODEL_CUTOFF` 2026-02-16) still loads, and still derives
    the locked 2026-03-01 filter date.
    """
    cfg = load_settings(write_config(tmp_path))

    assert cfg.model_router_string == "openai/gpt-5.6-sol"
    assert MODEL_CUTOFFS[cfg.model_router_string] == MODEL_CUTOFF == "2026-02-16"
    assert cfg.candidate_cutoff_date == "2026-03-01"


def test_unknown_model_raises_value_error(tmp_path):
    """`load_settings()` has a DOCUMENTED error contract (`ValueError` for any bad
    value). A bare `KeyError` out of `MODEL_CUTOFFS[...]` would not be that contract —
    D13 caught an `OverflowError` escaping this same function for this same reason.

    `pytest.raises(ValueError)` IS that assertion, in full: `KeyError` inherits
    `LookupError`, so a `KeyError` cannot satisfy this and the test fails. An earlier
    draft added `assert not isinstance(excinfo.value, KeyError)` underneath, which
    reads like extra rigour but is unfalsifiable — the two hierarchies are disjoint, so
    the line could never fire. A dead assertion carrying the test's whole point is this
    project's signature defect (a claim standing over no mechanism) inside a test
    written to prevent it — the same irony `test_config_cutoff_must_equal_the_code_constant`
    records about an earlier draft of this file.
    """
    with pytest.raises(ValueError):
        load_settings(write_config(tmp_path, model_router_string="openai/gpt-9-future"))


def test_unknown_model_error_names_the_model_and_the_whole_remedy(tmp_path):
    """The error is the mechanism: it must tell a forker who has never read D14 what
    to do. Naming the model, the table to extend, the constant to re-derive, and the
    goal ruling that requires it.
    """
    with pytest.raises(ValueError) as excinfo:
        load_settings(write_config(tmp_path, model_router_string="openai/gpt-9-future"))

    message = str(excinfo.value)
    assert "openai/gpt-9-future" in message      # WHICH model
    assert "MODEL_CUTOFFS" in message            # the table to add it to
    assert "CANDIDATE_CUTOFF_DATE" in message    # what to re-derive
    assert "goal #3" in message                  # the ruling that requires it


def test_model_in_the_table_but_model_cutoff_forgotten_raises(tmp_path, monkeypatch):
    """**The exploit D14 exists to kill**, exactly as a forker would reach it: add the
    new model and its real (later) documented cutoff to the table, swap the one line
    goal #9 invites — and FORGET `MODEL_CUTOFF`, which every downstream date derives
    from. Pre-fix this loaded cleanly and corrupted the pool in silence.
    """
    monkeypatch.setitem(MODEL_CUTOFFS, "openai/gpt-9-future", "2026-06-01")

    with pytest.raises(ValueError) as excinfo:
        load_settings(write_config(tmp_path, model_router_string="openai/gpt-9-future"))

    message = str(excinfo.value)
    assert "MODEL_CUTOFF" in message
    assert "2026-02-16" in message   # the stale value
    assert "2026-06-01" in message   # the documented one it must become


def test_a_malformed_table_cutoff_is_named_at_the_table(tmp_path, monkeypatch):
    """A forker's `"openai/x": "June 1 2026"` passes both string comparisons above and
    would otherwise die inside `candidates._derived_floor()` on `date.fromisoformat` —
    in-contract (a ValueError escapes) but naming neither `MODEL_CUTOFFS` nor the
    remedy, at exactly the moment the forker is mid-swap and needs both.
    """
    monkeypatch.setitem(MODEL_CUTOFFS, "openai/gpt-9-future", "June 1 2026")
    monkeypatch.setattr("mastra_prep.config.MODEL_CUTOFF", "June 1 2026")

    with pytest.raises(ValueError, match="MODEL_CUTOFFS"):
        load_settings(write_config(tmp_path, model_router_string="openai/gpt-9-future"))


def test_the_stale_cutoff_error_precedes_the_derivations_unsafe_advice(tmp_path, monkeypatch):
    """Pins the ORDER of the two gates — which is about the ADVICE a broken config
    gets, not about whether it is caught (either order catches it; both raise).

    D13's lesson is that an operator who COMPLIES with a wrong error message converts
    a loud failure into a silent corruption. `assert_cutoff_margin` derives its floor
    FROM `MODEL_CUTOFF` — so with a stale `MODEL_CUTOFF`, running it first would
    announce "the earliest defensible candidate date is 2026-03-01" while the pinned
    model's real documented cutoff is 2026-06-01. Comply with that and you set a filter
    date inside the new model's training data, believing a startup check blessed it.

    So the message must name the ROOT CAUSE (`MODEL_CUTOFF` disagrees with the table),
    never the floor derived from the stale value.
    """
    monkeypatch.setitem(MODEL_CUTOFFS, "openai/gpt-9-future", "2026-06-01")

    with pytest.raises(ValueError) as excinfo:
        load_settings(write_config(
            tmp_path, model_router_string="openai/gpt-9-future",
            candidate_cutoff_date='"2026-01-01"'))   # also below the derived floor

    message = str(excinfo.value)
    assert "MODEL_CUTOFFS" in message      # the root cause...
    assert "2026-03-01" not in message     # ...never the floor derived from the stale cutoff


def test_a_correctly_completed_model_swap_is_still_caught_by_the_derivation(tmp_path, monkeypatch):
    """COMPOSITION coverage, not exploit coverage — it passes with D14 reverted, since
    `assert_cutoff_margin` (D13) is what fires here. It earns its place by pinning that
    the two gates leave NO GAP between them, which neither test proves alone.

    A forker who does the FIRST half correctly (new model in the table, `MODEL_CUTOFF`
    moved to match) but not the second (re-deriving the filter date) must still fail
    closed: 2026-03-01 is inside a 2026-06-01 model's training window.
    """
    monkeypatch.setitem(MODEL_CUTOFFS, "openai/gpt-9-future", "2026-06-01")
    monkeypatch.setattr("mastra_prep.config.MODEL_CUTOFF", "2026-06-01")
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2026-06-01")

    with pytest.raises(ValueError, match="re-deriv"):
        load_settings(write_config(tmp_path, model_router_string="openai/gpt-9-future"))


def test_a_fully_completed_swap_lands_on_the_correctly_tightened_floor(tmp_path, monkeypatch):
    """The GREEN path — also not exploit coverage (it passes with D14 reverted). A gate
    that blocks everything is useless, so this pins that a correctly-completed swap
    still works and lands on the TIGHTENED date rather than the old, now-unsafe one.

    It demonstrates one path THROUGH. It establishes nothing about paths AROUND — an
    earlier name ("the swap cannot be completed without confronting the cutoff") claimed
    exactly that, which no single test can show. The exploit coverage is the three tests
    above.
    """
    monkeypatch.setitem(MODEL_CUTOFFS, "openai/gpt-9-future", "2026-06-01")
    monkeypatch.setattr("mastra_prep.config.MODEL_CUTOFF", "2026-06-01")
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2026-06-01")
    monkeypatch.setattr("mastra_prep.config.CANDIDATE_CUTOFF_DATE", "2026-06-14")
    monkeypatch.setattr("mastra_prep.candidates._CANDIDATE_CUTOFF", date(2026, 6, 14))

    cfg = load_settings(write_config(
        tmp_path, model_router_string="openai/gpt-9-future",
        candidate_cutoff_date='"2026-06-14"'))

    # 2026-06-01 + 14d inclusive = 2026-06-14 — the SAME derivation, a later model.
    assert cfg.candidate_cutoff_date == "2026-06-14"


# ══ Anti-padding: the keys that MUST NOT exist ══


def test_settings_has_no_snapshot_date():
    """`SNAPSHOT_DATE` is `candidates.py`'s code constant (§2/§13), never a key.

    An earlier draft exposed it here as a plain ISO-date key, which would have let
    a user set `"3000-01-01"` and silently defeat the date-rot upper bound — and
    the corpus really does carry dates out to 2569. The field must not exist at
    all: absence is the mechanism.
    """
    assert not hasattr(Settings, "snapshot_date")
    assert "snapshot_date" not in Settings.__dataclass_fields__


def test_settings_has_no_reasoning_effort():
    """`REASONING_EFFORT` is `budget.py`'s code constant (§3/§13). It is a dial on
    BASELINE STRENGTH: "low" makes the same pinned model reason less, which makes
    more probes fail, which grows the yield — goal #9's named rigging mode reached
    through a lever goal #9 never anticipated.
    """
    assert not hasattr(Settings, "reasoning_effort")
    assert "reasoning_effort" not in Settings.__dataclass_fields__


@pytest.mark.parametrize(
    "sneaky_key, value",
    [
        ("snapshot_date", '"3000-01-01"'),
        ("reasoning_effort", "low"),
        ("some_typo_key", "1"),
    ],
)
def test_unknown_config_key_raises(tmp_path, sneaky_key, value):
    """Proving neither constant can be reintroduced as a tunable: an unknown key
    is a hard error, not a silently ignored line.
    """
    path = write_config(tmp_path, **{sneaky_key: value})

    with pytest.raises(ValueError, match=sneaky_key):
        load_settings(path)


def test_missing_required_key_raises(tmp_path):
    path = write_config(tmp_path, judge_confidence_floor=_OMIT)

    with pytest.raises(ValueError, match="judge_confidence_floor"):
        load_settings(path)


# ══ judge_confidence_floor — the near-miss guard (goal, §4) ══


@pytest.mark.parametrize("floor", [0.5, 0.69, 0.0, -1.0])
def test_judge_confidence_floor_below_0_7_raises(tmp_path, floor):
    with pytest.raises(ValueError, match="judge_confidence_floor"):
        load_settings(write_config(tmp_path, judge_confidence_floor=floor))


@pytest.mark.parametrize("floor", [0.7, 0.9, 1.0])
def test_judge_confidence_floor_at_or_above_0_7_passes(tmp_path, floor):
    cfg = load_settings(write_config(tmp_path, judge_confidence_floor=floor))

    assert cfg.judge_confidence_floor == floor


def test_judge_confidence_floor_above_1_raises(tmp_path):
    """A floor above 1.0 admits nothing at all — never a legitimate setting."""
    with pytest.raises(ValueError, match="judge_confidence_floor"):
        load_settings(write_config(tmp_path, judge_confidence_floor=1.5))


# ══ target_set_size — goal #11's ceiling: may shrink, never grow ══


def test_target_set_size_201_raises(tmp_path):
    with pytest.raises(ValueError, match="target_set_size"):
        load_settings(write_config(tmp_path, target_set_size=201))


@pytest.mark.parametrize("size", [1, 30, 200])
def test_target_set_size_within_the_ceiling_passes(tmp_path, size):
    """goal #11: "The set size is a ceiling and may be freely reduced." A
    30-record set of proven failures is a success.
    """
    cfg = load_settings(write_config(tmp_path, target_set_size=size))

    assert cfg.target_set_size == size


@pytest.mark.parametrize("size", [0, -1])
def test_non_positive_target_set_size_raises(tmp_path, size):
    with pytest.raises(ValueError, match="target_set_size"):
        load_settings(write_config(tmp_path, target_set_size=size))


# ══ scenario_trial_min / _size (§7's sufficiency floor) ══


@pytest.mark.parametrize("trial_min", [0, -1, 31])
def test_scenario_trial_min_outside_its_range_raises(tmp_path, trial_min):
    with pytest.raises(ValueError, match="scenario_trial_min"):
        load_settings(write_config(tmp_path, scenario_trial_min=trial_min))


@pytest.mark.parametrize("trial_min", [1, 10, 30])
def test_scenario_trial_min_within_range_passes(tmp_path, trial_min):
    cfg = load_settings(write_config(tmp_path, scenario_trial_min=trial_min))

    assert cfg.scenario_trial_min == trial_min


# ══ Remaining key constraints (§13's table) ══


@pytest.mark.parametrize("router", ["anthropic/claude-opus-4", "gpt-5.6-sol", "openai:gpt-5.6-sol", "OPENAI/gpt-5.6-sol"])
def test_model_router_string_must_start_with_openai(tmp_path, router):
    """goal #9: OpenAI is the only provider prep calls, and the Anthropic API is
    explicitly out of scope.
    """
    with pytest.raises(ValueError, match="model_router_string"):
        load_settings(write_config(tmp_path, model_router_string=router))


@pytest.mark.parametrize("bad", [0, -1, -40])
@pytest.mark.parametrize("key", ["probe_batch_size", "probe_max_records", "scenario_trial_size"])
def test_positive_int_keys_reject_zero_and_negatives(tmp_path, key, bad):
    with pytest.raises(ValueError, match=key):
        load_settings(write_config(tmp_path, **{key: bad}))


@pytest.mark.parametrize(
    "key, bad",
    [
        ("sample_seed", "not-an-int"),
        ("target_set_size", "true"),          # YAML bool; bool is an int in Python
        ("probe_batch_size", "1.5"),
        ("annotations_path", "42"),
        ("candidate_cutoff_date", "20260301"),
        ("total_spend_ceiling_usd", "'120.0'"),
    ],
)
def test_wrong_typed_values_raise(tmp_path, key, bad):
    with pytest.raises(ValueError, match=key):
        load_settings(write_config(tmp_path, **{key: bad}))


def test_empty_config_file_raises(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        load_settings(str(path))


def test_non_mapping_config_file_raises(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent("- just\n- a\n- list\n"), encoding="utf-8")

    with pytest.raises(ValueError):
        load_settings(str(path))


# ══ Cross-language drift checks (§8, §2 — P6.15) ══
#
# The two halves duplicate these constants DELIBERATELY (goal #1 forbids
# `template/` importing from `prep/`, or vice versa — see test_imports.py and
# `test_never_imports_carver_showcase`'s sibling rule). Nothing else keeps
# them equal, so these five tests are the entire mechanical defence for
# `MODEL_ID`, `MODEL_CUTOFF`, `JUDGE_CONFIDENCE_FLOOR`, `REASONING_EFFORT` and
# `JUDGE_SYSTEM_PROMPT` — the five constants P6.15 (plus orchestrator D27's
# addendum) names. `config.ts` pins two further mirrors this task does not
# cover, `SNAPSHOT_DATE` and `MAX_OUTPUT_TOKENS`: out of P6.15's stated scope,
# not an oversight — see the plan task before adding to this list.
#
# Every check reads `template/src/*.ts` as PLAIN TEXT via `.read_text()` and
# regex-extracts a literal — never `import`, never executes a line of
# TypeScript. That is the one safe crossing between two languages and two
# venvs, and it is the identical trick `generate_template_config.py` (§7) uses
# to WRITE these files in the first place. The complementary half of
# `test_model_id_matches_template` — that the TS literal actually KEEPS the
# `openai/` prefix rather than dropping it — is asserted TS-side, by
# `config.test.ts`'s `MODEL_ID.startsWith("openai/")` case; this test strips
# the prefix from both sides deliberately (see its docstring) and so cannot
# see that half on its own.
#
# `test_reasoning_effort_matches_template` and `test_judge_system_prompt_matches_template`
# also protect against goal #9's named rigging modes: a `template/`-only edit to
# `REASONING_EFFORT` would weaken the SAME pinned model without touching
# `budget.py` (more probes would fail there, growing the cleared set, while the
# runtime scoreboard silently measured a stronger judge/agent than curation
# selected against); a drifted `JUDGE_SYSTEM_PROMPT` would mean curation and the
# runtime scoreboard no longer ask the judge the same question, so the
# scoreboard would measure something other than what the dataset was selected
# for — and nothing would say so.


def _extract_ts_string_literal(path: Path, name: str) -> str:
    """Regex-extracts an `export const {name} = "..."` string literal from a
    TS file read as plain text (never imported, never executed — goal #1).

    Anchored to the START of a (possibly indented) line via `re.MULTILINE`, so
    a commented-out or example declaration (`// export const MODEL_ID = ...`)
    cannot match — a `//`-prefixed line is never `^\\s*export const`. Also
    asserts there is exactly ONE such declaration: `config.ts`'s own docstring
    claims "no second literal anywhere" for `MODEL_ID`, and this is what makes
    that claim a checked property rather than an assertion.

    Tolerates an optional `: type` annotation
    (`DEMO_TRIGGER_RECORD_ID: string = "..."`) and a trailing `as const`
    (`REASONING_EFFORT = "medium" as const`), since neither changes what value
    is actually pinned.
    """
    pattern = rf'^\s*export const {name}(?::\s*\w+)?\s*=\s*"([^"]*)"'
    matches = re.findall(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not matches:
        raise AssertionError(
            f"could not find an `export const {name} = \"...\";` string literal in "
            f"{path} — has the constant been renamed, removed, or changed type?"
        )
    if len(matches) > 1:
        raise AssertionError(
            f"found {len(matches)} `export const {name} = \"...\";` declarations in "
            f"{path} (expected exactly one) — {matches!r}"
        )
    return matches[0]


def _extract_ts_numeric_literal(path: Path, name: str) -> float:
    """The numeric sibling of `_extract_ts_string_literal` — deliberately a
    SEPARATE function, not a string-then-number fallback. A fallback would let
    `export const JUDGE_CONFIDENCE_FLOOR = "0.7";` (a STRING) false-pass this
    check via `float("0.7") == 0.7`, silently no longer proving the TS side is
    the number `JUDGE_CONFIDENCE_FLOOR` (§9c) is typed as everywhere it is
    used. Same anchoring and uniqueness discipline as the string extractor.
    """
    pattern = rf'^\s*export const {name}(?::\s*\w+)?\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)\b'
    matches = re.findall(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if not matches:
        raise AssertionError(
            f"could not find an `export const {name} = <number>;` literal in "
            f"{path} — has the constant been renamed, removed, or changed type?"
        )
    if len(matches) > 1:
        raise AssertionError(
            f"found {len(matches)} `export const {name} = <number>;` declarations in "
            f"{path} (expected exactly one) — {matches!r}"
        )
    return float(matches[0])


def test_model_id_matches_template():
    """§8's drift check. Both sides strip the `openai/` prefix before comparing:
    the TS literal keeps it (goal #9's "one shared pinned constant" claim), while
    prep's OpenAI-SDK call sites strip it before passing `model=` — so the two
    representations differ by that prefix even when the pinned model agrees.
    `config.test.ts` separately asserts the TS side actually keeps the prefix.
    """
    ts_model_id = _extract_ts_string_literal(TEMPLATE_CONFIG_TS_PATH, "MODEL_ID")
    cfg = load_settings(str(REPO_CONFIG_PATH))

    assert ts_model_id.removeprefix("openai/") == cfg.model_router_string.removeprefix("openai/")


def test_model_cutoff_matches_template():
    """Locks `template/src/config.ts`'s `MODEL_CUTOFF` to `budget.py`'s — the
    same constant D14's `MODEL_CUTOFFS` table cross-checks against
    `model_router_string` on the prep side alone. This is the OTHER side: the
    template's copy must track whichever value prep actually ships.
    """
    ts_cutoff = _extract_ts_string_literal(TEMPLATE_CONFIG_TS_PATH, "MODEL_CUTOFF")

    assert ts_cutoff == MODEL_CUTOFF


def test_judge_confidence_floor_matches_template():
    """§9c's drift check. `judge_confidence_floor` has no code-constant home on
    the prep side (it is a `config.yaml` key, validated by `_validate` above);
    the template's copy must track the SHIPPED config value, not just the
    `MIN_JUDGE_CONFIDENCE_FLOOR` code floor both sides also enforce.
    """
    ts_floor = _extract_ts_numeric_literal(TEMPLATE_CONFIG_TS_PATH, "JUDGE_CONFIDENCE_FLOOR")
    cfg = load_settings(str(REPO_CONFIG_PATH))

    assert ts_floor == cfg.judge_confidence_floor


def test_reasoning_effort_matches_template():
    """§3/§8's drift check on the anti-padding lever goal #9 never named:
    `reasoning_effort` is a CODE CONSTANT precisely because it is a dial on
    baseline strength. A `template/`-only edit could weaken the SAME pinned
    model without a code-reviewed change to `budget.py`, silently measuring a
    scoreboard arm stronger or weaker than the one curation selected against.
    """
    ts_effort = _extract_ts_string_literal(TEMPLATE_CONFIG_TS_PATH, "REASONING_EFFORT")

    assert ts_effort == REASONING_EFFORT


def test_judge_system_prompt_matches_template():
    """The fifth drift check (orchestrator addendum D27's final section).
    Nothing else mechanically locks `JUDGE_SYSTEM_PROMPT`
    (`template/src/judge/contract.ts`) to `prep/prompts/judge_system.md` — they
    are byte-identical TODAY, by construction, with no test proving it. If they
    drift, curation and the runtime scoreboard stop asking the judge the same
    question, so the scoreboard measures something other than what the dataset
    was selected for — and nothing would say so. A file read and a string
    compare closes that gap.

    NOTE for anyone editing either file: `judge_system.md` deliberately has NO
    trailing newline (it is a template LITERAL's exact contents, and the TS
    literal closes immediately after the final period) — a "helpful"
    end-of-file-newline fix on the `.md` would make this test fail correctly,
    but confusingly, on a whitespace-only diff.

    Also asserts the captured literal is a plain, INERT string: no `` ` ``
    (would need `\\`` escaping in the TS source, so a markdown code span copied
    verbatim into the `.md` produces a permanent, un-fixable-by-copying
    mismatch) and no `${`/`\\` (JS template-literal interpolation or escapes —
    either would make the TS SOURCE TEXT this test compares differ from the
    RUNTIME STRING the judge actually receives, which is the property that
    actually matters and which a source-text compare cannot see directly).
    """
    contract_source = TEMPLATE_JUDGE_CONTRACT_TS_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*export const JUDGE_SYSTEM_PROMPT(?::\s*\w+)?\s*=\s*`(.*?)`;",
        contract_source, re.DOTALL | re.MULTILINE,
    )
    assert match is not None, (
        f"could not find `export const JUDGE_SYSTEM_PROMPT = `...`;` in "
        f"{TEMPLATE_JUDGE_CONTRACT_TS_PATH} — has it been renamed or removed?"
    )
    literal = match.group(1)
    assert "`" not in literal and "${" not in literal and "\\" not in literal, (
        "JUDGE_SYSTEM_PROMPT must stay a PLAIN, INERT template literal — no backtick, "
        "no `${...}` interpolation, no backslash escape — or this source-text compare "
        "stops equalling the runtime string the judge actually receives"
    )

    assert literal == JUDGE_SYSTEM_PROMPT_MD_PATH.read_text(encoding="utf-8")
