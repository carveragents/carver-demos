"""`config.yaml` -> `Settings` (spec §13).

**This module is an ENFORCEMENT POINT, not a parser.** `config.yaml` is a
user-editable file sitting upstream of a real credit card and of the dataset's
experimental validity, so every value it carries is validated here, at load, and
the run dies at startup rather than drifting:

  * **Non-finite guards (orchestrator D8).** `.nan`/`.inf`/`-.inf` are real YAML
    float tokens, and **every comparison against NaN returns `False`** — so the
    spec's `if price < PINNED_PRICE_INPUT: raise` shape *passes* a NaN price, and
    `spend + nan > ceiling` is then `False` as well: the ceiling gate never fires
    and the run bills without bound. `math.isfinite` is therefore load-bearing on
    every money value, and a `<`/`>` floor is not sufficient. `SpendBudget.__init__`
    enforces the same floors independently (P1.11) so they hold for direct
    construction that bypasses this function; a guard that exists twice must be
    *correct* twice.
  * **The cutoff is DERIVED** — `assert_cutoff_margin` (§2) owns the floor, which
    is computed from `budget.py`'s `MODEL_CUTOFF` + `CUTOFF_MARGIN_DAYS`. This
    module does NOT re-implement it as a literal; that duplication is exactly the
    hole V9 was raised to close (§8 advertises the model swap as a one-line
    change, and a floor independent of the model would let it silently corrupt the
    filter).
  * **...and the cutoff is TIED TO THE MODEL (orchestrator D14).** Deriving from
    `MODEL_CUTOFF` is only worth anything if `MODEL_CUTOFF` describes the model
    actually pinned. §13 constrains `model_router_string` to the `openai/` prefix
    and nothing else, while goal #9 *invites* a one-line swap — so `_validate`
    asserts `MODEL_CUTOFF == MODEL_CUTOFFS[model_router_string]` and rejects a
    model absent from that table. This is V9's other half: D13 tied the config key
    to the constant the filter reads; this ties the cutoff to the model it
    describes. goal #3's "MUST be re-derived" is a mechanism here, not a sentence.
  * **Unknown keys are a hard error.** `snapshot_date` and `reasoning_effort` are
    code constants precisely because each is a lever — on the date-rot upper bound
    (§2) and on baseline strength (§3) respectively. Absence is the mechanism, so
    a stray key must raise rather than be ignored.

**Not a leaf, deliberately** (orchestrator D12): `config -> candidates` is a real
edge (`assert_cutoff_margin`) and `config -> budget` is another (the pinned price
floors). §1:427's LEAF listing for this module is stale; both edges point
downward, so the DAG holds.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path

import yaml

from .budget import (
    MODEL_CUTOFF,
    MODEL_CUTOFFS,
    PINNED_PRICE_INPUT_USD_PER_MILLION,
    PINNED_PRICE_OUTPUT_USD_PER_MILLION,
)
from .candidates import CANDIDATE_CUTOFF_DATE, assert_cutoff_margin

# goal #11's ceiling on the cleared set: it may shrink freely, never grow.
MAX_TARGET_SET_SIZE = 200

# The goal's near-miss guard (§4): a floor, not a tunable default.
MIN_JUDGE_CONFIDENCE_FLOOR = 0.7

_MODEL_ROUTER_PREFIX = "openai/"


@dataclass(frozen=True)
class Settings:
    """§13's complete key set — no more, no less.

    There is deliberately **no `snapshot_date` field and no `reasoning_effort`
    field**. Both are code constants (`candidates.SNAPSHOT_DATE`,
    `budget.REASONING_EFFORT`); see the module docstring.
    """

    model_router_string: str
    annotations_path: str
    candidate_cutoff_date: str
    sample_seed: int
    probe_batch_size: int
    target_set_size: int
    probe_max_records: int
    scenario_trial_size: int
    scenario_trial_min: int
    price_input_per_million_usd: float
    price_output_per_million_usd: float
    total_spend_ceiling_usd: float
    judge_confidence_floor: float
    dotenv_path: str
    cleared_dir: str
    scratch_dir: str


def _require_str(raw: dict, key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string; got {value!r}")
    return value


def _require_int(raw: dict, key: str) -> int:
    value = raw[key]
    # `isinstance(True, int)` is True, so bools must be rejected explicitly —
    # `target_set_size: true` would otherwise resolve to a silent 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer; got {value!r}")
    return value


def _require_finite_float(raw: dict, key: str) -> float:
    """Accepts `int` or `float`, rejects `bool`, and — the point of this function —
    rejects NaN/inf/-inf (D8). PyYAML resolves `.nan`/`.inf`/`-.inf` to real
    floats, and a non-finite value defeats every `<`/`>` guard downstream by
    returning `False` from each comparison rather than by raising.
    """
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number; got {value!r}")
    try:
        value = float(value)
    except OverflowError:
        # A Python int has no width limit, so YAML resolves an arbitrarily long
        # digit string to an int that `float()` cannot represent. OverflowError is
        # NOT a ValueError, so without this it escapes as an unhandled traceback
        # rather than as this module's named startup error.
        raise ValueError(f"{key} is too large to represent as a number; got a "
                         f"{len(str(abs(value)))}-digit int") from None
    if not math.isfinite(value):
        raise ValueError(
            f"{key}={value} is not finite. NaN/inf defeat every comparison guard silently "
            f"(nan < floor is False, spend + nan > ceiling is False), which would remove the "
            f"spend ceiling entirely — see the module docstring.")
    return value


def load_settings(path: str | Path = "config.yaml") -> Settings:
    """Load, validate and freeze `config.yaml` (§13).

    Raises `FileNotFoundError` if the file is absent, and `ValueError` for any
    unknown key, missing key, wrong type, non-finite money value, or value outside
    its documented constraint. Every check is a startup error by design: each one
    guards either the spend ceiling or the dataset's validity, and a run that
    proceeds on a bad value is worse than one that never starts.
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{config_path} must contain a YAML mapping; got {type(raw).__name__}")

    known = {field.name for field in fields(Settings)}
    # `str(k)` because a YAML mapping may carry non-string keys (`42: x`), which
    # would otherwise make `", ".join(...)` raise TypeError instead of this
    # module's documented ValueError.
    unknown = sorted(str(key) for key in set(raw) - known)
    if unknown:
        raise ValueError(
            f"unknown config key(s): {', '.join(unknown)}. `snapshot_date` and "
            f"`reasoning_effort` are CODE CONSTANTS, never config keys (§13) — each is a "
            f"lever on the date-rot gate and on baseline strength respectively, and "
            f"absence is the mechanism that keeps them un-tunable.")
    missing = sorted(known - set(raw))
    if missing:
        raise ValueError(f"missing required config key(s): {', '.join(missing)}")

    settings = Settings(
        model_router_string=_require_str(raw, "model_router_string"),
        annotations_path=_require_str(raw, "annotations_path"),
        candidate_cutoff_date=_require_str(raw, "candidate_cutoff_date"),
        sample_seed=_require_int(raw, "sample_seed"),
        probe_batch_size=_require_int(raw, "probe_batch_size"),
        target_set_size=_require_int(raw, "target_set_size"),
        probe_max_records=_require_int(raw, "probe_max_records"),
        scenario_trial_size=_require_int(raw, "scenario_trial_size"),
        scenario_trial_min=_require_int(raw, "scenario_trial_min"),
        price_input_per_million_usd=_require_finite_float(raw, "price_input_per_million_usd"),
        price_output_per_million_usd=_require_finite_float(raw, "price_output_per_million_usd"),
        total_spend_ceiling_usd=_require_finite_float(raw, "total_spend_ceiling_usd"),
        judge_confidence_floor=_require_finite_float(raw, "judge_confidence_floor"),
        dotenv_path=_require_str(raw, "dotenv_path"),
        cleared_dir=_require_str(raw, "cleared_dir"),
        scratch_dir=_require_str(raw, "scratch_dir"),
    )
    _validate(settings)
    return settings


def _validate(cfg: Settings) -> None:
    """Every §13 constraint that is not a type check. Ordered as §13's table."""
    if not cfg.model_router_string.startswith(_MODEL_ROUTER_PREFIX):
        raise ValueError(
            f"model_router_string={cfg.model_router_string!r} must start with "
            f"{_MODEL_ROUTER_PREFIX!r}: OpenAI is the only provider prep calls (goal #9).")

    # V9's TRUE RESIDUAL (orchestrator D14): tie the cutoff to the MODEL.
    #
    # §13's only pinned constraint on this key is the `openai/` prefix above, and
    # goal #9 ACTIVELY INVITES the one-line swap. So MODEL_CUTOFF — which every
    # date below derives from — described a model nobody checked was still the
    # model being probed. A forker swapping to a later-cutoff model and forgetting
    # MODEL_CUTOFF passed every check while the filter admitted documents from
    # inside the new model's training data. goal #3's "MUST be re-derived" had no
    # mechanism; this is it.
    #
    # ORDER MATTERS — but for REMEDIATION CORRECTNESS, not for closure. Being
    # precise about which, because overclaiming a mechanism is this project's
    # signature defect and an earlier draft of this very comment did it:
    #
    #   * NOT closure. Both this and `assert_cutoff_margin` raise ValueError, run
    #     unconditionally, and have no side effects, so the set of configs that
    #     survive `_validate` is IDENTICAL under either ordering. Reversing them
    #     would not open a hole.
    #   * IT IS the error a broken config gets, which is D13's whole lesson: an
    #     operator who COMPLIES with a wrong message converts a loud failure into a
    #     silent corruption. With a stale MODEL_CUTOFF, `assert_cutoff_margin`
    #     derives its floor FROM that stale value — so running it first would
    #     announce "the earliest defensible candidate date is 2026-03-01" while the
    #     pinned model's real cutoff is months later. Comply with THAT and you set
    #     a filter date inside the new model's training data, believing a startup
    #     check told you it was safe.
    #
    # So: establish that MODEL_CUTOFF really describes the pinned model FIRST; only
    # then is a floor derived from it meaningful advice. Pinned by
    # `test_the_stale_cutoff_error_precedes_the_derivations_unsafe_advice`.
    documented_cutoff = MODEL_CUTOFFS.get(cfg.model_router_string)
    if documented_cutoff is None:
        # `.get` + explicit raise, never `MODEL_CUTOFFS[...]`: a bare KeyError
        # traceback would escape this function's documented ValueError contract
        # (D13 caught an OverflowError doing exactly that) AND would tell a forker
        # nothing about what to do. The error IS the mechanism here — it is the
        # only thing standing between goal #9's invited swap and a silently
        # corrupted experiment, so it must be readable by someone who has never
        # heard of D14.
        raise ValueError(
            f"model_router_string={cfg.model_router_string!r} is not in budget.py's "
            f"MODEL_CUTOFFS (known: {', '.join(sorted(MODEL_CUTOFFS))}). goal #9 invites this "
            f"one-line model swap; goal #3 requires the candidate date to be RE-DERIVED from "
            f"the new model's documented cutoff whenever it happens. A model with a LATER "
            f"cutoff silently admits documents from inside its own training data, which "
            f"destroys the recency delta the whole project measures. To swap: (1) add "
            f"{cfg.model_router_string!r} -> its PROVIDER-DOCUMENTED knowledge cutoff to "
            f"MODEL_CUTOFFS in budget.py — read it from the provider's docs, never guess; "
            f"(2) set MODEL_CUTOFF to that same date; (3) re-derive CANDIDATE_CUTOFF_DATE in "
            f"candidates.py AND candidate_cutoff_date in config.yaml (the margin rule does "
            f"the arithmetic — see assert_cutoff_margin); (4) re-run curation, since "
            f"data/cleared/ was selected against the OLD model. USE AN EXPLICIT, VERSIONED "
            f"MODEL ID: the bare alias 'openai/gpt-5.6' is valid per goal #9 but is "
            f"deliberately absent from MODEL_CUTOFFS, because an alias's cutoff is a claim "
            f"about whatever it resolves to TOMORROW — pin the alias today and it silently "
            f"stops being true the day it re-points, which is this check's own failure mode.")

    if MODEL_CUTOFF != documented_cutoff:
        raise ValueError(
            f"budget.py's MODEL_CUTOFF={MODEL_CUTOFF} disagrees with "
            f"MODEL_CUTOFFS[{cfg.model_router_string!r}]={documented_cutoff}, the documented "
            f"cutoff of the model actually pinned. MODEL_CUTOFF is what every candidate date "
            f"derives from (assert_cutoff_margin -> CANDIDATE_CUTOFF_DATE), so a stale value "
            f"here selects the pool against a model that is NOT the one being probed — goal "
            f"#3's exact failure. Set MODEL_CUTOFF={documented_cutoff} and re-derive "
            f"CANDIDATE_CUTOFF_DATE (candidates.py) and candidate_cutoff_date (config.yaml).")

    # A malformed table entry is caught HERE rather than 30 frames down. Both checks
    # above pass on a forker's `"openai/x": "June 1 2026"` (they only compare strings),
    # and it would then die inside `candidates._derived_floor()` on `date.fromisoformat`
    # — technically in-contract (a ValueError escapes), but naming neither MODEL_CUTOFFS
    # nor the remedy, at exactly the moment a forker is mid-swap and needs both. The
    # error IS the mechanism (see above), so it has to survive contact with the person
    # it is written for.
    try:
        date.fromisoformat(documented_cutoff)
    except ValueError:
        raise ValueError(
            f"MODEL_CUTOFFS[{cfg.model_router_string!r}]={documented_cutoff!r} is not a "
            f"parseable ISO date (YYYY-MM-DD). It is the input to the candidate-date "
            f"derivation (assert_cutoff_margin), so it must be an exact date read from the "
            f"provider's documentation.") from None

    # The DERIVATION (§2) — never a literal floor. This is the whole reason
    # `config -> candidates` is a real import edge (D12). It checks BOTH this
    # declared value and `CANDIDATE_CUTOFF_DATE`, the constant the filter really
    # reads. Meaningful only because MODEL_CUTOFF was just verified against the
    # pinned model above.
    assert_cutoff_margin(cfg.candidate_cutoff_date)

    # ...and the two must AGREE. `is_candidate(rec)`'s pinned signature (§2:579)
    # cannot receive the config value, so the filter reads the code constant and
    # this key would otherwise be inert — a documented knob wired to nothing,
    # which is how a compliant-looking config.yaml could describe a filter that
    # behaves differently. §13:5717 states this key's effect IS the `is_candidate()`
    # predicate; this equality is what makes that claim true rather than false.
    # Tightening therefore means editing BOTH — a code change, reviewed, which is
    # the anti-padding posture goal #11 asks for anyway.
    if cfg.candidate_cutoff_date != CANDIDATE_CUTOFF_DATE:
        raise ValueError(
            f"candidate_cutoff_date={cfg.candidate_cutoff_date} disagrees with candidates.py's "
            f"CANDIDATE_CUTOFF_DATE={CANDIDATE_CUTOFF_DATE}, which is the constant "
            f"`is_candidate()` actually filters on — so this config value would have no effect "
            f"and the pool would silently be selected on the other date. Change BOTH, or "
            f"neither.")

    for key in ("probe_batch_size", "probe_max_records", "scenario_trial_size"):
        if getattr(cfg, key) < 1:
            raise ValueError(f"{key} must be >= 1; got {getattr(cfg, key)}")

    if not 1 <= cfg.target_set_size <= MAX_TARGET_SET_SIZE:
        raise ValueError(
            f"target_set_size={cfg.target_set_size} must be 1..{MAX_TARGET_SET_SIZE}. It is "
            f"goal #11's CEILING: it may be freely reduced, but never raised as a way to force "
            f"more yield — a padded set destroys the one claim this project exists to make.")

    if not 1 <= cfg.scenario_trial_min <= cfg.scenario_trial_size:
        raise ValueError(
            f"scenario_trial_min={cfg.scenario_trial_min} must be 1..scenario_trial_size "
            f"({cfg.scenario_trial_size}).")

    # `not (x >= floor)` rather than `x < floor`, and `not (x > 0)` rather than
    # `x <= 0`. Identical for every finite value, but the negated-positive form is
    # NaN-SAFE BY CONSTRUCTION: `nan >= floor` is False, so `not (...)` raises,
    # whereas `nan < floor` is also False and would silently PASS. These guards are
    # only reachable after `_require_finite_float` has already rejected NaN, so
    # today this is redundant — deliberately. D8's own rule is that a guard which
    # exists twice must be *correct* twice, and this shape means the floors do not
    # depend on another function's ordering for their correctness.
    if not (cfg.price_input_per_million_usd >= PINNED_PRICE_INPUT_USD_PER_MILLION):
        raise ValueError(
            f"price_input_per_million_usd={cfg.price_input_per_million_usd} is below the pinned "
            f"floor {PINNED_PRICE_INPUT_USD_PER_MILLION}. Under-pricing shrinks the effective "
            f"spend ceiling's protection; only ever RAISE this, if OpenAI's published rate goes up.")

    if not (cfg.price_output_per_million_usd >= PINNED_PRICE_OUTPUT_USD_PER_MILLION):
        raise ValueError(
            f"price_output_per_million_usd={cfg.price_output_per_million_usd} is below the pinned "
            f"floor {PINNED_PRICE_OUTPUT_USD_PER_MILLION}. Under-pricing shrinks the effective "
            f"spend ceiling's protection; only ever RAISE this, if OpenAI's published rate goes up.")

    if not (cfg.total_spend_ceiling_usd > 0):
        raise ValueError(
            f"total_spend_ceiling_usd={cfg.total_spend_ceiling_usd} must be > 0.")

    if not MIN_JUDGE_CONFIDENCE_FLOOR <= cfg.judge_confidence_floor <= 1.0:
        raise ValueError(
            f"judge_confidence_floor={cfg.judge_confidence_floor} must be "
            f"{MIN_JUDGE_CONFIDENCE_FLOOR}..1.0. It is the goal's near-miss guard (§4) — a "
            f"floor, not a free parameter: lowering it admits near-misses as 'failures' and "
            f"pads the set.")
