"""The curation loop (spec §3/§4) — the URL gate, the three calls, the three
scorers, and the sweep that stops at exactly the right record.

**The two count caps bind at the RECORD boundary, not the batch boundary.** An
earlier draft checked `target_set_size`/`probe_max_records` only after a complete
`probe_batch_size` batch had run, which overshoots by up to a whole batch: at
`probe_batch_size: 40`, a run sitting at 199 survivors probes all 40 records of
the next batch and ends at up to 239 — 39 records past a ceiling goal #11 states
as a maximum, and it scales with the batch size. `_cap_stop_reason` is therefore
evaluated before EVERY record, before any spend on it; `probe_batch_size` is now
a **logging cadence and nothing else**, which is what
`test_cap_is_identical_across_batch_sizes` pins.

**Four places this module deliberately departs from §3/§4's pinned pseudocode,
each because following it verbatim would be wrong rather than merely different.
All four are flagged in the task report:**

  1. **`record["artifact_id"]`, never `record["id"]`.** §4's `probe_and_score_one`
     and §3's `run_curation` both read `record["id"]`. `extract_record` maps `id`
     -> `artifact_id` (§2's `FIELD_MAP`), and there is no `id` key on the flat
     record shape anywhere downstream of extraction — the pinned line is a
     `KeyError` against the only record shape this function is ever called with.
     `probe.py` and `scenarios.py` already document the same disagreement and
     already use `artifact_id`.
  2. **`cfg.judge_confidence_floor` is threaded EXPLICITLY into
     `score_missed_obligation`.** §4 pins that signature as 4-arg while pinning
     its rule as `confidence >= cfg.judge_confidence_floor` — naming a `cfg` the
     signature cannot receive, so the pinned call site silently takes the
     `MIN_JUDGE_CONFIDENCE_FLOOR` (0.7) default. That is latent while
     `config.yaml` pins the floor AT its minimum, but an operator who RAISES it to
     0.9 would get 0.7 here and admit verdicts in [0.7, 0.9) — a failure in the
     ADMITTING direction, quietly padding the dataset with near-misses the
     operator explicitly tried to exclude. `score_missed_obligation` takes the
     floor as an optional 5th parameter precisely so this call site can be
     correct; a docstring is not a mechanism.
  3. **`CurationResult(...)` is constructed with KEYWORDS.** §3's pseudocode calls
     it positionally (`CurationResult(survivors, probed, budget.spend_so_far_usd,
     stop)`), which a `TypedDict` cannot accept — its constructor is `dict`'s, so
     the positional form is a `TypeError`. §3's own `BudgetExhausted` return uses
     keywords; the other three sites are the ones that drifted.
  4. **`score_citation` is called 3-arg**, passing the gate's `url_cache`, against
     §4's pinned 2-arg call. §4 pins the signature as 2-arg while pinning the
     algorithm as `resolve_url(stage_b.source_url, cache)` — naming a cache the
     signature cannot receive, exactly as (2) names a `cfg` it cannot receive.
     `scoring.py` made the parameter optional for this call site; passing it means
     a URL the gate already resolved is not re-probed to score the same record.

**The call lifecycle is pinned (see `budget.py`), and a retry is a NEW call** with
its own payload, its own reservation, and its own terminal operation. `probe.py`
deliberately does not retry (its docstring delegates §15's retry to this module);
`judge.py` owns its own retry internally, so `run_judge` is called ONCE here —
wrapping it again would give the judge four attempts instead of §15's two.

Intra-package imports: `budget`, `probe`, `judge`, `scoring`, `sampling`,
`logging_`, plus `urls` + `candidates._REG_REFERENCE_KEYS` for §2's gate (§1's
dependency table lists the first five and omits the last two, though §4's step 0
mandates the gate — flagged in the task report; both are downward edges, so the
DAG holds and `test_imports.py::test_no_circular_imports` stays green).
`Settings` and `ScenarioSpec` are imported under TYPE_CHECKING only, as `judge.py`
does with `Settings`: both are used purely as annotations, and PEP 563 (`from
__future__ import annotations`) makes every annotation here a string that is never
evaluated at import time, so the runtime edge would buy nothing.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal, TypedDict

from .budget import BudgetExhausted, SpendBudget
from .candidates import _REG_REFERENCE_KEYS
from .judge import RETRY_BACKOFF_SECONDS, JudgeObligationInput, JudgeResult, run_judge
from .logging_ import log
from .probe import StageAResult, StageBResult, run_stage_a, run_stage_b
from .sampling import stratified_sample_sequence
from .scoring import (
    CitationScore,
    DateScore,
    ObligationScore,
    _normalize_url,
    passes_failure_bar,
    score_citation,
    score_compliance_date,
    score_missed_obligation,
)
from .urls import UrlStatus, extract_urls, resolve_url

if TYPE_CHECKING:
    from .config import Settings
    from .scenarios import ScenarioSpec


class ProbeAndScoreResult(TypedDict):
    record_id: str
    disqualified_reason: Literal["no_resolving_ground_truth_url", "probe_error"] | None
    # "no_resolving_ground_truth_url": §2's URL gate (zero API calls).
    # "probe_error": §15's exhausted-retry path — an API failure, NOT evidence
    # about the baseline. Both mean "this record taught us nothing".
    resolving_urls: list[tuple[str, str]]   # (name, url) pairs that resolved at probe time — §5's
                                            # citation-selection input
    stage_a: StageAResult | None            # None iff disqualified_reason is set
    stage_b: StageBResult | None
    judge: JudgeResult | None
    citation: CitationScore | None
    date: DateScore | None
    obligation: ObligationScore | None
    passes_failure_bar: bool                # always False when disqualified_reason is set
    evidence_modes: list[str]               # always [] when disqualified_reason is set


class CurationResult(TypedDict):
    survivors: list[ProbeAndScoreResult]
    probed: int
    spend_usd: float
    stop_reason: Literal["target_reached", "sweep_cap", "spend_ceiling", "pool_exhausted"]


def run_curation(client, candidates: list[dict], scenario: "ScenarioSpec", cfg: "Settings",
                 budget: SpendBudget, exclude_ids: frozenset[str] = frozenset()) -> CurationResult:
    """Sweep the candidate pool, probing until a stop condition binds (§3).

    PRECONDITION (enforced by the caller, `run_prep.py::main`, not re-checked here):
    every element of `candidates` already satisfies `is_eligible(r, scenario)` (§7)
    — a record with no real connection to the scenario's framing could otherwise be
    probed under it, and an over-broad judge flag would then be "evidence" of a
    mismatch between record and scenario rather than of a baseline failure.

    `exclude_ids`: the records §7's scenario trial ALREADY probed (its winning arm's
    `probed_ids`). Filtered out before probing, so curation measures a FRESH sample
    rather than re-probing the records the winner was chosen for out-performing on
    (§7's winner's-curse note). Their evidence is not lost — trial survivors go to
    human review directly, tagged `from_trial`.

    Four stop conditions, in this priority: (1) a reservation fails
    (`BudgetExhausted` — the hard backstop, and the ONLY stop that can fire
    mid-record, since a record's three calls reserve independently; the record it
    fires on is left probed-but-incomplete and counted in NEITHER `probed` NOR
    `survivors`), (2) `target_set_size` survivors found, (3) `probe_max_records`
    records probed, (4) the pool itself ran out. (2) and (3) are exact and
    unconditional: `len(survivors) <= cfg.target_set_size` and `probed <=
    cfg.probe_max_records` hold on every return path, for every `probe_batch_size`.
    """
    ordered = [record for record in stratified_sample_sequence(candidates, seed=cfg.sample_seed)
               if record["artifact_id"] not in exclude_ids]
    survivors: list[ProbeAndScoreResult] = []
    probed = 0

    for start in range(0, len(ordered), cfg.probe_batch_size):
        for record in ordered[start:start + cfg.probe_batch_size]:
            # PRE-RECORD cap check — before ANY spend on this record, so survivors
            # can never exceed target_set_size and probed can never exceed
            # probe_max_records, not by a batch and not by one. Each
            # probe_and_score_one appends at most ONE survivor and increments
            # probed by exactly ONE, so a check on entry makes both caps exact.
            stop = _cap_stop_reason(survivors, probed, cfg)
            if stop:
                return _result(survivors, probed, budget, stop)
            try:
                result = probe_and_score_one(client, record, scenario, cfg, budget)
            except BudgetExhausted:
                # Never retried (§15) — the ceiling refused, or an accounting anomaly
                # poisoned the budget. Either way the run stops here.
                return _result(survivors, probed, budget, "spend_ceiling")
            probed += 1
            if result["passes_failure_bar"]:
                survivors.append(result)
        # Batching is a PROGRESS-LOGGING concern ONLY — no stop decision is made
        # here. probe_batch_size controls how often this line prints; it has no
        # effect whatsoever on how many records are probed or kept.
        log(f"{len(survivors)} survivors / {probed} probed / ${budget.spend_so_far_usd:.2f} spent")

    # The pool ran out. If the final record simultaneously hit a cap, the CAP is the
    # reported reason — a deterministic tie-break that keeps stop_reason a pure
    # function of the final counts rather than of loop-exit order.
    return _result(survivors, probed, budget,
                   _cap_stop_reason(survivors, probed, cfg) or "pool_exhausted")


def _cap_stop_reason(survivors: list, probed: int, cfg: "Settings") -> str | None:
    """The two COUNT caps, evaluated at the exact record boundary. Priority order
    matches §3's documented list: target before sweep. Returns None when neither cap
    binds and probing may continue."""
    if len(survivors) >= cfg.target_set_size:
        return "target_reached"
    if probed >= cfg.probe_max_records:
        return "sweep_cap"
    return None


def probe_and_score_one(client, record: dict, scenario: "ScenarioSpec", cfg: "Settings",
                        budget: SpendBudget) -> ProbeAndScoreResult:
    """One record: gate it, probe it, judge it, score it (§4).

    0. **URL GATE** (§2 — first, before any LLM call): resolve the record's
       reg-reference URLs over HTTP. If NONE resolve, return immediately with
       `disqualified_reason="no_resolving_ground_truth_url"` — zero
       `budget.reserve()` calls are made and the record never reaches Stage A/B/
       Judge at all. This is what makes such a record "not even eligible to be
       probed" rather than "probed and then discarded".
    1-3. Stage A (draft), Stage B (citation/date), then the Judge — each following
       §3's pinned call lifecycle, each reserved independently. An API error gets
       §15's one retry (a brand-new call); if that also fails the record is
       `disqualified_reason="probe_error"` and is excluded from survivors, because
       an API error is not evidence about the baseline. `BudgetExhausted` /
       `BudgetPoisoned` are NEVER retried and propagate to `run_curation` /
       `decide_scenario`, which stop the run (§3).
    4. Score, in this order — `score_citation` MUST run first, since
       `score_compliance_date` takes its result (§4: a date is only ever judged
       wrong once the citation is confirmed to be THIS record's).

    Always returns a full result, including when `passes_failure_bar` is False, so
    near-misses and gate disqualifications stay inspectable.
    """
    # §2 pins this cache's lifetime as the RUN's, but §4 pins this signature with no
    # cache parameter, so the widest honest scope is one record: the same URL is
    # never re-probed within a record (the gate and score_citation share this dict),
    # but IS re-probed across records. Flagged in the task report.
    url_cache: dict[str, UrlStatus] = {}
    resolving_urls = _resolving_ground_truth_urls(record, url_cache)
    if not resolving_urls:
        return _disqualified(record, "no_resolving_ground_truth_url", [])

    try:
        stage_a = _with_one_retry("stage A", lambda: run_stage_a(client, record, scenario, cfg, budget))
        stage_b = _with_one_retry("stage B", lambda: run_stage_b(client, record, scenario, cfg, budget))
        # run_judge owns §15's retry internally — do NOT wrap it again.
        judge = run_judge(client, [_as_judge_obligation(record)], stage_a["draft_text"], cfg, budget)
    except BudgetExhausted:
        raise                                    # the run stops; this record counts for nothing
    except Exception as exc:
        log(f"record {record['artifact_id']} disqualified: probe_error ({type(exc).__name__}: {exc})")
        return _disqualified(record, "probe_error", resolving_urls)

    citation = score_citation(stage_b, record, url_cache)
    date = score_compliance_date(stage_b, record, citation)
    obligation = score_missed_obligation(record, scenario, judge, record["artifact_id"],
                                         cfg.judge_confidence_floor)   # see docstring deviation 2
    passes, evidence_modes = passes_failure_bar(citation, date, obligation)
    return ProbeAndScoreResult(
        record_id=record["artifact_id"], disqualified_reason=None,
        resolving_urls=resolving_urls, stage_a=stage_a, stage_b=stage_b, judge=judge,
        citation=citation, date=date, obligation=obligation,
        passes_failure_bar=passes, evidence_modes=evidence_modes,
    )


# ── internals ───────────────────────────────────────────────────────────────

def _result(survivors: list[ProbeAndScoreResult], probed: int, budget: SpendBudget,
            stop_reason: str) -> CurationResult:
    """One constructor for all four return paths, so `spend_usd` can never be read
    from anywhere but the budget's own ledger at the moment of the stop."""
    return CurationResult(survivors=survivors, probed=probed,
                          spend_usd=budget.spend_so_far_usd, stop_reason=stop_reason)


def _with_one_retry(stage_name: str, call):
    """§15's "one retry with exponential backoff (1s)" for a Stage A/B API error.

    The retry is a BRAND-NEW call: `run_stage_a`/`run_stage_b` rebuild their payload
    and reserve afresh, and the failed attempt has already terminated its own
    reservation via `terminal_for_exception` before this function ever sees the
    exception. `BudgetExhausted` is never retried (§15) — it means stop, and a retry
    would only re-raise it against an already-refused ceiling.
    """
    try:
        return call()
    except BudgetExhausted:
        raise
    except Exception as exc:
        log(f"{stage_name} call failed ({type(exc).__name__}) — retrying once in "
            f"{RETRY_BACKOFF_SECONDS}s (§15)")
        time.sleep(RETRY_BACKOFF_SECONDS)
    return call()   # if this one fails too, it propagates -> disqualified_reason="probe_error"


def _as_judge_obligation(record: dict) -> JudgeObligationInput:
    """§4's one-line adapter — the SAME shape §9b's runtime verdict stage builds from
    `data/cleared/` records, keeping "what the judge is shown" identical in both
    places. §4 names it `as_judge_obligation` but gives it no owning module and no
    caller outside this one; kept private here rather than claiming a package-level
    symbol (§1's pinned `__init__.py` block re-exports only `run_curation` from this
    module). Flagged in the task report.
    """
    return JudgeObligationInput(
        id=record["artifact_id"],                 # NOT record["id"] — see deviation 1
        title=record["title"],
        key_requirements=record["key_requirements"],
        objective=record["objective"],
    )


def _resolving_ground_truth_urls(record: dict, cache: dict[str, UrlStatus]) -> list[tuple[str, str]]:
    """§2's gate + §5's citation-selection input in one pass: every reg-reference URL
    that RESOLVES over HTTP at probe time, paired with its `name`.

    This repeats `candidates._reg_reference_urls`' lane walk rather than calling it,
    because that function's `list[str]` return cannot carry §5's `name` — which is
    read off the CONTAINING string and so must be computed during the walk, not
    after it. It is kept honest by sharing both of that function's inputs
    (`_REG_REFERENCE_KEYS` and `extract_urls`), so the two admit the same URL set
    today; note this is shared inputs, not a shared mechanism — a filter added
    INSIDE `_reg_reference_urls` would not propagate here. That matters because
    `scoring.py` builds ground truth from `_reg_reference_urls`' full, unfiltered
    output, so the two must agree about WHICH urls are ground truth (they do: this
    function's output is a resolution-filtered subset of the same set, and §4
    deliberately still scores a baseline citing a 404-ing ground-truth URL as
    `citation_correct`).

    Deduplicated on `scoring._normalize_url`'s key — the same rule that decides
    whether the baseline's citation IS a ground-truth URL — so a document cited from
    two lanes as `.../oj` and `.../oj/` is one citation choice for §6's reviewer, not
    two. The first occurrence wins, keeping the URL as its own prose renders it.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key in _REG_REFERENCE_KEYS:
        lane = record.get(key)
        if not isinstance(lane, list):
            continue
        for entry in lane:
            if not isinstance(entry, str):
                continue
            for url in extract_urls(entry):
                if _normalize_url(url) in seen or resolve_url(url, cache) != "resolves":
                    continue
                seen.add(_normalize_url(url))
                pairs.append((_citation_name(entry, url), url))
    return pairs


def _citation_name(entry: str, url: str) -> str:
    """§5's `name`: "the containing string's text before the parenthetical URL,
    trimmed". Falls back to the URL itself when the prose is nothing but the URL —
    §6 shows this string to a human, and an empty label is worse than a redundant
    one."""
    head = entry[:entry.find(url)].strip()
    return head.rstrip("([<").strip() or url


def _disqualified(record: dict, reason: str,
                  resolving_urls: list[tuple[str, str]]) -> ProbeAndScoreResult:
    """Both disqualification paths, in one shape: no stages, no scores, no evidence,
    `passes_failure_bar=False` — a record that taught us nothing, still returned in
    full so it stays inspectable in the probe log."""
    return ProbeAndScoreResult(
        record_id=record["artifact_id"], disqualified_reason=reason,
        resolving_urls=resolving_urls, stage_a=None, stage_b=None, judge=None,
        citation=None, date=None, obligation=None,
        passes_failure_bar=False, evidence_modes=[],
    )
