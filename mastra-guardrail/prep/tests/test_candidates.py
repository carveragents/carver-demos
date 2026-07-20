"""Tests for `mastra_prep.candidates` — spec §2's candidate filter.

This module is the project's **anti-padding floor** (goal #3, goal #11): the
filter is never relaxed, and the levers that would relax it are code constants
with no config override. The tests are written against that contract, not just
the API:

  * `ACTIONABLE_UPDATE_TYPES` is a `frozenset` CODE constant — widening it takes
    a code change and review, never a runtime flag (§6's anti-padding table).
  * `impact_label == "high"` is a hardcoded literal comparison — same reason.
  * `SNAPSHOT_DATE` is a CODE constant, never a `config.yaml` key — an earlier
    draft exposed it, which would have let `"3000-01-01"` silently defeat the
    date-rot upper bound (§13).
  * `assert_cutoff_margin` enforces the **DERIVATION** (`MODEL_CUTOFF` +
    `CUTOFF_MARGIN_DAYS`, inclusive convention), never a hardcoded floor — a bare
    literal independent of the pinned model is the exact hole V9 exists to close,
    because §8 advertises the model swap as a one-line change.

Both date bounds are load-bearing and are tested separately (§2): the corpus's
`reconciled_published_date` really does span 1442 -> 2569, and `valid` is an
upstream flag of unknown semantics that demonstrably does not catch the rot.
"""
from __future__ import annotations

from datetime import date

import pytest

from mastra_prep.budget import CUTOFF_MARGIN_DAYS, CUTOFF_MARGIN_IS_INCLUSIVE, MODEL_CUTOFF
from mastra_prep.candidates import (
    ACTIONABLE_UPDATE_TYPES,
    CANDIDATE_CUTOFF_DATE,
    SNAPSHOT_DATE,
    assert_cutoff_margin,
    filter_candidates,
    is_candidate,
)

# A real-shaped reg-reference string: free-text prose with an embedded URL, which
# is the ONLY form the corpus carries (§2 — there is no structured URL field).
_REG_RULE_WITH_URL = (
    "Commission Implementing Regulation (EU) 2021/451 of 17 December 2020 "
    "(https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32021R0451)"
)


def make_extracted(**overrides) -> dict:
    """A minimal EXTRACTED record (post-`extract_record`, i.e. `FIELD_MAP`'s flat
    output keys) that passes every predicate. Tests override one key at a time so
    each predicate is exercised in isolation.
    """
    record = {
        "artifact_id": "rec-001",
        "reconciled_pub_valid": True,
        "reconciled_published_date": "2026-04-15",
        "update_type": "enforcement",
        "impact_label": "high",
        "key_requirements": ["Submit the Q2 return by 2026-08-01."],
        "reg_rules": [_REG_RULE_WITH_URL],
        "reg_statutes": [],
        "reg_other_ref": [],
    }
    record.update(overrides)
    return record


def make_raw(artifact_id: str = "rec-001", **overrides) -> dict:
    """A RAW annotation record (nested `output_data` shape) that survives
    `extract_record` -> `is_candidate`. Used only for `filter_candidates`, which
    takes the raw stream straight off `stream_annotations` (§3's pinned
    `main`: `filter_candidates(stream_annotations(cfg.annotations_path))`).
    """
    raw = {
        "id": artifact_id,
        "output_data": {
            "scores": {"impact": {"label": "high"}},
            "classification": {"update_type": "enforcement"},
            "metadata": {
                "impact_summary": {"key_requirements": ["Do the thing."]},
                "reg_references": {"rules": [_REG_RULE_WITH_URL]},
            },
            "reconciled_published_date": {"date": "2026-04-15", "valid": True},
        },
    }
    raw.update(overrides)
    return raw


# ── The baseline: the fixture itself must pass, or every negative test is vacuous ──


def test_fully_valid_record_is_a_candidate():
    passes, failed = is_candidate(make_extracted())

    assert passes is True
    assert failed == []


# ── Date bounds — BOTH are load-bearing (§2) ──


def test_cutoff_date_boundary_is_inclusive():
    """`2026-03-01` (goal #3's locked date) passes; `2026-02-28` fails."""
    passes_on, _ = is_candidate(make_extracted(reconciled_published_date="2026-03-01"))
    passes_before, failed_before = is_candidate(
        make_extracted(reconciled_published_date="2026-02-28")
    )

    assert passes_on is True
    assert passes_before is False
    assert "reconciled_published_date" in failed_before


def test_snapshot_date_boundary_is_inclusive():
    """`2026-07-11` (the snapshot) passes; `2026-07-12` fails."""
    passes_on, _ = is_candidate(make_extracted(reconciled_published_date="2026-07-11"))
    passes_after, failed_after = is_candidate(
        make_extracted(reconciled_published_date="2026-07-12")
    )

    assert passes_on is True
    assert passes_after is False
    assert "reconciled_published_date" in failed_after


def test_snapshot_upper_bound_catches_rot_even_when_valid_flag_lies():
    """The corpus's `reconciled_published_date` spans 1442 -> 2569 (goal.md).

    A year-2569 parse is `>= 2026-03-01` and is marked `valid=True` by whatever
    produced it, so the lower bound and the `valid` flag BOTH admit it. Only the
    `<= SNAPSHOT_DATE` upper bound rejects it — no real record can be published
    after the snapshot was taken. This test proves the upper bound, not `valid`,
    is doing the work.
    """
    rotten = make_extracted(reconciled_published_date="2569-01-01", reconciled_pub_valid=True)

    passes, failed = is_candidate(rotten)

    assert passes is False
    assert "reconciled_published_date" in failed


def test_underflow_rot_is_caught_by_the_lower_bound():
    """The other end of the corpus's rot (1442 — a Hijri-calendar mis-parse)."""
    passes, failed = is_candidate(make_extracted(reconciled_published_date="1442-01-01"))

    assert passes is False
    assert "reconciled_published_date" in failed


def test_valid_flag_false_fails():
    passes, failed = is_candidate(make_extracted(reconciled_pub_valid=False))

    assert passes is False
    assert "reconciled_published_date" in failed


@pytest.mark.parametrize("bad_date", ["", None, "not-a-date", "2026-13-01", 20260415])
def test_unparseable_date_fails_without_raising(bad_date):
    passes, failed = is_candidate(make_extracted(reconciled_published_date=bad_date))

    assert passes is False
    assert "reconciled_published_date" in failed


# ── update_type — the allow-list is a CODE constant ──


@pytest.mark.parametrize("update_type", sorted(ACTIONABLE_UPDATE_TYPES))
def test_each_actionable_update_type_passes(update_type):
    """NOTE: this parametrizes FROM the system under test, so it cannot detect a
    widened allow-list — adding `"press release"` to the frozenset would simply
    generate a case asserting it passes, and go green.

    `test_actionable_update_types_is_exactly_the_measured_eight` below is what
    actually guards that, by pinning the eight literals independently. **The two
    are a pair; the sibling is load-bearing — do not delete it as redundant.**
    """
    passes, failed = is_candidate(make_extracted(update_type=update_type))

    assert passes is True, f"{update_type!r} should be actionable; failed={failed}"


def test_actionable_update_types_is_exactly_the_measured_eight():
    """goal.md's measured pool breakdown: 2016+1637+1391+1235+864+645+439+33 =
    8,260 — the stated candidate pool. The allow-list is that breakdown's key
    set, not an independently invented list.
    """
    assert ACTIONABLE_UPDATE_TYPES == frozenset(
        {
            "enforcement",
            "advisory",
            "guidance",
            "bulletin",
            "final rule",
            "proposed rule",
            "comment request",
            "standard",
        }
    )
    assert isinstance(ACTIONABLE_UPDATE_TYPES, frozenset)


@pytest.mark.parametrize(
    "noise_type",
    ["press release", "other", "speech", "event announcement", "newsletter", "insights", "trend report"],
)
def test_noisy_update_types_fail(noise_type):
    """goal #3's excluded-by-omission list — `press release` alone is 98,826 of
    the corpus's 212,845 records.
    """
    passes, failed = is_candidate(make_extracted(update_type=noise_type))

    assert passes is False
    assert "update_type" in failed


@pytest.mark.parametrize("messy", ["  Enforcement  ", "FINAL RULE", "Comment Request"])
def test_update_type_is_lowercased_and_stripped(messy):
    passes, failed = is_candidate(make_extracted(update_type=messy))

    assert passes is True, f"{messy!r} should normalize into the allow-list; failed={failed}"


@pytest.mark.parametrize("missing", [None, "", 42])
def test_missing_or_non_string_update_type_fails(missing):
    passes, failed = is_candidate(make_extracted(update_type=missing))

    assert passes is False
    assert "update_type" in failed


# ── impact_label — a hardcoded literal, no override path ──


@pytest.mark.parametrize("label", ["medium", "low", "", None, "HIGH ", "high impact"])
def test_only_exact_high_impact_passes(label):
    """goal #11 forbids admitting `medium`/`low` to hit a number. The comparison
    is a literal `== "high"`; nothing normalizes a near-miss into a pass.
    """
    passes, failed = is_candidate(make_extracted(impact_label=label))

    assert passes is False
    assert "impact_label" in failed


# ── key_requirements ──


@pytest.mark.parametrize("empty", [[], None, "", "a string, not a list"])
def test_empty_key_requirements_fails(empty):
    passes, failed = is_candidate(make_extracted(key_requirements=empty))

    assert passes is False
    assert "key_requirements" in failed


@pytest.mark.parametrize("blank", [[""], ["   "], ["", "  "], [None], [""], ["\n\t"]])
def test_key_requirements_of_only_blanks_fails(blank):
    """goal #3 requires "non-empty `impact_summary.key_requirements`" — i.e. the
    record actually STATES an obligation. `[""]` is a non-empty list carrying no
    obligation, and it would render an empty requirement into the probe's prompt.
    Tightening, never loosening (goal #11).
    """
    passes, failed = is_candidate(make_extracted(key_requirements=blank))

    assert passes is False
    assert "key_requirements" in failed


def test_key_requirements_with_one_real_entry_among_blanks_passes():
    passes, failed = is_candidate(make_extracted(key_requirements=["", "Submit the return."]))

    assert passes is True, f"one real obligation is enough; failed={failed}"


# ── reg-reference URLs — well-formed only at filter time (cost control, §2) ──


def test_well_formed_but_unresolved_url_still_passes_filter_time_check():
    """Filter time is FREE and syntactic: HTTP resolution happens later, only for
    records that survive the probe (§2's two-phase pipeline — resolving 8,260
    URLs up front is wasted work when <5% are ever probed). A URL that would 404
    must still pass HERE.
    """
    record = make_extracted(
        reg_rules=["Some Rule (https://regulator.example.invalid/definitely-not-there)"]
    )

    passes, failed = is_candidate(record)

    assert passes is True, f"filter-time check must be syntactic only; failed={failed}"


@pytest.mark.parametrize("lane", ["reg_rules", "reg_statutes", "reg_other_ref"])
def test_url_may_come_from_any_reg_reference_lane(lane):
    record = make_extracted(reg_rules=[], reg_statutes=[], reg_other_ref=[])
    record[lane] = [_REG_RULE_WITH_URL]

    passes, failed = is_candidate(record)

    assert passes is True, f"a URL in {lane} should satisfy the predicate; failed={failed}"


def test_no_reg_reference_url_fails():
    record = make_extracted(reg_rules=[], reg_statutes=[], reg_other_ref=[])

    passes, failed = is_candidate(record)

    assert passes is False
    assert "reg_reference_url" in failed


@pytest.mark.parametrize(
    "malformed",
    [
        "Regulation 2021/451 with no link at all",
        "See ftp://files.example.gov/doc.pdf",
        "See www.example.gov/doc",
    ],
)
def test_malformed_or_non_http_url_fails(malformed):
    record = make_extracted(reg_rules=[malformed], reg_statutes=[], reg_other_ref=[])

    passes, failed = is_candidate(record)

    assert passes is False
    assert "reg_reference_url" in failed


def test_none_reg_reference_lanes_do_not_raise():
    record = make_extracted(reg_rules=None, reg_statutes=None, reg_other_ref=None)

    passes, failed = is_candidate(record)

    assert passes is False
    assert "reg_reference_url" in failed


# ── is_candidate evaluates ALL predicates (§2: does not short-circuit) ──


def test_failed_predicates_are_complete_not_short_circuited():
    """§2 pins this: `failed_predicate_names` must be COMPLETE for
    debugging/reporting, so every predicate is evaluated even after one fails.
    """
    all_bad = make_extracted(
        reconciled_published_date="2026-01-01",
        update_type="press release",
        impact_label="medium",
        key_requirements=[],
        reg_rules=[],
        reg_statutes=[],
        reg_other_ref=[],
    )

    passes, failed = is_candidate(all_bad)

    assert passes is False
    assert set(failed) == {
        "reconciled_published_date",
        "update_type",
        "impact_label",
        "key_requirements",
        "reg_reference_url",
    }


# ── filter_candidates ──


def test_filter_candidates_yields_extracted_records():
    out = list(filter_candidates([make_raw("rec-001")]))

    assert len(out) == 1
    # extract_record()'s flat output shape, not the raw nested one.
    assert out[0]["artifact_id"] == "rec-001"
    assert out[0]["impact_label"] == "high"
    assert "output_data" not in out[0]


def test_filter_candidates_drops_non_candidates():
    keep = make_raw("keep-me")
    drop = make_raw("drop-me")
    drop["output_data"]["classification"]["update_type"] = "press release"

    out = list(filter_candidates([keep, drop]))

    assert [r["artifact_id"] for r in out] == ["keep-me"]


def test_filter_candidates_drops_unrecoverable_records():
    """`extract_record` returns None when `id` is missing — never a KeyError."""
    no_id = make_raw()
    del no_id["id"]

    out = list(filter_candidates([no_id, make_raw("ok")]))

    assert [r["artifact_id"] for r in out] == ["ok"]


def test_duplicate_ids_deduped():
    """The SOLE dedup layer in the package (§2) — first occurrence in file order
    wins; no other module repeats or relies on a second pass.
    """
    first = make_raw("dup")
    first["output_data"]["classification"]["metadata"] = {"title": "the first one"}
    second = make_raw("dup")
    second["output_data"]["classification"]["metadata"] = {"title": "the later one"}

    out = list(filter_candidates([first, second, make_raw("other")]))

    assert [r["artifact_id"] for r in out] == ["dup", "other"]
    assert out[0]["title"] == "the first one"


def test_a_rejected_record_still_claims_its_artifact_id():
    """"First occurrence **in file order** wins" (§2) — not "first *passing*
    occurrence wins". The distinction is invisible when both copies pass, which is
    why `test_duplicate_ids_deduped` cannot catch it.

    It matters because the two readings fail in opposite directions. If `seen`
    were populated only by records that PASS, a later re-annotation of the same
    artifact (say `impact_label` revised `medium` -> `high`) would be admitted
    after the first copy was rejected — **widening the pool**, which is the padding
    direction, reached by accident. goal #11 says pay the yield in exactly this
    ambiguity: the filter is a floor, and a record whose first occurrence failed
    does not get a second audition.
    """
    rejected = make_raw("dup")
    rejected["output_data"]["scores"]["impact"]["label"] = "medium"
    later_passing = make_raw("dup")

    out = list(filter_candidates([rejected, later_passing]))

    assert out == [], "a rejected first occurrence must consume its artifact_id"


def test_filter_candidates_is_lazy():
    """It must stay a generator over the stream: the real file is ~1.8 GB and
    `stream_annotations` is a generator by design (goal #13).
    """
    consumed: list[str] = []

    def stream():
        for artifact_id in ("a", "b", "c"):
            consumed.append(artifact_id)
            yield make_raw(artifact_id)

    it = filter_candidates(stream())
    first = next(it)

    assert first["artifact_id"] == "a"
    assert consumed == ["a"], "filter_candidates must not drain the stream eagerly"


# ── assert_cutoff_margin — the DERIVATION, not a literal (V9) ──


def test_cutoff_is_derived_from_model(monkeypatch):
    """With the shipped constants the derived floor is EXACTLY `2026-03-01` —
    goal #3's locked date — so `2026-03-01` passes and `2026-02-28` raises.

    The shipped-floor assertions alone would pass against a HARDCODED
    `if given < date(2026, 3, 1)` just as happily, so they do not, by themselves,
    test a derivation. The third assertion is what earns the name: the floor must
    MOVE when `MODEL_CUTOFF` moves, which no literal can do.
    """
    assert_cutoff_margin("2026-03-01")  # the derived floor — must not raise

    with pytest.raises(ValueError, match="2026-03-01"):
        assert_cutoff_margin("2026-02-28")

    # Derivation, not literal: a different model => a different floor.
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2026-01-01")
    assert_cutoff_margin("2026-01-14")  # 2026-01-01 + 13d — the NEW floor, must not raise
    with pytest.raises(ValueError, match="2026-01-14"):
        assert_cutoff_margin("2026-01-13")


def test_flipping_the_inclusive_convention_moves_the_floor(monkeypatch):
    """`CUTOFF_MARGIN_IS_INCLUSIVE` must be WIRED, not decorative.

    Spec §2:703-705 states the exclusive reading is reachable by changing "one
    constant (`CUTOFF_MARGIN_IS_INCLUSIVE = False`) plus a re-measure of the pool
    — **not** a spec rewrite, because the derivation is now the mechanism rather
    than a literal." That claim is only true if the constant actually feeds the
    arithmetic. A constant that reads like a switch but is wired to nothing is
    this project's signature defect: *a claim of a mechanism, standing over no
    mechanism.*

    This does NOT relitigate the withdrawn 2026-03-02 amendment: the shipped
    constant stays `True` and the shipped floor stays 2026-03-01. It only makes
    the documented escape hatch real — and it can only ever TIGHTEN the floor,
    which is the direction goal #3 permits.
    """
    monkeypatch.setattr("mastra_prep.candidates.CUTOFF_MARGIN_IS_INCLUSIVE", False)

    # 14 CLEAR days after 2026-02-16 is 2026-03-02 — the exclusive reading. The
    # floor moves, and the shipped CANDIDATE_CUTOFF_DATE (2026-03-01) is now below
    # it: the flip demands the constant move too, which IS §2's "plus a re-measure
    # of the pool". That the constant check fires here is the C1 fix working.
    with pytest.raises(ValueError, match="2026-03-02"):
        assert_cutoff_margin("2026-03-01")

    # With the filter constant moved to match, the exclusive floor accepts 03-02
    # and still rejects 03-01 — i.e. the switch moved the arithmetic, not just a
    # message.
    monkeypatch.setattr("mastra_prep.candidates._CANDIDATE_CUTOFF", date(2026, 3, 2))
    assert_cutoff_margin("2026-03-02")  # must not raise
    with pytest.raises(ValueError, match="2026-03-02"):
        assert_cutoff_margin("2026-03-01")


def test_a_model_swap_is_caught_even_when_the_config_is_edited_to_comply(monkeypatch):
    """The hole this test exists to close, reproduced end-to-end before the fix.

    `assert_cutoff_margin` validates `config.yaml`'s `candidate_cutoff_date`, but
    `is_candidate` filters on the `CANDIDATE_CUTOFF_DATE` **code constant** — the
    config key is not wired to the filter at all (its pinned signature,
    `is_candidate(rec: dict)`, cannot receive it). So:

        1. A forker takes §8's advertised one-line model swap -> MODEL_CUTOFF moves later.
        2. Startup raises. The gate fires correctly.
        3. The operator does EXACTLY what the message says and re-derives
           `candidate_cutoff_date` in config.yaml.
        4. Startup now passes -- and the filter still admits from 2026-03-01,
           i.e. from INSIDE the new model's training data.

    **Complying with the error message converts a loud failure into a silent
    corruption** — goal #9's signature mode (*it would appear to succeed*), and
    the exact shape of V9 reopened one level down. So the derivation must also
    check the constant the filter ACTUALLY uses, on every startup.
    """
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2026-06-01")

    # The operator's compliant, re-derived date: 2026-06-01 + 13d.
    with pytest.raises(ValueError) as excinfo:
        assert_cutoff_margin("2026-06-14")

    message = str(excinfo.value)
    assert "CANDIDATE_CUTOFF_DATE" in message, "must name the constant the filter really uses"
    assert "MODEL_CUTOFF" in message, "must name the constant that actually moved"


def test_cutoff_margin_convention_is_inclusive():
    """The convention is NAMED, here and at the constant and in the function
    (goal #3). `CUTOFF_MARGIN_DAYS = 14` counted INCLUSIVELY of the cutoff date
    (the cutoff is day 1) => floor = cutoff + 13 calendar days = 2026-03-01.

    Under the EXCLUSIVE reading the floor would be 2026-03-02, which moves goal
    #3's locked date and its measured 8,260 pool. That amendment was issued and
    WITHDRAWN (orchestrator-decisions.md); this test pins the inclusive reading
    so it cannot drift back silently.
    """
    assert CUTOFF_MARGIN_DAYS == 14
    assert CUTOFF_MARGIN_IS_INCLUSIVE is True
    assert MODEL_CUTOFF == "2026-02-16"

    # The exclusive reading's floor must NOT be the floor: 2026-03-01 is admitted.
    assert_cutoff_margin("2026-03-01")


def test_shipped_candidate_cutoff_constant_satisfies_the_derivation():
    """`CANDIDATE_CUTOFF_DATE` (what `is_candidate` actually filters on) and the
    derived floor (what `load_settings` validates `config.yaml` against) must
    agree — otherwise the two could drift and the filter would enforce a date the
    startup gate never checked.
    """
    assert CANDIDATE_CUTOFF_DATE == "2026-03-01"
    assert_cutoff_margin(CANDIDATE_CUTOFF_DATE)  # must not raise


def test_later_model_cutoff_makes_the_unchanged_date_raise(monkeypatch):
    """§8 advertises the model swap as a one-line change. A forker repointing at
    a model with a LATER cutoff must get a hard, named startup error — not a
    silently corrupted filter admitting documents inside the new model's training
    data (goal #9's signature failure mode: *it would appear to succeed*).

    Patching `candidates.MODEL_CUTOFF` faithfully simulates the post-import state
    of editing `budget.py`'s constant, since `candidates.py` binds it at import.
    """
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2026-06-01")

    with pytest.raises(ValueError) as excinfo:
        assert_cutoff_margin("2026-03-01")

    message = str(excinfo.value)
    assert "2026-06-14" in message, "the floor must MOVE WITH the model"
    assert "re-deriv" in message.lower(), "the error must name the re-derivation goal #3 requires"


def test_earlier_model_cutoff_still_admits_a_more_conservative_date(monkeypatch):
    """goal #3's own asymmetry: this is a FLOOR. You may always be MORE
    conservative than derivation requires and never less.
    """
    monkeypatch.setattr("mastra_prep.candidates.MODEL_CUTOFF", "2025-01-01")

    assert_cutoff_margin("2026-03-01")  # far above the floor — must not raise


@pytest.mark.parametrize("bad", ["", "not-a-date", "2026-02-30"])
def test_assert_cutoff_margin_rejects_unparseable_dates(bad):
    with pytest.raises(ValueError):
        assert_cutoff_margin(bad)


def test_snapshot_date_is_the_measured_snapshot():
    """A CODE constant, never a config key (§13) — `test_config.py` proves the
    config side; this pins the value goal.md measured.
    """
    assert SNAPSHOT_DATE == "2026-07-11"
