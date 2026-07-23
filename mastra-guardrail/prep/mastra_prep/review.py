"""Human review — the clearance gate (spec §6, plan P4.1, decision D25).

**This module is THE PUBLICATION GATE.** The goal's hard constraint is *never
ship a record that has not been human-reviewed*, and this file is the mechanism
that makes that true by construction rather than by convention:

  * `record_signoff()` is the ONLY producer of a `ClearedRecord`, and
  * `write_cleared_records()` is the ONLY writer of `data/cleared/`
    (`grep -rn "data/cleared" mastra_prep/` shows no other writer; `run_prep.py`
    reads that directory for `--verify-cleared` and never writes it).

There is **no batch-approve flag** — not here, not in `config.yaml`, not in
`run_prep.py`'s argv. Adding one is the "waiving human review" row of §6's
anti-padding table, and D25 is the record of that cut being proposed once, for
convenience, and reversed.

---

**Why `record_signoff` takes exactly three parameters, and why that is the
point.** An earlier draft of §6 let a reviewer edit `title`/`why_it_matters`
before approving. That is removed: editing extracted annotation text IS
paraphrasing a record, one of goal #11's forbidden ways to reach the set, and
there is no line between "a redaction" and "a paraphrase" that a schema can
enforce. So the contract is no edits at all — enforced by the signature having
no channel through which any extracted field's value could be supplied:

    record_signoff(record, reviewer, obligation_confirmations)

`test_review.py::test_record_signoff_has_no_override_parameter` asserts the
parameter list is exactly those three names, so a future `title=` kwarg cannot
be added without a test going red. Every extracted field in the returned
`ClearedRecord` is copied verbatim off `record["source_record"]`, which came
off disk from `extract_record()`'s output.

---

**DEVIATIONS from §6's pinned surface — all four flagged in the task report.**

1. **The reviewer's citation pick reaches `record_signoff` through the
   candidate, not through a parameter.** §6 says `record_signoff` is a pure
   "attach `human_review` and `citation`" operation while pinning a signature
   with no `citation` parameter. Adding one as an optional 4th kwarg would have
   satisfied the algorithm but weakened the property the plan actually tests
   ("the signature takes only `record`/`reviewer`/`obligation_confirmations`"),
   so the loop instead threads `select_citation`'s result onto the candidate
   (`{**candidate, "citation": ...}`, never a mutation) and `record_signoff`
   reads it there. `ReviewCandidate.citation` is `None` until a human picks it,
   and `record_signoff` raises rather than defaulting — a missing pick fails
   CLOSED.

2. **`ReviewCandidate` and its `data/scratch/candidates_for_review.jsonl`
   writer/reader are defined HERE, and §6 assigns the file to no owner.** §6
   says curation's survivors "are written only to
   `data/scratch/candidates_for_review.jsonl`", but `run_curation` does not
   write it and no plan task creates it — so `--review`'s own documented input
   had no producer. The shape is owned by the module that consumes it;
   `run_prep.py::main` calls `write_review_candidates()` after curation.

3. **`record_rejection` takes an optional `rejections_path`.** §6 pins the
   3-parameter signature AND pins the file the rejection lands in, which the
   signature cannot supply. Optional, defaulting to the real path, per the
   plan's rule for exactly this case: only tests override it.

4. **Trial survivors are NOT reachable by review.** `curate.py`'s docstring says
   "trial survivors go to human review directly, tagged `from_trial`", but
   `ScenarioDecision` (§7) carries only `probed_ids` — no
   `ProbeAndScoreResult` payload — so `run_prep.py` has nothing to build a
   candidate from. Flagged, not worked around: fabricating those candidates
   from ids would mean re-probing (real money) or inventing evidence.

---

**`data/cleared/` is never auto-created** (§15): `write_cleared_records` raises
`FileNotFoundError` if the directory is absent, exactly like `to_json()`. And it
**merges** by id with whatever is already on disk rather than truncating, and
writes after **every** approval rather than at the end of the session: a reviewer
is a human, a session of 137 records will be interrupted, and a crash at record
100 must not discard 100 sign-offs it can never cheaply reproduce.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, TypedDict

from .curate import ProbeAndScoreResult
from .logging_ import log
from .schema import (
    MODEL_CUTOFF,
    MODEL_ID,
    SCORE_OUTCOME_TO_FAILURE_MODE,
    SNAPSHOT_DATE,
    STAGE_OF_MODE,
    BaselineFailure,
    ClearedRecord,
    to_json,
    validate_cleared_record,
)

# §5: "verbatim (<=1000 chars), never paraphrased". The truncation is a LENGTH
# cut on a prefix of the real response — never a summary, never a rewrite.
MAX_EXCERPT_CHARS = 1000

CANDIDATES_FILENAME = "candidates_for_review.jsonl"
REJECTIONS_FILENAME = "review_rejections.jsonl"
CLEARED_FILENAME = "cleared_records.json"

DEFAULT_CANDIDATES_PATH = f"data/scratch/{CANDIDATES_FILENAME}"
DEFAULT_REJECTIONS_PATH = f"data/scratch/{REJECTIONS_FILENAME}"

# §6's three sub-attestation questions, VERBATIM, paired with the
# `HumanReview` key each one answers. The order is the order they are asked.
#
# The `{firm}` placeholder is question 1's "[the fictional firm]" — §7's
# ScenarioSpec supplies the name, so the reviewer is asked about Aldergrove Labs
# or Solmark Capital by name rather than about an abstraction.
OBLIGATION_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("obligation_applies_confirmed",
     "Does this obligation genuinely apply to {firm}'s described activity, not "
     "merely a loosely related topic?"),
    ("artifact_capable_of_violation_confirmed",
     "Is the drafted artifact/action capable of violating this obligation — i.e. is "
     "this the kind of document where the requirement would actually need to appear?"),
    ("omission_materiality_confirmed",
     "Is the omission the judge flagged materially real in this context, not a "
     "technicality?"),
)

_YES = frozenset({"y", "yes"})
_NO = frozenset({"n", "no"})


class HumanReview(TypedDict):
    """§6's structured attestation — deliberately not a single boolean flag.

    `attestation` is `Literal["approved"]` because a rejection never produces a
    `ClearedRecord` at all: there is no such thing as a rejected record living in
    `data/cleared/` behind a flag. A rejection's reason lives ONLY in
    `data/scratch/review_rejections.jsonl`.

    The three confirmations are `None` IFF `missed_obligation` is not among the
    record's evidence modes — `validate_cleared_record` enforces that
    conjunction in both directions (all three `True`, or all three `None`; a
    stray `True` would misrepresent that a check happened when it did not).
    """

    reviewer: str
    reviewed_at: str
    attestation: Literal["approved"]
    obligation_applies_confirmed: bool | None
    artifact_capable_of_violation_confirmed: bool | None
    omission_materiality_confirmed: bool | None


class ReviewCandidate(TypedDict):
    """One survivor, packaged with everything §6 says the reviewer must see —
    and nothing else. See DEVIATION 2 in the module docstring for why this shape
    lives here.

    `source_record` is `extract_record()`'s FLAT shape (`artifact_id`, not `id` —
    D15), carried verbatim. `record_signoff` is what converts it into §5's
    published NESTED shape; no other code does that conversion.

    `citation` is `None` until a human picks one (`select_citation`), and is the
    reviewer's pick verbatim — never edited, never reworded.
    """

    source_record: dict                      # extract_record()'s flat output, verbatim
    scenario: Literal["A", "B"]              # the scenario this record was probed under
    scenario_firm: str                       # §7's fictional firm name, for question 1
    probed_at: str                           # the probe that produced baseline_failures
    resolving_urls: list[list[str]]          # [name, url] pairs — JSON has no tuple
    baseline_failures: list[BaselineFailure]
    judge_context: dict | None               # §6's applies_to_draft/omission_material/
                                             # rationale, shown only when missed_obligation
    citation: dict | None                    # {"name", "url"} — the reviewer's pick


class ReviewOutcome(TypedDict):
    approved: list[str]                      # record ids that reached data/cleared/
    rejected: list[str]                      # record ids a human dropped, reason on disk
    failed: list[str]                        # record ids the SCHEMA gate refused after an
                                             # approve — reported separately because it is a
                                             # data fault, not a review decision, and folding
                                             # it into `rejected` would misattribute it to the
                                             # reviewer


# ---------------------------------------------------------------------------
# The loop — `run_prep.py --review` dispatches straight here.
# ---------------------------------------------------------------------------

def run_review_loop(candidates: list[ReviewCandidate], reviewer: str, *,
                    cleared_dir: Path | str, rejections_path: Path | str = DEFAULT_REJECTIONS_PATH,
                    prompt: Callable[[str], str] = input,
                    show: Callable[[str], None] = print) -> ReviewOutcome:
    """Drive §6's clearance loop over `candidates`. Makes **no API calls** — every
    input it reads was recorded at probe time, and the resolving URLs were resolved
    then too (§5: human review re-resolves nothing).

    Per candidate, in this exact order:
      1. `present_for_review` — everything that would ship, nothing else;
      2. `select_citation` — auto-picked with NO prompt when exactly one URL
         resolved, prompted when more than one;
      3. `ask_obligation_confirmations` — `None` immediately unless
         `missed_obligation` is among the modes;
      4. **any `False` among the three → `record_rejection`, and `approve` is
         never offered.** This is the branch rubric #2 exists for: "provably
         fails" must rest on more than the judge's own say-so, so a reviewer who
         says the obligation does not apply cannot then be asked to approve
         anyway. There is also no "keep the record but drop the
         missed_obligation evidence" option — that is an edit to
         `baseline_failures`, forbidden by the same no-edits rule as `title`. A
         record stands on its curated evidence as a whole, or it doesn't ship.
      5. otherwise the forced choice, with **exactly two** terminal outcomes.

    Each approval is written through immediately (see the module docstring), so
    an interrupted session keeps every sign-off it earned.
    """
    outcome = ReviewOutcome(approved=[], rejected=[], failed=[])

    for index, candidate in enumerate(candidates, start=1):
        record_id = candidate["source_record"]["artifact_id"]
        show(f"\n── record {index} of {len(candidates)} ─────────────────────────────")
        show(present_for_review(candidate, candidate["resolving_urls"]))

        name, url = select_citation(candidate["resolving_urls"], prompt=prompt, show=show)
        picked = {**candidate, "citation": {"name": name, "url": url}}

        confirmations = ask_obligation_confirmations(picked, prompt=prompt, show=show)
        blocking = _blocking_questions(confirmations)
        if blocking:
            reason = ("automatic rejection — answered 'no' to: " + ", ".join(blocking))
            show(f"REJECTED (approve is not offered): {reason}")
            record_rejection(picked, reviewer, reason, rejections_path=rejections_path)
            outcome["rejected"].append(record_id)
            continue

        if _asks_to_approve(prompt, show):
            try:
                cleared = record_signoff(picked, reviewer, confirmations)
                write_cleared_records([cleared], cleared_dir=cleared_dir)
            except ValueError as exc:
                # The gate refused (a null `topic_id`, an unparseable field — real on
                # extracted data, since `extract_record` resolves a missing path to
                # None). Fails CLOSED, which is right; but it must cost THIS record,
                # not records N+1..137. The reviewer sees every complaint and moves on.
                show(f"NOT SHIPPED — {record_id} failed the schema gate: {exc}")
                outcome["failed"].append(record_id)
                continue
            outcome["approved"].append(record_id)
            show(f"APPROVED — {record_id} written to {cleared_dir}/{CLEARED_FILENAME}")
        else:
            reason = prompt("reason for rejection: ").strip() or "(no reason given)"
            record_rejection(picked, reviewer, reason, rejections_path=rejections_path)
            outcome["rejected"].append(record_id)
            show(f"REJECTED — {record_id} dropped; reason logged to {rejections_path}")

    show(f"\nreview complete: {len(outcome['approved'])} approved, "
         f"{len(outcome['rejected'])} rejected, {len(outcome['failed'])} refused by the "
         f"schema gate, {len(candidates)} reviewed")
    return outcome


# ---------------------------------------------------------------------------
# §6's five pinned functions.
# ---------------------------------------------------------------------------

def present_for_review(record: ReviewCandidate, resolving_citations: list) -> str:
    """The formatted block a reviewer reads (§6).

    Shows: title, regulator, jurisdiction, and each `baseline_failures` entry's
    mode + verbatim baseline excerpt **side by side with the ground truth it is
    being checked against** — a mode name alone is a claim, and the reviewer's
    job is to check the claim, not to take it.

    When `missed_obligation` is among the modes, additionally: the scenario
    eligibility result that gated this record into curation at all (§4's
    "applicability is a precondition" fix — shown as CONFIRMATION CONTEXT, not
    re-asked), and the judge's own `applies_to_draft`/`omission_material`/
    `rationale` for that specific verdict.

    Deliberately absent: raw file paths, `output_data` internals, ids of things
    the reviewer cannot act on — only what would ship.
    """
    source = record["source_record"]
    modes = _modes(record)
    lines: list[str] = [
        f"title:        {source.get('title')}",
        f"regulator:    {source.get('regulator_name')}",
        f"jurisdiction: {_jurisdiction_phrase(source)}",
        f"scenario:     {record['scenario']} ({record['scenario_firm']})",
        f"update type:  {source.get('update_type')}  |  impact: {source.get('impact_label')}",
        "",
        "ground truth (verbatim from the annotation — this is what ships):",
        f"  compliance_date: {source.get('compliance_date')}",
        "  key_requirements:",
    ]
    lines += [f"    - {requirement}" for requirement in (source.get("key_requirements") or [])]

    lines += ["", f"baseline failure evidence ({len(record['baseline_failures'])} mode(s)):"]
    for failure in record["baseline_failures"]:
        lines += [
            f"  [{failure['mode']}]  (stage {failure['stage']})",
            f"    baseline said: {failure['baseline_response_excerpt']}",
        ]
        if failure["judge_rationale"] is not None:
            lines.append(f"    judge said:    {failure['judge_rationale']}")

    if "missed_obligation" in modes:
        judge = record["judge_context"] or {}
        lines += [
            "",
            "missed_obligation context (confirmation context — NOT re-asked):",
            f"  scenario eligibility: this record is is_eligible for scenario "
            f"{record['scenario']} — that is a PRECONDITION of it being probed at all (§4)",
            f"  judge applies_to_draft:  {judge.get('applies_to_draft')}",
            f"  judge omission_material: {judge.get('omission_material')}",
            f"  judge confidence:        {judge.get('confidence')}",
            f"  judge rationale:         {judge.get('rationale')}",
        ]

    lines += ["", f"resolving ground-truth URLs ({len(resolving_citations)}):"]
    if len(resolving_citations) == 1:
        name, url = resolving_citations[0]
        lines.append(f"  (auto-selected — only one resolved)  {name} — {url}")
    else:
        lines += [f"  [{i}] {name} — {url}"
                  for i, (name, url) in enumerate(resolving_citations, start=1)]
    return "\n".join(lines)


def select_citation(resolving_citations: list, *,
                    prompt: Callable[[str], str] = input,
                    show: Callable[[str], None] = print) -> tuple[str, str]:
    """Pick the ONE citation that ships, from the URLs that resolved AT PROBE TIME
    (§5). Re-resolves nothing — `resolving_citations` is
    `ProbeAndScoreResult.resolving_urls`, already computed by the URL gate.

    Exactly one element -> auto-selected with **no prompt**: there is no real
    choice to make, and a prompt with one option trains a reviewer to press enter.
    More than one -> the reviewer MUST pick exactly one before `record_signoff`
    can proceed. `name`/`url` are that pick verbatim, never edited or reworded.

    Raises:
        ValueError: on an empty list. Unreachable through the real pipeline (§2's
            URL gate disqualifies a record with zero resolving URLs before it is
            ever probed) — so if it happens, the candidate file is corrupt and
            guessing a citation would be inventing one.
    """
    if not resolving_citations:
        raise ValueError(
            "no resolving ground-truth URL to cite — §2's URL gate should have "
            "disqualified this record before it was probed; refusing to invent a citation"
        )
    if len(resolving_citations) == 1:
        name, url = resolving_citations[0]
        return (name, url)

    while True:
        answer = prompt(f"select the citation to ship [1-{len(resolving_citations)}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(resolving_citations):
            name, url = resolving_citations[int(answer) - 1]
            return (name, url)
        show(f"not a valid option — enter a number from 1 to {len(resolving_citations)}")


def ask_obligation_confirmations(record: ReviewCandidate, *,
                                 prompt: Callable[[str], str] = input,
                                 show: Callable[[str], None] = print) -> dict[str, bool] | None:
    """§6's three yes/no questions, asked **before** the approve/reject choice is
    offered at all.

    Returns `None` **immediately** — with no prompt of any kind — when
    `missed_obligation` is not among the record's evidence modes. There is
    nothing to confirm for a record admitted on citation/date evidence, and a
    `True` recorded there would be an attestation nobody made
    (`validate_cleared_record` rejects exactly that).

    Otherwise returns all three answers. A `False` among them is returned, not
    swallowed: the CALLER routes it to `record_rejection` (see `run_review_loop`),
    which keeps "which question triggered the rejection" available for the
    rejection log.
    """
    if "missed_obligation" not in _modes(record):
        return None

    show("\nthree confirmations are required before approve/reject is offered (§6).\n"
         "any 'no' rejects this record outright — approve will not be offered.")
    answers: dict[str, bool] = {}
    for key, question in OBLIGATION_QUESTIONS:
        answers[key] = _ask_yes_no(question.format(firm=record["scenario_firm"]), prompt, show)
    return answers


def record_signoff(record: ReviewCandidate, reviewer: str,
                   obligation_confirmations: dict[str, bool] | None) -> ClearedRecord:
    """Attach `human_review` and `citation` to `record` and return the shipped
    `ClearedRecord` (§6's `approve` path).

    **Pure.** No I/O, no prompt, no clock beyond `reviewed_at`, and — the point of
    the function — **no parameter through which any extracted field's value could
    be supplied or overridden.** Every one of `title`/`why_it_matters`/`objective`/
    `what_changed`/`key_requirements` is copied verbatim off
    `record["source_record"]`, which is `extract_record()`'s direct output. There
    is no code path here capable of writing edited prose, by construction.

    `attestation` is the literal `"approved"` — this function is only ever called
    on the approve path, and a rejection produces no `ClearedRecord` at all.

    Raises:
        ValueError: if no citation has been picked, if the three-confirmation
            conjunction is broken (a `False`, a `None`, or a stray confirmation on
            a record with no `missed_obligation` evidence), or if the assembled
            record fails `validate_cleared_record`. Every one fails CLOSED — the
            gate refuses rather than shipping a record it cannot vouch for.
    """
    if record.get("citation") is None:
        raise ValueError(
            "record_signoff called before a citation was selected — §5 requires the "
            "reviewer's pick from resolving_urls; there is no default"
        )

    modes = _modes(record)
    blocking = _blocking_questions(obligation_confirmations)
    if blocking:
        raise ValueError(
            f"refusing to sign off a record the reviewer answered 'no' on: {blocking}. "
            f"Any 'no' rejects outright (§6) — approve is not reachable."
        )
    if "missed_obligation" in modes and obligation_confirmations is None:
        raise ValueError(
            "refusing to sign off missed_obligation evidence with no confirmations — "
            "§6's three sub-attestations are required for exactly this evidence mode"
        )
    if "missed_obligation" not in modes and obligation_confirmations is not None:
        raise ValueError(
            "refusing to record confirmations for a record with no missed_obligation "
            "evidence — the three questions are only asked when that evidence exists "
            "(§6); a stray confirmation misrepresents that a check happened"
        )

    source = record["source_record"]
    confirmations = obligation_confirmations or {}
    human_review = HumanReview(
        reviewer=reviewer,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        attestation="approved",
        obligation_applies_confirmed=confirmations.get("obligation_applies_confirmed"),
        artifact_capable_of_violation_confirmed=confirmations.get(
            "artifact_capable_of_violation_confirmed"),
        omission_materiality_confirmed=confirmations.get("omission_materiality_confirmed"),
    )

    cleared = ClearedRecord(
        # D15/§5: the PUBLISHED record is `id`, the PIPELINE record is
        # `artifact_id`. This assignment is the one place the two shapes meet,
        # and it is a rename, not an edit.
        id=source["artifact_id"],
        title=source["title"],
        regulator_name=source["regulator_name"],
        jurisdiction={
            "scope": source.get("jurisdiction_scope"),
            "country": source.get("jurisdiction_country"),
            "bloc": source.get("jurisdiction_bloc"),
            "region_name": source.get("jurisdiction_region"),
        },
        update_type=source["update_type"],
        impact_label=source["impact_label"],
        objective=source["objective"],
        what_changed=source["what_changed"],
        why_it_matters=source["why_it_matters"],
        key_requirements=source["key_requirements"],
        compliance_date=source.get("compliance_date"),
        citation=record["citation"],
        impacted_business=_impacted_business(source),
        impacted_functions=source.get("impacted_functions") or [],
        scenario=record["scenario"],
        baseline_failures=record["baseline_failures"],
        human_review=dict(human_review),
        source={
            "artifact_id": source["artifact_id"],
            "topic_id": source.get("topic_id"),
            "source_id": source.get("source_id"),
            "snapshot_date": SNAPSHOT_DATE,
        },
        probed_at=record["probed_at"],
        model_id=MODEL_ID,
        model_cutoff=MODEL_CUTOFF,
    )

    # to_json validates and raises with EVERY complaint named. Called here, on the
    # gate's own output, so a malformed record cannot reach the writer at all.
    return to_json(cleared)   # type: ignore[return-value]


def record_rejection(record: ReviewCandidate, reviewer: str, reason: str, *,
                     rejections_path: Path | str = DEFAULT_REJECTIONS_PATH) -> None:
    """Log a rejection and drop the record (§6's `reject` path).

    The rejection lands in `data/scratch/review_rejections.jsonl` and **nowhere
    else**: no `ClearedRecord` is produced, nothing is written to
    `data/cleared/`, and no shipped record carries a "rejected" flag or a
    reviewer note. `reason` includes which of the three questions triggered an
    automatic rejection, when one did (`run_review_loop` composes it).

    `rejections_path` is DEVIATION 3 — see the module docstring.
    """
    path = Path(rejections_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "record_id": record["source_record"]["artifact_id"],
        "reviewer": reviewer,
        "reason": reason,
        "rejected_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log(f"review: rejected {entry['record_id']} — {reason}")


# ---------------------------------------------------------------------------
# The write path into data/cleared/ — this module's alone.
# ---------------------------------------------------------------------------

def write_cleared_records(records: list[ClearedRecord], *, cleared_dir: Path | str) -> Path:
    """Merge `records` into `data/cleared/cleared_records.json` and return the path.

    **The only writer of `data/cleared/` in this codebase.** Every element is
    re-validated on the way through `to_json()` — so even a caller that assembled
    a record by hand cannot write an unreviewed one — and existing records are
    MERGED by id rather than truncated, because a second review session must not
    silently destroy the first one's sign-offs.

    **Existing records are re-validated too, not merely preserved.** Being the sole
    writer does not establish that everything in the file went through the gate:
    this function re-emits whatever it finds under its own authorship, so a record
    hand-added between sessions would be laundered by the next `approve` unless it
    is checked here. It is checked here. A `[null]` element (a truncated write, a
    bad merge — the exact input `validate_cleared_record` was hardened against) is
    named rather than raising a `TypeError` from a subscript.

    Raises:
        FileNotFoundError: if `cleared_dir` does not exist. Never auto-created
            (§15) — the directory is part of the repo, and creating it silently
            would turn a wrong `cleared_dir` into a run that writes a real
            dataset somewhere nobody looks.
        ValueError: from `to_json()`, if any record fails the schema gate, or if a
            record ALREADY on disk fails it — refusing to carry an unreviewed
            record forward is the whole point of re-validating them.
    """
    directory = Path(cleared_dir)
    if not directory.is_dir():
        raise FileNotFoundError(
            f"cleared directory not found: {directory} — data/cleared/ is never "
            f"auto-created (§15)")

    path = directory / CLEARED_FILENAME
    merged: dict[str, dict] = {}
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        for i, record in enumerate(existing if isinstance(existing, list) else [existing]):
            ok, errors = validate_cleared_record(record)
            if not ok:
                raise ValueError(
                    f"refusing to merge into {path}: existing record [{i}] is not a valid "
                    f"cleared record ({len(errors)} problem(s): {'; '.join(errors)}). This "
                    f"writer re-emits what it finds, so carrying it forward would launder "
                    f"an unreviewed record through the gate."
                )
            merged[record["id"]] = record
    for record in records:
        validated = to_json(record)
        merged[validated["id"]] = validated

    # ensure_ascii=False per D11: the wire is UTF-8, and §5 requires this file to
    # stay human-readable as vendored into template/src/data/.
    path.write_text(json.dumps(list(merged.values()), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The candidate file — see DEVIATION 2.
# ---------------------------------------------------------------------------

def build_review_candidate(record: dict, result: ProbeAndScoreResult,
                           scenario: dict) -> ReviewCandidate:
    """Package one curation survivor for §6's reviewer.

    `record` is `extract_record()`'s flat shape; `result` is the survivor's
    `ProbeAndScoreResult`; `scenario` is the `ScenarioSpec` it was probed under.
    No prose is generated here: every string either comes off the record verbatim
    or off the probe's own recorded response.
    """
    return ReviewCandidate(
        source_record=record,
        scenario=scenario["id"],
        scenario_firm=scenario["COMPANY"],
        probed_at=(result["stage_a"] or {}).get("called_at", ""),
        resolving_urls=[list(pair) for pair in result["resolving_urls"]],
        baseline_failures=_baseline_failures(result),
        judge_context=_judge_context(result),
        citation=None,
    )


def write_review_candidates(candidates: list[ReviewCandidate], *,
                            path: Path | str = DEFAULT_CANDIDATES_PATH) -> Path:
    """Write the candidate queue `--review` reads. `data/scratch/`, never
    `data/cleared/` — §6's second construction proof is that curation's survivors
    reach scratch and only a human moves them further."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in candidates),
        encoding="utf-8")
    return target


def load_review_candidates(path: Path | str = DEFAULT_CANDIDATES_PATH) -> list[ReviewCandidate]:
    """Read the candidate queue. Raises `FileNotFoundError` if curation has not run
    — a `--review` against no queue is an operator error worth naming, not an
    empty session that reports "0 reviewed" and looks like success."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(
            f"no review queue at {target} — run `run_prep.py` (curation) first; it "
            f"writes every survivor there for review")
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def _blocking_questions(confirmations: dict[str, bool] | None) -> list[str]:
    """The question keys answered `False` — §6's "any 'no' forces rejection
    outright". `None` (not asked) is not a blocker; `False` (asked and denied) is.
    Returned as a list so the rejection log can name WHICH question triggered it."""
    if not confirmations:
        return []
    return [key for key, _ in OBLIGATION_QUESTIONS if confirmations.get(key) is False]


def _modes(record: ReviewCandidate) -> set[str]:
    return {failure["mode"] for failure in record["baseline_failures"]}


def _asks_to_approve(prompt: Callable[[str], str], show: Callable[[str], None]) -> bool:
    """§6's forced choice with EXACTLY two terminal outcomes. No third option, no
    default on an empty answer, no `edit`: the loop re-asks until the reviewer says
    one of the two words. A default here would be a batch-approve flag with extra
    steps."""
    while True:
        answer = prompt("approve or reject this record? [approve/reject]: ").strip().lower()
        if answer == "approve":
            return True
        if answer == "reject":
            return False
        show("answer exactly 'approve' or 'reject' — there is no other outcome (§6)")


def _ask_yes_no(question: str, prompt: Callable[[str], str], show: Callable[[str], None]) -> bool:
    while True:
        answer = prompt(f"{question} [y/n]: ").strip().lower()
        if answer in _YES:
            return True
        if answer in _NO:
            return False
        show("answer 'y' or 'n'")


def _jurisdiction_phrase(source: dict) -> str:
    parts = [source.get("jurisdiction_scope"), source.get("jurisdiction_country"),
             source.get("jurisdiction_bloc"), source.get("jurisdiction_region")]
    return " / ".join(str(p) for p in parts if p) or "(none recorded)"


def _impacted_business(source: dict) -> dict:
    """§5's subset of the raw field: `size`/`type`/`industry` only. `other_notes`
    and the nested `jurisdiction` are dropped as redundant with the top-level
    `jurisdiction`/`why_it_matters`."""
    raw = source.get("impacted_business") or {}
    return {key: (raw.get(key) or []) for key in ("size", "type", "industry")}


def _baseline_failures(result: ProbeAndScoreResult) -> list[BaselineFailure]:
    """`ProbeAndScoreResult`'s scorer outcomes -> §5's `BaselineFailure` entries.

    **`evidence_modes` carries SCORER outcome literals, not shipped mode names.**
    `passes_failure_bar` returns `dimension["outcome"]`, so an obligation failure
    reads `"violation"` — the shipped label is `"missed_obligation"`, and
    `SCORE_OUTCOME_TO_FAILURE_MODE` is the map §5 pins for exactly this rename.
    Comparing `evidence_modes` against a shipped mode name without it is silently
    always-False; see the task report.

    `stage` is DERIVED via `STAGE_OF_MODE`, never set independently.
    """
    failures: list[BaselineFailure] = []
    for outcome in result["evidence_modes"]:
        mode = SCORE_OUTCOME_TO_FAILURE_MODE[outcome]
        failures.append(BaselineFailure(
            mode=mode,
            stage=STAGE_OF_MODE[mode],
            baseline_response_excerpt=_excerpt(mode, result),
            # Non-null IFF missed_obligation: no judge is involved in producing a
            # citation_*/date_* mode, so a rationale on one is evidence that never
            # existed (§5, enforced by validate_cleared_record).
            judge_rationale=(_judge_rationale(result) if mode == "missed_obligation" else None),
        ))
    return failures


def _excerpt(mode: str, result: ProbeAndScoreResult) -> str:
    """The baseline's OWN words, verbatim, truncated to §5's 1000-char cap.

    Stage A's response is free-form prose, so the excerpt is its prefix. Stage B's
    is a structured-output object, so the excerpt renders the fields the baseline
    actually returned — the same `source_name=... source_url=... compliance_date=...`
    rendering the vendored golden fixtures already use, kept identical so the two
    are diffable.
    """
    if mode == "missed_obligation":
        return _clip((result["stage_a"] or {}).get("draft_text") or "")
    stage_b = result["stage_b"] or {}
    return _clip(
        f"source_name={stage_b.get('source_name')!r} "
        f"source_url={stage_b.get('source_url')!r} "
        f"compliance_date={stage_b.get('compliance_date')!r}"
    )


def _clip(text: str) -> str:
    return text if len(text) <= MAX_EXCERPT_CHARS else text[:MAX_EXCERPT_CHARS]


def _judge_rationale(result: ProbeAndScoreResult) -> str:
    verdicts = (result["judge"] or {}).get("verdicts") or []
    return verdicts[0]["rationale"] if verdicts else ""


def _judge_context(result: ProbeAndScoreResult) -> dict | None:
    """§6's extra display block, shown only when missed_obligation is present.
    Reads `ObligationScore` (the SCORED verdict) rather than the raw judge
    response: that is the object §4's rules actually acted on."""
    obligation = result["obligation"]
    if obligation is None or not obligation["is_failure"]:
        return None
    return {
        "applies_to_draft": obligation["applies_to_draft"],
        "omission_material": obligation["omission_material"],
        "confidence": obligation["confidence"],
        "rationale": _judge_rationale(result),
    }


__all__ = [
    "CLEARED_FILENAME",
    "DEFAULT_CANDIDATES_PATH",
    "DEFAULT_REJECTIONS_PATH",
    "OBLIGATION_QUESTIONS",
    "HumanReview",
    "ReviewCandidate",
    "ReviewOutcome",
    "ask_obligation_confirmations",
    "build_review_candidate",
    "load_review_candidates",
    "present_for_review",
    "record_rejection",
    "record_signoff",
    "run_review_loop",
    "select_citation",
    "write_cleared_records",
    "write_review_candidates",
]
