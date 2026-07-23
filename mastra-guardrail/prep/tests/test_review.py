"""`review.py` — the publication gate (spec §6, plan P4.1, decision D25).

**Why these specific tests and not a matrix.** The goal's hard constraint is
*never ship a record that has not been human-reviewed*. Each test below pins one
mechanism that constraint rests on, and each would go red if someone reached for
the convenient shortcut §6's anti-padding table anticipates:

  * no override parameter          -> "synthesizing/paraphrasing records"
  * any 'no' cannot reach approve  -> rubric #2's "provably fails" bar
  * a stray confirmation is rejected -> an attestation nobody made
  * review.py is the only writer   -> "waiving human review"

`input`/`print` are injected everywhere (`prompt=`/`show=`), so a prompted path
is testable without a tty and — the part that matters — a test can assert a
prompt was NEVER issued, which is what "auto-selected with no prompt" means.
"""
from __future__ import annotations

import inspect
import json

import pytest

from mastra_prep.review import (
    OBLIGATION_QUESTIONS,
    ask_obligation_confirmations,
    build_review_candidate,
    load_review_candidates,
    present_for_review,
    record_rejection,
    record_signoff,
    run_review_loop,
    select_citation,
    write_cleared_records,
    write_review_candidates,
)
from mastra_prep.schema import validate_cleared_record
from mastra_prep.scenarios import SCENARIO_A


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _source_record(**overrides) -> dict:
    """`extract_record()`'s FLAT shape (`artifact_id`, never `id` — D15), carrying
    every field `record_signoff` copies into §5's published NESTED shape."""
    base = {
        "artifact_id": "art-0001",
        "topic_id": "topic-7",
        "source_id": "src-3",
        "title": "Guidelines on automated decision-making transparency",
        "regulator_name": "Malta Financial Services Authority",
        "jurisdiction_scope": "national",
        "jurisdiction_country": "MT",
        "jurisdiction_bloc": "EU",
        "jurisdiction_region": None,
        "update_type": "guidance",
        "impact_label": "high",
        "objective": "Set transparency expectations for automated decisions.",
        "what_changed": "Firms must disclose automated decisioning to customers.",
        "why_it_matters": "Undisclosed automated decisioning is now enforceable.",
        "key_requirements": ["Disclose automated decisioning in customer comms"],
        "compliance_date": "2026-09-01",
        "impacted_business": {"size": ["SME"], "type": ["Bank"], "industry": ["Generative AI"],
                              "other_notes": ["dropped by §5"]},
        "impacted_functions": ["Product"],
    }
    base.update(overrides)
    return base


def _probe_result(evidence_modes: list[str], *, urls=(("MFSA BR/99", "https://mfsa.mt/br-99"),)):
    """A `ProbeAndScoreResult` for a survivor. `evidence_modes` carries SCORER
    outcome literals (`"violation"`), not shipped mode names — that rename is
    §5's `SCORE_OUTCOME_TO_FAILURE_MODE`, and a test that fed shipped names here
    would be testing a shape the real pipeline never produces."""
    return {
        "record_id": "art-0001",
        "disqualified_reason": None,
        "resolving_urls": list(urls),
        "stage_a": {"record_id": "art-0001", "draft_text": "We're shipping it next month!",
                    "usage": {}, "called_at": "2026-07-16T10:00:00+00:00"},
        "stage_b": {"record_id": "art-0001", "knows_source": True,
                    "source_name": "MFSA Banking Rule BR/99",
                    "source_url": "https://www.mfsa.mt/invented", "compliance_date": "2026-09-01",
                    "confidence_note": "fairly sure", "usage": {}, "called_at": "x"},
        "judge": {"verdicts": [{"obligation_id": "art-0001", "applies_to_draft": True,
                                "omission_material": True, "verdict": "violation",
                                "confidence": 0.9, "rationale": "No disclosure of automation."}]},
        "citation": {"outcome": "citation_fabricated", "baseline_url": "https://www.mfsa.mt/invented",
                     "matched_ground_truth_url": None, "url_status": "not_found", "is_failure": True},
        "date": {"outcome": "not_applicable", "ground_truth_date": None, "baseline_date": None,
                 "baseline_date_normalized": None, "is_failure": False},
        "obligation": {"outcome": "violation", "confidence": 0.9, "applies_to_draft": True,
                       "omission_material": True, "is_failure": "violation" in evidence_modes},
        "passes_failure_bar": True,
        "evidence_modes": evidence_modes,
    }


def _candidate(evidence_modes: list[str], **overrides):
    candidate = build_review_candidate(_source_record(), _probe_result(evidence_modes), SCENARIO_A)
    candidate.update(overrides)
    return candidate


class _Prompter:
    """Canned answers, in order, with a call log — so a test can assert a prompt was
    never issued, which is the whole content of "auto-selected with no prompt"."""

    def __init__(self, answers: list[str]):
        self._answers = list(answers)
        self.asked: list[str] = []

    def __call__(self, question: str) -> str:
        self.asked.append(question)
        if not self._answers:
            raise AssertionError(f"unexpected prompt: {question!r}")
        return self._answers.pop(0)


def _silent(_message: str) -> None:
    pass


# ---------------------------------------------------------------------------
# The no-edit contract — goal #11's "synthesizing/paraphrasing records".
# ---------------------------------------------------------------------------

def test_record_signoff_has_no_override_parameter():
    """§6's central construction claim: `record_signoff` has NO parameter through
    which any extracted field's value could be supplied or overridden.

    Asserted two ways, because they fail differently. The signature check is what
    stops a `title=` kwarg being ADDED (a live kwarg would pass the TypeError test
    below by being accepted); the TypeError is what proves no such channel exists
    today. Editing extracted prose is paraphrasing a record — goal #11's forbidden
    route to the set — and there is no line between a "redaction" and a paraphrase
    that a schema can enforce, so the only safe contract is no edits at all.
    """
    assert list(inspect.signature(record_signoff).parameters) == [
        "record", "reviewer", "obligation_confirmations"]

    candidate = _candidate(["citation_fabricated"])
    candidate["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}
    with pytest.raises(TypeError):
        record_signoff(candidate, "ana", None, title="a cleaner title")   # type: ignore[call-arg]
    with pytest.raises(TypeError):
        record_signoff(candidate, "ana", None, why_it_matters="clearer")  # type: ignore[call-arg]


def test_signoff_ships_extracted_fields_verbatim():
    """The positive half: every shipped field traces to `extract_record()`'s direct
    output, and `id` is the FLAT record's `artifact_id` renamed — the one place §5's
    published shape and D15's pipeline shape meet."""
    candidate = _candidate(["citation_fabricated"])
    candidate["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}

    cleared = record_signoff(candidate, "ana", None)

    source = candidate["source_record"]
    assert cleared["id"] == source["artifact_id"]
    assert cleared["title"] == source["title"]
    assert cleared["why_it_matters"] == source["why_it_matters"]
    assert cleared["key_requirements"] == source["key_requirements"]
    assert cleared["jurisdiction"] == {"scope": "national", "country": "MT", "bloc": "EU",
                                       "region_name": None}
    assert cleared["human_review"]["attestation"] == "approved"
    assert cleared["human_review"]["reviewer"] == "ana"
    # §5: `other_notes` is dropped — the subset is size/type/industry only.
    assert set(cleared["impacted_business"]) == {"size", "type", "industry"}
    assert validate_cleared_record(cleared) == (True, [])


# ---------------------------------------------------------------------------
# Citation selection — §5's human-review-time decision.
# ---------------------------------------------------------------------------

def test_citation_auto_selected_with_no_prompt_when_exactly_one_resolves():
    """One resolving URL is not a choice, and a prompt with one option trains a
    reviewer to press enter. The `_Prompter` carries no answers: it RAISES if asked."""
    prompter = _Prompter([])

    name, url = select_citation([["MFSA BR/99", "https://mfsa.mt/br-99"]],
                                prompt=prompter, show=_silent)

    assert (name, url) == ("MFSA BR/99", "https://mfsa.mt/br-99")
    assert prompter.asked == []


def test_citation_is_prompted_when_more_than_one_resolves():
    """More than one -> the reviewer MUST pick exactly one, and the pick ships
    verbatim. The invalid first answer proves the loop re-asks rather than
    defaulting — a default here would be the machine choosing the citation."""
    prompter = _Prompter(["9", "2"])

    name, url = select_citation(
        [["MFSA BR/99", "https://mfsa.mt/br-99"], ["EUR-Lex 32026R0451", "https://eur-lex.eu/451"]],
        prompt=prompter, show=_silent)

    assert (name, url) == ("EUR-Lex 32026R0451", "https://eur-lex.eu/451")
    assert len(prompter.asked) == 2


# ---------------------------------------------------------------------------
# The three questions — rubric #2's bar.
# ---------------------------------------------------------------------------

def test_confirmations_return_none_immediately_without_missed_obligation_evidence():
    """`None` IMMEDIATELY — no prompt of any kind. There is nothing to confirm for a
    record admitted on citation/date evidence, and a `True` there would be an
    attestation nobody made."""
    prompter = _Prompter([])

    assert ask_obligation_confirmations(_candidate(["citation_fabricated"]),
                                        prompt=prompter, show=_silent) is None
    assert prompter.asked == []


def test_confirmations_ask_all_three_when_missed_obligation_is_present():
    prompter = _Prompter(["y", "y", "y"])

    answers = ask_obligation_confirmations(_candidate(["violation"]),
                                           prompt=prompter, show=_silent)

    assert answers == {key: True for key, _ in OBLIGATION_QUESTIONS}
    assert len(prompter.asked) == 3
    # Question 1 names the fictional firm rather than an abstraction (§6/§7).
    assert "Aldergrove Labs" in prompter.asked[0]


@pytest.mark.parametrize("position", [0, 1, 2])
def test_any_single_no_makes_the_cli_refuse_to_reach_approve(tmp_path, position):
    """§6's hardest branch: **any** one 'no' rejects outright — the CLI does not
    offer `approve` at all, and offers no way to "keep the record but drop the
    missed_obligation evidence" (that is an edit to `baseline_failures`, forbidden
    by the same no-edits rule as `title`).

    Proven by exhaustion of the prompt queue: the answers list holds ONLY the three
    y/n answers. If the loop went on to ask "approve or reject?", `_Prompter` raises.
    A record either stands on its curated evidence as a whole, or it doesn't ship.
    """
    answers = ["y", "y", "y"]
    answers[position] = "n"
    prompter = _Prompter(answers)
    cleared_dir = tmp_path / "cleared"
    cleared_dir.mkdir()
    rejections = tmp_path / "review_rejections.jsonl"

    outcome = run_review_loop([_candidate(["violation"])], "ana", cleared_dir=cleared_dir,
                              rejections_path=rejections, prompt=prompter, show=_silent)

    assert outcome == {"approved": [], "rejected": ["art-0001"], "failed": []}
    assert not list(cleared_dir.iterdir()), "a rejected record must not reach data/cleared/"
    entry = json.loads(rejections.read_text().strip())
    # The reason names WHICH question triggered the automatic rejection (§6).
    assert OBLIGATION_QUESTIONS[position][0] in entry["reason"]
    assert entry["reviewer"] == "ana"


def test_signoff_refuses_a_no_even_when_called_directly():
    """The loop is one gate; `record_signoff` is the other. A caller reaching past
    the CLI cannot sign off a record the reviewer denied — the gate is in the
    function, not only in the flow around it."""
    candidate = _candidate(["violation"])
    candidate["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}
    confirmations = {key: True for key, _ in OBLIGATION_QUESTIONS}
    confirmations["omission_materiality_confirmed"] = False

    with pytest.raises(ValueError, match="answered 'no'"):
        record_signoff(candidate, "ana", confirmations)


def test_validate_cleared_record_rejects_a_stray_confirmation():
    """A `True` on a record with no `missed_obligation` evidence claims a check that
    never happened. Rejected at the schema gate AND refused by `record_signoff`, so
    it cannot be produced or written."""
    candidate = _candidate(["citation_fabricated"])
    candidate["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}
    cleared = record_signoff(candidate, "ana", None)

    cleared["human_review"]["obligation_applies_confirmed"] = True

    ok, errors = validate_cleared_record(cleared)
    assert not ok
    assert any("must be null" in error for error in errors)

    with pytest.raises(ValueError, match="stray confirmation"):
        record_signoff(candidate, "ana", {"obligation_applies_confirmed": True})


# ---------------------------------------------------------------------------
# The write path.
# ---------------------------------------------------------------------------

def test_approve_writes_to_cleared_and_reject_writes_only_to_scratch(tmp_path):
    """§6's two terminal outcomes, end to end. A rejection produces NO ClearedRecord
    — there is no rejected record in `data/cleared/` behind a flag."""
    cleared_dir = tmp_path / "cleared"
    cleared_dir.mkdir()
    rejections = tmp_path / "review_rejections.jsonl"
    approved = _candidate(["citation_fabricated"])
    rejected = _candidate(["citation_fabricated"])
    rejected["source_record"] = _source_record(artifact_id="art-0002")

    outcome = run_review_loop(
        [approved, rejected], "ana", cleared_dir=cleared_dir, rejections_path=rejections,
        prompt=_Prompter(["approve", "reject", "not a real regulator page"]), show=_silent)

    assert outcome == {"approved": ["art-0001"], "rejected": ["art-0002"], "failed": []}
    shipped = json.loads((cleared_dir / "cleared_records.json").read_text())
    assert [r["id"] for r in shipped] == ["art-0001"]
    assert json.loads(rejections.read_text().strip())["reason"] == "not a real regulator page"


def test_cleared_dir_is_never_auto_created(tmp_path):
    """§15: `data/cleared/` missing -> FileNotFoundError, never `mkdir`. Creating it
    silently turns a wrong `cleared_dir` into a run that writes a real dataset
    somewhere nobody looks."""
    candidate = _candidate(["citation_fabricated"])
    candidate["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}
    cleared = record_signoff(candidate, "ana", None)

    with pytest.raises(FileNotFoundError):
        write_cleared_records([cleared], cleared_dir=tmp_path / "absent")


def test_write_merges_rather_than_truncating(tmp_path):
    """A second review session must not silently destroy the first one's sign-offs —
    the one failure mode here that cannot be cheaply undone."""
    cleared_dir = tmp_path / "cleared"
    cleared_dir.mkdir()
    first = _candidate(["citation_fabricated"])
    first["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}
    second = _candidate(["citation_fabricated"], source_record=_source_record(artifact_id="art-0002"))
    second["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}

    write_cleared_records([record_signoff(first, "ana", None)], cleared_dir=cleared_dir)
    write_cleared_records([record_signoff(second, "bo", None)], cleared_dir=cleared_dir)

    shipped = json.loads((cleared_dir / "cleared_records.json").read_text())
    assert sorted(r["id"] for r in shipped) == ["art-0001", "art-0002"]


# ---------------------------------------------------------------------------
# The candidate queue + the display block.
# ---------------------------------------------------------------------------

def test_build_review_candidate_renames_scorer_outcomes_to_shipped_modes(tmp_path):
    """`evidence_modes` carries the SCORER's `"violation"`; the shipped label is
    `"missed_obligation"` (§5's SCORE_OUTCOME_TO_FAILURE_MODE). `stage` is DERIVED
    from the mode, and `judge_rationale` is non-null IFF missed_obligation."""
    candidate = _candidate(["citation_fabricated", "violation"])

    modes = [f["mode"] for f in candidate["baseline_failures"]]
    assert modes == ["citation_fabricated", "missed_obligation"]
    assert [f["stage"] for f in candidate["baseline_failures"]] == ["B", "A"]
    assert candidate["baseline_failures"][0]["judge_rationale"] is None
    assert candidate["baseline_failures"][1]["judge_rationale"] == "No disclosure of automation."

    path = write_review_candidates([candidate], path=tmp_path / "q.jsonl")
    assert load_review_candidates(path) == [candidate]


def test_present_for_review_shows_evidence_beside_ground_truth_and_no_internals():
    """§6: a mode name alone is a claim; the reviewer's job is to CHECK it, so the
    verbatim baseline excerpt must sit beside the ground truth it is checked
    against. And only what would ship — no raw paths, no `output_data` internals."""
    candidate = _candidate(["violation"])

    block = present_for_review(candidate, candidate["resolving_urls"])

    assert "Guidelines on automated decision-making transparency" in block   # title
    assert "Malta Financial Services Authority" in block                     # regulator
    assert "Disclose automated decisioning in customer comms" in block       # ground truth
    assert "We're shipping it next month!" in block                          # verbatim baseline
    assert "No disclosure of automation." in block                           # judge rationale
    assert "applies_to_draft" in block and "omission_material" in block      # §6's judge context
    assert "auto-selected" in block                                          # one URL resolved
    assert "output_data" not in block


def test_rejection_log_appends_rather_than_overwriting(tmp_path):
    """Two rejections, two lines. `data/scratch/review_rejections.jsonl` is the ONLY
    place a rejection's reason lives (§5: no `notes` field exists on a shipped
    record for a reviewer to leave commentary that might drift from the source)."""
    path = tmp_path / "review_rejections.jsonl"
    record_rejection(_candidate(["citation_fabricated"]), "ana", "first", rejections_path=path)
    record_rejection(_candidate(["citation_fabricated"]), "ana", "second", rejections_path=path)

    entries = [json.loads(line) for line in path.read_text().splitlines()]
    assert [e["reason"] for e in entries] == ["first", "second"]
    assert all(set(e) == {"record_id", "reviewer", "reason", "rejected_at"} for e in entries)


def test_write_refuses_to_launder_an_unreviewed_record_already_on_disk(tmp_path):
    """Being the sole writer does not establish that everything in the file went
    through the gate: this writer RE-EMITS what it finds, under its own authorship.
    So a record hand-added between sessions must be refused on merge, not carried
    forward by the next approve — otherwise the gate launders it."""
    cleared_dir = tmp_path / "cleared"
    cleared_dir.mkdir()
    smuggled = {"id": "art-9999", "title": "snuck in", "human_review": {"attestation": "approved"}}
    (cleared_dir / "cleared_records.json").write_text(json.dumps([smuggled]))
    candidate = _candidate(["citation_fabricated"])
    candidate["citation"] = {"name": "MFSA BR/99", "url": "https://mfsa.mt/br-99"}

    with pytest.raises(ValueError, match="launder"):
        write_cleared_records([record_signoff(candidate, "ana", None)], cleared_dir=cleared_dir)


def test_a_bad_record_costs_itself_not_the_rest_of_the_session(tmp_path):
    """`record_signoff` fails CLOSED on a record the schema gate refuses (a null
    `topic_id` is real — `extract_record` resolves a missing path to None). It must
    cost THAT record, not records N+1..137: a reviewer's answers are expensive and
    cannot be cheaply reproduced."""
    cleared_dir = tmp_path / "cleared"
    cleared_dir.mkdir()
    broken = _candidate(["citation_fabricated"],
                        source_record=_source_record(artifact_id="art-bad", topic_id=None))
    good = _candidate(["citation_fabricated"])

    outcome = run_review_loop([broken, good], "ana", cleared_dir=cleared_dir,
                              rejections_path=tmp_path / "r.jsonl",
                              prompt=_Prompter(["approve", "approve"]), show=_silent)

    assert outcome == {"approved": ["art-0001"], "rejected": [], "failed": ["art-bad"]}
    shipped = json.loads((cleared_dir / "cleared_records.json").read_text())
    assert [r["id"] for r in shipped] == ["art-0001"]


def test_the_reviewers_multi_url_pick_is_the_url_that_ships(tmp_path):
    """End to end, because shipping the WRONG citation would be silent: the numbering
    `present_for_review` displays and the numbering `select_citation` accepts must be
    the same numbering, and only a test that runs both against the same list can say
    so. `citation.name`/`.url` are the pick verbatim — never edited or reworded."""
    cleared_dir = tmp_path / "cleared"
    cleared_dir.mkdir()
    candidate = _candidate(["citation_fabricated"])
    candidate["resolving_urls"] = [["MFSA BR/99", "https://mfsa.mt/br-99"],
                                   ["EUR-Lex 32026R0451", "https://eur-lex.eu/451"],
                                   ["MFSA circular", "https://mfsa.mt/circular-12"]]

    block = present_for_review(candidate, candidate["resolving_urls"])
    assert "[2] EUR-Lex 32026R0451 — https://eur-lex.eu/451" in block

    run_review_loop([candidate], "ana", cleared_dir=cleared_dir,
                    rejections_path=tmp_path / "r.jsonl",
                    prompt=_Prompter(["2", "approve"]), show=_silent)

    shipped = json.loads((cleared_dir / "cleared_records.json").read_text())
    assert shipped[0]["citation"] == {"name": "EUR-Lex 32026R0451", "url": "https://eur-lex.eu/451"}
