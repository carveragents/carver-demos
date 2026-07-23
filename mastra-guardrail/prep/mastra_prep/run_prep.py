"""The single entrypoint (spec §3's pinned `main`, plan P5.1).

Mirrors `gics-topic-tagging`'s `run_pipeline.py`: one `main(argv)`, one config
load, one budget, and every phase threaded through them.

---

**THREE argv branches, not §3's four. `--replay` is CUT (D22).** §3 rests its
determinism claim on a `--replay` flag reading `data/scratch/probe_log/` back.
D22 cut it: re-running curation from a log is a convenience for a pipeline that
runs many times, and this one runs **once**. Building a replay harness to avoid a
rerun we do not expect to need is speculative work. The consequence is stated
rather than papered over: **the run is auditable, not reproducible.** Every
probe's inputs and outputs are on disk and can be read; nothing replays them.
Do not restate the stronger claim.

**`data/scratch/probe_log/` STAYS, and this module owns it (D22).** It is a
write-only append of each probe call's raw request and response. It is insurance
on the one phase that spends real money (~$17 against the user's own key): if the
run dies at record 380 of 400 with no transcript, the only recovery is to pay
again. `ProbeLogClient` wraps the injected OpenAI client and writes each call
through — which is why it captures a call that DIES, not just one that returns,
and why a `BudgetExhausted` mid-sweep still leaves every prior call on disk.

**DEVIATION (flagged in the task report):** §3 pins the log's filename as
`<record_artifact_id>_{stage_a,stage_b,judge}.json`. The client seam cannot see a
record id — `client.chat.completions.create(**payload)` receives a prompt and
nothing else, and `probe.py`/`judge.py` do not expose a logging hook. The stage
IS derivable (the payload's `response_format.json_schema.name`), so files are
`<NNNN>_<stage>.json` in call order. The alternative was threading a log path
through `run_curation`/`probe_and_score_one`/`run_stage_a` — four pinned
signatures — to recover a filename component. A logging failure NEVER kills the
run: insurance that burns down the house is worse than none.

---

**The reservation audit is in a `finally`, and that is load-bearing.** It runs on
every exit — clean finish, `insufficient_trial` early return, `BudgetExhausted`
stop, and an unexpected exception alike. A leak check that only ran on the happy
path would miss precisely the runs most likely to leak, since the failure paths
are the ones that terminate reservations under pressure. An `AssertionError`
raised from the `finally` during unwinding REPLACES the original exception; that
is deliberate (§3): a leaked reservation means the spend figure in the original
error's own report is wrong, so surfacing the ledger bug beats preserving a
message whose numbers cannot be trusted.

**`run_prep.py` never writes `data/cleared/`.** It reads it (`--verify-cleared`)
and it writes `data/scratch/`. `review.py` is the only writer, and that is the
goal's human-review constraint (D25).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .budget import SpendBudget
from .candidates import filter_candidates
from .config import Settings, load_settings
from .curate import CurationResult, run_curation
from .generate_template_config import emit_template_config
from .judge import JUDGE_RESPONSE_SCHEMA
from .logging_ import configure_logging, log
from .openai_client import load_env, make_client
from .probe import STAGE_B_RESPONSE_SCHEMA
from .reader import stream_annotations
from .review import (
    CANDIDATES_FILENAME,
    CLEARED_FILENAME,
    REJECTIONS_FILENAME,
    build_review_candidate,
    load_review_candidates,
    run_review_loop,
    write_review_candidates,
)
from .scenario_decision import ARMS, EVIDENCE_PATH, ScenarioDecision, decide_scenario
from .schema import SCORE_OUTCOME_TO_FAILURE_MODE, validate_cleared_record
from .scenarios import SCENARIOS, is_eligible

PROBE_LOG_DIRNAME = "probe_log"

# The payload's structured-output schema name -> the stage that built it. Stage A
# passes `schema=None` to `build_request_payload`, so an ABSENT `response_format`
# is the Stage A signal.
#
# The two names are READ OFF their owning modules rather than retyped here. A
# literal copy would agree today and drift silently: rename
# STAGE_B_RESPONSE_SCHEMA["name"] and every Stage B call would log as `stage_a`
# with the suite green, because nothing would tie the copy to the original.
_SCHEMA_NAME_TO_STAGE: dict[str, str] = {
    STAGE_B_RESPONSE_SCHEMA["name"]: "stage_b",
    JUDGE_RESPONSE_SCHEMA["name"]: "judge",
}

# Every flag `main` understands. Unknown `--flags` are REJECTED, never ignored:
# `config.py` takes the identical posture on unknown config keys, and argv is a
# user-editable input upstream of the same credit card. A typo'd `--verify-clared`
# falling through would start the full curation flow — a real client, a real
# budget, ~$17 against the user's key — when the operator asked for a free,
# read-only check.
_KNOWN_FLAGS: frozenset[str] = frozenset({
    "--review", "--emit-template-config", "--verify-cleared", "--config", "--reviewer",
})
_FLAGS_TAKING_A_VALUE: frozenset[str] = frozenset({"--config", "--reviewer"})


def main(argv: list[str] | None = None) -> None:
    """Prep's single entrypoint. §3 pins this function's structure exactly.

    Exits 0 on every honest outcome, including the two empty ones: an
    `insufficient_trial` decision and a zero-survivor curation are RESULTS, not
    errors (§7, §14). Non-zero exit is reserved for `--verify-cleared` failing and
    for genuine faults.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    configure_logging()
    _reject_unknown_flags(args)

    if "--review" in args:
        return _review_branch(args)
    if "--emit-template-config" in args:
        return _emit_template_config_branch(args)
    if "--verify-cleared" in args:
        return _verify_cleared_branch(args)

    cfg = load_settings(_config_path(args))
    load_env(cfg.dotenv_path)
    client = ProbeLogClient(make_client(), Path(cfg.scratch_dir) / PROBE_LOG_DIRNAME)
    budget = SpendBudget(cfg.total_spend_ceiling_usd,
                         cfg.price_input_per_million_usd, cfg.price_output_per_million_usd)
    try:
        candidates = list(filter_candidates(stream_annotations(cfg.annotations_path)))   # §2
        decision = decide_scenario(client, candidates, cfg, budget)                      # §7
        write_json(decision["evidence_path"], decision)   # written on BOTH outcomes

        if decision["outcome"] == "insufficient_trial":
            # Terminal, and NOT an error: report and stop. No scenario is locked, no
            # curation runs, and the A tie-break is deliberately NOT applied — §7's
            # `>=` over two three-record arms is a coin-flip wearing the probe's
            # clothes, and goal #10's "decided by the probe" is what rules it out.
            log(report_insufficient_trial(decision, cfg))
            return                                # -> exit 0; the `finally` still audits

        scenario = SCENARIOS[decision["winner"]]
        eligible = [r for r in candidates if is_eligible(r, scenario)]   # §4's applicability fix
        result = run_curation(client, eligible, scenario, cfg, budget,   # §3
                              exclude_ids=frozenset(decision["probed_ids"][decision["winner"]]))
        _queue_for_review(result, eligible, scenario, cfg)
        log(report_curation(result, decision, len(candidates), len(eligible),
                            ceiling_usd=budget.ceiling_usd))
    finally:
        # EVERY exit path — normal, insufficient_trial, BudgetExhausted, or an
        # unexpected exception propagating out — passes through here.
        budget.assert_no_open_reservations()
        log(f"spend: ${budget.spend_so_far_usd:.2f} of ${budget.ceiling_usd:.2f} ceiling")


# ---------------------------------------------------------------------------
# Reporting — both terminal shapes are pinned, because each is a number a human
# reads to decide whether the project worked.
# ---------------------------------------------------------------------------

def report_insufficient_trial(decision: ScenarioDecision, cfg: Settings | None = None) -> str:
    """Diagnose WHICH failure this is — D23's ruling, and the whole point of the
    function.

    **Two failures with non-overlapping fixes:**

      * *"this arm never ran"* (`trial_planned == 0`) — no record in the corpus is
        eligible for that scenario. Eligibility is a pure function of the corpus,
        so the run is deterministic and **re-running changes nothing**: it will
        stop at the same place forever. The fix is to widen eligibility, or to
        accept the walkover to the arm that did run (D23 part 1).
      * *"this arm was truncated"* (`completed < min(planned, scenario_trial_min)`)
        — the budget or the API cut the trial short. The fix is to raise
        `total_spend_ceiling_usd` (or wait for the API) and re-run.

    §7 specifies only the second. Emitting it for the first sends the operator to
    re-run a deterministic dead end — which is why the split exists, and why the
    diagnosis is per-arm rather than one message for the pair (an arm can be empty
    while the OTHER is truncated; both fixes then apply, and both are printed).

    D23's parts 1-2 — the walkover machinery itself — are deliberately NOT built
    here: decided now, built on contact. If the Phase-7 trial pairs both arms, none
    of this fires.

    `cfg` is not in §3's pinned `report_insufficient_trial(decision)` signature, but
    the truncation test needs `scenario_trial_min` and `ScenarioDecision` does not
    report it. Optional and threaded from `main`, per the rule for exactly this case.
    Without it the test falls back to `completed < planned`, which can only
    OVER-report truncation (naming an arm short that cleared the bar) — never
    under-report it, so the fallback fails in the direction that shows a reader more
    rather than less.
    """
    lines = [
        "outcome:             insufficient_trial — no scenario locked, no curation run, exit 0",
        f"stop_reason:         {decision['stop_reason']}",
        f"discarded_rounds:    {decision['discarded_rounds']}",
        "trial:               " + "  ".join(
            f"{arm}={decision['trial_completed'][arm]}/{decision['trial_planned'][arm]}"
            for arm in ARMS),
        "strength (reported, NOT a basis for a winner): " + "  ".join(
            f"{arm}={decision['strength_scores'][arm]:.2f}" for arm in ARMS),
        "",
    ]

    never_ran = [arm for arm in ARMS if decision["trial_planned"][arm] == 0]
    truncated = [arm for arm in ARMS
                 if arm not in never_ran and not _arm_met_its_bar(decision, arm, cfg)]

    for arm in never_ran:
        other = [a for a in ARMS if a != arm]
        lines += [
            f"arm {arm} NEVER RAN: 0 records in the corpus are eligible for scenario {arm}.",
            f"  Eligibility is a pure function of the corpus, so this run is deterministic —",
            f"  RE-RUNNING CHANGES NOTHING. It will stop here every time.",
            f"  Fix: widen scenario {arm}'s eligibility, or accept the walkover to arm "
            f"{'/'.join(other)} (D23).",
        ]
    for arm in truncated:
        lines += [
            f"arm {arm} WAS TRUNCATED: {decision['trial_completed'][arm]} of "
            f"{decision['trial_planned'][arm]} planned records completed, below the "
            f"scenario_trial_min bar.",
            f"  The trial was cut short ({decision['stop_reason']}), not starved of records.",
            f"  Fix: raise total_spend_ceiling_usd (or wait for the API) and re-run.",
        ]
    if not never_ran and not truncated:
        # Defensive: decide_scenario said insufficient, but no arm reads as short.
        # Naming that beats printing a fix for a diagnosis we do not have.
        lines.append("no arm reads as short — the decision and this diagnosis disagree; "
                     "inspect the evidence file before re-running anything.")

    lines += ["", f"evidence:            {decision['evidence_path']}"]
    return "\n".join(lines)


def report_curation(result: CurationResult, decision: ScenarioDecision,
                    candidate_count: int, eligible_count: int,
                    ceiling_usd: float | None = None) -> str:
    """The run's terminal output on the successful path (§3, pinned).

    Three things it must state, because each is a way the headline number could
    mislead — and all three are printed, not left to a README:

      * **The denominator is the scenario-eligible subset, not the headline
        8,260.** A "137 of 400" hit rate is over records already filtered to the
        winning scenario (§4's applicability fix). Printing 8,260 next to 137 would
        invite a rate that means nothing.
      * **`survivors/probed` is success-conditioned.** Curation STOPS at
        `target_set_size`, so on a `stop_reason="target_reached"` run the rate is
        biased UPWARD — it is the rate *until we had enough*, not the rate over a
        fixed sample. `stop_reason` prints beside it for exactly that reason.
      * **Survivors are not the shipped set.** Human review (§6) comes next and can
        only REDUCE the number.

    The zero-survivor case uses this same function and the same shape, plus goal
    #11's line — *ship nothing rather than pad* — and exits 0. An honest empty
    result is a result.

    `ceiling_usd` is not in §3's pinned call site, but §3's pinned OUTPUT prints
    "$16.84 of $120.00 ceiling" and `CurationResult` carries only the spend.
    Optional and threaded from `main`'s budget, per the rule for exactly this case.
    """
    survivors = result["survivors"]
    probed = result["probed"]
    winner = decision["winner"]
    rate = f"{100.0 * len(survivors) / probed:.1f}%" if probed else "n/a"

    lines = [
        f"scenario:            {winner} (mean strength "
        + " ".join(f"{arm}={decision['strength_scores'][arm]:.2f}" for arm in ARMS)
        + "; trial "
        + " vs ".join(f"{decision['trial_completed'][arm]}/{decision['trial_planned'][arm]}"
                      for arm in ARMS)
        + f"; {decision['discarded_rounds']} rounds discarded)",
        f"candidates:          {candidate_count:,} matched goal #3's filter",
        f"                     -> {eligible_count:,} scenario-eligible "
        f"(is_eligible for {winner}, incl. narrowability, §7)",
        f"probed:              {probed:,} of those {eligible_count:,}   "
        f"(stop_reason={result['stop_reason']})",
        f"survivors:           {len(survivors):,} of {probed:,} probed  = {rate} hit rate",
    ]
    for mode, count in _mode_counts(result).items():
        lines.append(f"  {mode:<20} {count}")
    if survivors:
        lines.append("        (records may carry more than one mode)")
    ceiling = f"${ceiling_usd:.2f} ceiling" if ceiling_usd is not None else "the run ceiling"
    lines.append(f"spend:               ${result['spend_usd']:.2f} of {ceiling}")

    lines += [
        "",
        "how to read the hit rate — all three caveats apply to the line above:",
        f"  * the DENOMINATOR is the {eligible_count:,} scenario-eligible records, NOT the "
        f"{candidate_count:,} the goal's filter matched. A rate over {candidate_count:,} would "
        f"mean nothing.",
        f"  * it is SUCCESS-CONDITIONED: curation stops at target_set_size, so on a "
        f"target_reached run the rate is BIASED UPWARD — it is the rate until we had enough, "
        f"not the rate over a fixed sample (this run: stop_reason={result['stop_reason']}).",
        "  * survivors are NOT the shipped set: human review (§6) comes next and can only "
        "REDUCE this number. The final count is the post-review one.",
    ]

    if not survivors:
        lines += ["", "0 records survived — see goal #11: ship nothing rather than pad."]
    else:
        lines += ["", f"next:                run_prep.py --review   ({len(survivors)} records "
                      f"await human clearance; none ship unreviewed)"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# argv branches — each returns before the main flow, and none constructs a budget
# (none makes an API call).
# ---------------------------------------------------------------------------

def _review_branch(args: list[str]) -> None:
    """§6's human checkpoint. Makes **NO API calls** — every input was recorded at
    probe time, so no client and no budget is constructed here at all, which is the
    strongest form of "no calls" available: there is nothing to call with."""
    cfg = load_settings(_config_path(args))
    reviewer = (_flag_value(args, "--reviewer") or input("reviewer name: ")).strip()
    if not reviewer:
        raise SystemExit("--reviewer is required: an attestation needs a name behind it")

    candidates = load_review_candidates(Path(cfg.scratch_dir) / CANDIDATES_FILENAME)
    log(f"review: {len(candidates)} candidate(s) awaiting clearance")
    run_review_loop(candidates, reviewer, cleared_dir=cfg.cleared_dir,
                    rejections_path=Path(cfg.scratch_dir) / REJECTIONS_FILENAME)


def _emit_template_config_branch(args: list[str]) -> None:
    """Runs AFTER human review, and makes no API calls, so it constructs no budget
    (§3)."""
    cfg = load_settings(_config_path(args))
    records = _load_cleared(cfg.cleared_dir)
    decision = json.loads(Path(EVIDENCE_PATH).read_text(encoding="utf-8"))
    bundle = emit_template_config(records, decision)
    log(f"emitted scenario-{bundle['winner']} config from trigger "
        f"{bundle['trigger_record_id']} (1 of {bundle['trigger_candidate_count']} "
        f"eligible trigger candidates); wrote {', '.join(bundle['written_files'])}")


def _verify_cleared_branch(args: list[str]) -> None:
    """Validate `data/cleared/`'s STRUCTURE — pinned so it does not grow.

    Checks, and nothing else: every file parses as a `ClearedRecord`,
    `validate_cleared_record` passes, `human_review.attestation == "approved"`,
    and `citation.url` matches one of the record's OWN recorded resolving URLs.

    **Makes no network calls and re-resolves nothing.** §14 places post-clearing
    re-validation explicitly out of scope for v1. An earlier draft had this flag
    "re-resolve each citation.url", which silently adds a URL crawler the spec
    excludes — and quoted §14's own exclusion two lines later. Citations are
    validated at CLEARING time, by §2's gate; a link that dies afterwards is a
    manual fix the README documents.

    Raises `SystemExit(1)` on any offender — this is pre-commit-friendly, so it
    must fail the process, not just print.
    """
    cfg = load_settings(_config_path(args))
    directory = Path(cfg.cleared_dir)
    if not directory.is_dir():
        raise FileNotFoundError(
            f"cleared directory not found: {directory} — never auto-created (§15)")

    resolving = _recorded_resolving_urls(cfg)
    offenders: list[str] = []
    count = 0
    citations_checked = 0
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in (payload if isinstance(payload, list) else [payload]):
            count += 1
            ok, errors = validate_cleared_record(record)
            if not ok:
                offenders.append(f"{path.name}:{_record_id(record)}: {errors}")
                continue          # attestation/citation checks below need a valid shape
            # Redundant with validate_cleared_record (which pins the literal), and
            # kept: this flag's contract names the attestation explicitly, and a
            # gate that leans on another gate having run is not a gate.
            if record["human_review"]["attestation"] != "approved":
                offenders.append(f"{path.name}:{record['id']}: attestation is not 'approved'")
            known = resolving.get(record["id"])
            if known is None:
                continue          # no queue entry -> the citation is NOT checked; counted below
            citations_checked += 1
            if record["citation"]["url"] not in known:
                offenders.append(
                    f"{path.name}:{record['id']}: citation.url "
                    f"{record['citation']['url']!r} is not one of the "
                    f"{len(known)} URL(s) that resolved for this record at probe time")

    if offenders:
        for offender in offenders:
            log(f"INVALID: {offender}")
        raise SystemExit(f"--verify-cleared FAILED: {len(offenders)} problem(s) in {directory}")

    # Report what was CHECKED, not what was hoped. The citation check needs the
    # scratch queue that recorded the probe-time resolutions, and a vendored
    # data/cleared/ (Phase 8) legitimately travels without it — which is exactly
    # when someone runs this flag. Claiming coverage over records it skipped would
    # make the message false at the one moment it is read.
    log(f"--verify-cleared OK: {count} record(s) in {directory} are structurally valid "
        f"and human-approved.")
    log(f"  citation.url checked against the recorded resolving URLs for "
        f"{citations_checked} of {count} record(s)"
        + ("" if citations_checked == count else
           f"; {count - citations_checked} had no entry in {Path(cfg.scratch_dir) / CANDIDATES_FILENAME} "
           f"and were NOT checked"))
    log("  no network calls were made and nothing was re-resolved — §14 puts "
        "post-clearing re-validation out of scope for v1")


# ---------------------------------------------------------------------------
# The probe log — D22's insurance on the one phase that spends real money.
# ---------------------------------------------------------------------------

class ProbeLogClient:
    """A pass-through wrapper over the OpenAI client that appends every call's raw
    request and response to `data/scratch/probe_log/`.

    Mimics exactly the surface prep's pinned call lifecycle touches
    (`client.chat.completions.create(**payload)`), and nothing more — the same
    surface `tests/stubs.py` mimics, which is why a stub drops straight in.

    **Write-only.** Nothing reads this back: `--replay` is cut (D22). The log is
    what makes the run AUDITABLE — every probe's inputs and outputs are on disk —
    and is the transcript that turns a run dying at record 380 of 400 into one
    paid run instead of two.
    """

    def __init__(self, client, log_dir: Path | str) -> None:
        self._client = client
        self._log_dir = Path(log_dir)
        self._seq = 0
        self.chat = self
        self.completions = self

    def create(self, **payload):
        self._seq += 1
        seq, stage = self._seq, _stage_of_payload(payload)
        try:
            response = self._client.chat.completions.create(**payload)
        except Exception as exc:
            # A call that DIED is exactly the one worth having on disk.
            self._write(seq, stage, payload, {"error": f"{type(exc).__name__}: {exc}"})
            raise
        self._write(seq, stage, payload, _response_snapshot(response))
        return response

    def _write(self, seq: int, stage: str, payload: dict, response: dict) -> None:
        """Never raises. A logging failure must not kill a paid run — insurance that
        burns down the house is worse than no insurance."""
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            (self._log_dir / f"{seq:04d}_{stage}.json").write_text(
                json.dumps({"seq": seq, "stage": stage, "request": payload,
                            "response": response}, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8")
        except Exception as exc:      # noqa: BLE001 — deliberate, see the docstring
            log(f"probe_log write failed ({type(exc).__name__}: {exc}) — the run continues; "
                f"this call has no transcript")


def _stage_of_payload(payload: dict) -> str:
    """Which stage built this call, derived from the payload itself. Stage A passes
    `schema=None` to `build_request_payload`, so an absent `response_format` IS the
    Stage A signal (see the module docstring's DEVIATION on why the record id is
    not recoverable here)."""
    schema = (payload.get("response_format") or {}).get("json_schema") or {}
    return _SCHEMA_NAME_TO_STAGE.get(schema.get("name"), "stage_a")


def _response_snapshot(response) -> dict:
    """The response's content-bearing parts, defensively — a log that raises on an
    odd response shape is a log that fires exactly when it is needed most."""
    snapshot: dict = {}
    try:
        choice = response.choices[0]
        snapshot["content"] = choice.message.content
        snapshot["finish_reason"] = choice.finish_reason
    except Exception as exc:          # noqa: BLE001
        snapshot["content_error"] = f"{type(exc).__name__}: {exc}"
    try:
        snapshot["usage"] = response.usage.model_dump() if response.usage is not None else None
    except Exception as exc:          # noqa: BLE001
        snapshot["usage_error"] = f"{type(exc).__name__}: {exc}"
    return snapshot


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def write_json(path: Path | str, payload) -> Path:
    """Write `payload` as pretty UTF-8 JSON, creating the parent directory.

    `data/scratch/` only. `data/cleared/` is never written from this module and is
    never auto-created (§15) — `review.py` owns that directory, and this function
    is not how it would be reached anyway.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target


def _queue_for_review(result: CurationResult, eligible: list[dict], scenario: dict,
                      cfg: Settings) -> None:
    """Curation's survivors go to `data/scratch/candidates_for_review.jsonl` and
    **nowhere near** `data/cleared/` (§6's second construction proof).

    §6 names this file but gives it no owner, and `run_curation` does not write it
    — so `--review`'s own documented input had no producer. Flagged in the task
    report; built here because `main` is the only place holding both the survivors
    and the records they were probed from.
    """
    by_id = {record["artifact_id"]: record for record in eligible}
    missing = [s["record_id"] for s in result["survivors"] if s["record_id"] not in by_id]
    if missing:
        # Unreachable: `run_curation` only probes records drawn from `eligible`. Loud
        # rather than skipped, because a survivor that cannot be queued is a survivor
        # silently dropped from the dataset — evidence a human paid for and will
        # never see.
        raise AssertionError(
            f"{len(missing)} survivor(s) are not in the eligible pool they were probed "
            f"from: {missing}")
    candidates = [build_review_candidate(by_id[s["record_id"]], s, scenario)
                  for s in result["survivors"]]
    path = write_review_candidates(candidates,
                                   path=Path(cfg.scratch_dir) / CANDIDATES_FILENAME)
    log(f"{len(candidates)} survivor(s) queued for human review at {path}")


def _arm_met_its_bar(decision: ScenarioDecision, arm: str, cfg: Settings | None) -> bool:
    """`scenario_decision._arm_is_sufficient`'s rule, read off the decision's own
    reported counts. Mirrored rather than imported because that function takes a
    `Settings` and this one must work without one (see `report_insufficient_trial`).
    A drift between the two surfaces as "no arm reads as short", which the report
    prints out loud rather than papering over."""
    planned = decision["trial_planned"][arm]
    completed = decision["trial_completed"][arm]
    bar = planned if cfg is None else min(planned, cfg.scenario_trial_min)
    return planned > 0 and completed >= bar


def _mode_counts(result: CurationResult) -> dict[str, int]:
    """Survivor counts per SHIPPED failure mode.

    `evidence_modes` carries SCORER outcome literals (`"violation"`), not shipped
    mode names (`"missed_obligation"`) — `SCORE_OUTCOME_TO_FAILURE_MODE` is §5's
    map for exactly that rename, and skipping it silently reports 0 for the one
    mode the demo depends on. See the task report.
    """
    counts: dict[str, int] = {mode: 0 for mode in ("citation_fabricated", "date_wrong",
                                                   "missed_obligation")}
    for survivor in result["survivors"]:
        for outcome in survivor["evidence_modes"]:
            counts[SCORE_OUTCOME_TO_FAILURE_MODE[outcome]] += 1
    return counts


def _load_cleared(cleared_dir: Path | str) -> list[dict]:
    directory = Path(cleared_dir)
    path = directory / CLEARED_FILENAME
    if not path.is_file():
        raise FileNotFoundError(
            f"no cleared set at {path} — run `run_prep.py --review` first; nothing "
            f"reaches data/cleared/ without a human sign-off (§6)")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else [payload]


def _recorded_resolving_urls(cfg: Settings) -> dict[str, set[str]]:
    """`{record_id: {url, ...}}` from the review queue — the URLs that ACTUALLY
    resolved at probe time, recorded then, read now. This is what `--verify-cleared`
    checks `citation.url` against, and it is why the flag needs no network: the
    resolution already happened, once, at the only moment it was meaningful.

    An absent queue yields `{}` and the citation check is skipped rather than
    failed: a vendored `data/cleared/` (Phase 8) legitimately travels without the
    scratch file that produced it, and failing there would make the flag fail on a
    correct dataset.
    """
    path = Path(cfg.scratch_dir) / CANDIDATES_FILENAME
    if not path.is_file():
        return {}
    recorded: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        candidate = json.loads(line)
        recorded[candidate["source_record"]["artifact_id"]] = {
            url for _, url in candidate["resolving_urls"]}
    return recorded


def _record_id(record) -> str:
    return record.get("id", "?") if isinstance(record, dict) else "?"


def _reject_unknown_flags(args: list[str]) -> None:
    """Refuse an argv this entrypoint does not understand — see `_KNOWN_FLAGS`.

    A value following `--config`/`--reviewer` is skipped rather than inspected, so
    a path or a name is never mistaken for a flag. `--flag=value` forms are matched
    on the flag half.
    """
    index = 0
    while index < len(args):
        arg = args[index]
        flag = arg.split("=", 1)[0]
        if flag.startswith("--"):
            if flag not in _KNOWN_FLAGS:
                raise SystemExit(
                    f"unknown flag {flag!r}. This entrypoint understands only: "
                    f"{', '.join(sorted(_KNOWN_FLAGS))}. Refusing to fall through to the "
                    f"curation flow, which constructs a real client and bills a real key."
                )
            if flag in _FLAGS_TAKING_A_VALUE and "=" not in arg:
                index += 1                    # skip its value; it is not a flag
        index += 1


def _config_path(args: list[str]) -> str:
    return _flag_value(args, "--config") or "config.yaml"


def _flag_value(args: list[str], flag: str) -> str | None:
    """`--flag value` and `--flag=value` both. Returns None when absent."""
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(f"{flag}="):
            return arg.split("=", 1)[1]
    return None


if __name__ == "__main__":       # pragma: no cover
    main()
