"""The one test that reads across the seam (spec §12, §14).

**What it guards.** `scoring_golden.json`, `narrowing_golden.json` and
`buckets_golden.json` are the entire cross-language drift defence. Each is
checked into BOTH `prep/tests/fixtures/` and `template/tests/fixtures/` as a
literal byte-for-byte copy — deliberately not generated from one canonical
source, because goal #1 forbids `template/` having any build-time dependency on
`prep/`.

**Why the copies need their own test.** Each side otherwise tests only its OWN
copy. If one gained a case the other lacked, both suites would stay green while
the parity guarantee silently weakened — and "locked by the golden fixture"
would become a claim standing over no mechanism. That is the defect class this
project has now found repeatedly (§12's own words: a silent divergence here
"would be worse than the bug it replaces"), and an earlier stress-test found the
byte-identity was *claimed but never tested*. This is the test.

**Goal #1 is untouched, and the reason is directional.** Goal #1 forbids
`template/` depending on `prep/`. This is the arrow pointing the other way:
`prep/` reads `template/`'s copy, imports nothing from it, and executes nothing
there. `template/` remains trivially extractable into its own repo — and when it
is extracted, **this suite goes red by design**: noticing that its twin is gone
is precisely this file's job, and `prep/` never ships. (An earlier version of
this docstring claimed the suite "would keep passing" after extraction. It would
not, it should not, and "catches it" and "keeps passing" cannot both be true.)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mastra_prep.schema import validate_cleared_record

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREP_FIXTURES = PROJECT_ROOT / "prep" / "tests" / "fixtures"
TEMPLATE_FIXTURES = PROJECT_ROOT / "template" / "tests" / "fixtures"

# The three duplicated fixtures, named explicitly rather than globbed. An
# ALLOWLIST fails closed: a fourth shared fixture added to only one side must
# be added here deliberately, and `test_fixture_sets_are_identical_on_both_sides`
# catches it in the meantime. A glob over one directory would simply not see the
# file it was missing.
SHARED_FIXTURES = (
    "scoring_golden.json",
    "narrowing_golden.json",
    "buckets_golden.json",
)


@pytest.mark.parametrize("name", SHARED_FIXTURES)
def test_golden_fixtures_are_byte_identical(name: str):
    """Read both copies as BYTES and assert equality (spec §14).

    Bytes, not parsed JSON: two files can parse to equal objects while differing
    in key order, indentation, or unicode escaping — and the vendored file is
    meant to be human-readable as shipped (§5). Byte-identity is the only
    property that makes "literal byte-for-byte copies" checkable.
    """
    prep_path = PREP_FIXTURES / name
    template_path = TEMPLATE_FIXTURES / name

    assert prep_path.is_file(), f"missing prep-side fixture: {prep_path}"
    assert template_path.is_file(), f"missing template-side fixture: {template_path}"

    prep_bytes = prep_path.read_bytes()
    template_bytes = template_path.read_bytes()

    if prep_bytes == template_bytes:
        return

    # A bare `assert a == b` on two ~50KB blobs prints an unreadable diff, and an
    # unreadable failure is one a future maintainer resolves by deleting the
    # test. Name the first divergence instead.
    detail = (
        f"sizes: prep={len(prep_bytes):,}B template={len(template_bytes):,}B"
        if len(prep_bytes) != len(template_bytes)
        else "sizes match; content differs"
    )
    first_diff = next(
        (i for i, (a, b) in enumerate(zip(prep_bytes, template_bytes)) if a != b),
        min(len(prep_bytes), len(template_bytes)),
    )
    start = max(0, first_diff - 60)
    pytest.fail(
        f"{name}: the two copies have DRIFTED — {detail}. First difference at byte "
        f"{first_diff:,}.\n"
        f"  prep     ...{prep_bytes[start:first_diff + 60]!r}\n"
        f"  template ...{template_bytes[start:first_diff + 60]!r}\n"
        f"These fixtures are the entire cross-language drift defence: they must be "
        f"edited in BOTH places or NEITHER. Re-copy the intended side:\n"
        f"  cp {PREP_FIXTURES / name} {TEMPLATE_FIXTURES / name}"
    )


def test_fixture_sets_are_identical_on_both_sides():
    """Neither side may carry a shared golden the other lacks.

    `test_golden_fixtures_are_byte_identical` iterates a NAMED list, so it cannot
    see a fourth `*_golden.json` added to one side only — that file would drift
    freely with both suites green. This closes that gap by comparing the
    directories themselves.
    """
    assert PREP_FIXTURES.is_dir(), f"missing {PREP_FIXTURES}"
    assert TEMPLATE_FIXTURES.is_dir(), f"missing {TEMPLATE_FIXTURES}"

    prep_goldens = {p.name for p in PREP_FIXTURES.glob("*_golden.json")}
    template_goldens = {p.name for p in TEMPLATE_FIXTURES.glob("*_golden.json")}

    assert prep_goldens == template_goldens, (
        f"the two sides carry different golden fixtures — "
        f"prep-only: {sorted(prep_goldens - template_goldens)}, "
        f"template-only: {sorted(template_goldens - prep_goldens)}"
    )
    assert prep_goldens == set(SHARED_FIXTURES), (
        f"a golden fixture exists that this test does not check by name. Add it to "
        f"SHARED_FIXTURES: {sorted(prep_goldens ^ set(SHARED_FIXTURES))}"
    )


@pytest.mark.parametrize("name", SHARED_FIXTURES)
def test_golden_fixtures_are_valid_utf8_json(name: str):
    """A fixture neither side can parse locks nothing.

    Byte-identity alone is satisfied by two identical CORRUPT files, so this
    asserts the bytes are actually loadable as UTF-8 JSON on both sides.
    """
    for base in (PREP_FIXTURES, TEMPLATE_FIXTURES):
        text = (base / name).read_text(encoding="utf-8")
        payload = json.loads(text)
        assert isinstance(payload, dict), f"{base.parent.parent.name}/{name}: expected a JSON object"
        assert payload, f"{base.parent.parent.name}/{name}: is empty"


@pytest.mark.parametrize("name", SHARED_FIXTURES)
def test_golden_fixtures_do_not_escape_non_ascii(name: str):
    """D11: the wire is UTF-8. Escaping non-ASCII inflates the byte count and
    turns a fixture the spec requires to be human-readable into `\\uXXXX` soup.

    Asserted as "no `\\uXXXX` escape survives at the file's own JSON level", which
    is the checkable form: `json.dumps(..., ensure_ascii=False)` emits raw UTF-8
    (`narrowing_golden.json` carries a raw `Bundesanstalt für ...`), so any
    `\\uXXXX` here means someone serialized a nested string with the default
    `ensure_ascii=True`. That is not hypothetical — `scoring_golden.json`'s
    `raw_response` strings are themselves JSON, and building them with the
    default escaped two em-dashes into `\\u2014` until this test was written.
    """
    text = (PREP_FIXTURES / name).read_text(encoding="utf-8")
    escapes = re.findall(r"\\u[0-9a-fA-F]{4}", text)
    assert not escapes, (
        f"{name} carries {len(escapes)} escaped non-ASCII sequence(s) ({sorted(set(escapes))}). "
        f"Serialize with ensure_ascii=False — including for any nested JSON string "
        f"(e.g. judge_cases[].raw_response), whose inner dump defaults to True (D11)."
    )


def test_narrowing_golden_cleared_sets_are_valid_cleared_records():
    """`narrowObligationsPure` is typed `(firm, clearedSet: ClearedRecord[])`, and
    the TS side may Zod-parse this fixture. A `clearedSet` entry that is not a
    real ClearedRecord would lock the narrowing port against a shape that can
    never occur — and would fail `schema.test.ts` if it were ever parsed."""
    payload = json.loads((PREP_FIXTURES / "narrowing_golden.json").read_text(encoding="utf-8"))
    offenders: list[str] = []
    for case in payload["cases"]:
        for record in case["clearedSet"]:
            ok, errors = validate_cleared_record(record)
            if not ok:
                offenders.append(f"{case['name']}/{record.get('id', '?')}: {errors}")
    assert not offenders, f"invalid ClearedRecord(s) in narrowing_golden.json: {offenders}"


def test_narrowing_golden_firm_profiles_use_camelcase_impacted_functions():
    """The firm profile's function key is `impactedFunctions` (camelCase), NOT
    `impacted_functions`. Authorities: `FirmProfileSchema` (spec §8:3319-3325 —
    the executable Zod object), `firmProfileForRecord`'s own return (:3360), §9a's
    match proof (:4150), and §1's module table.

    §9a's `narrowObligationsPure` PSEUDOCODE reads `firm.impacted_functions` at
    :4090 and :4095 — which is `undefined` against a FirmProfileSchema-shaped
    object, i.e. a guardrail that silently narrows on jurisdiction alone. That is
    D15's exact family (executable site right, pseudocode stale) and is FLAGGED
    for a ruling. This test pins the fixture on the executable site's side so a
    P6 implementer copying §9a's snippet verbatim goes red instead of shipping a
    non-narrowing guardrail.

    `record.impacted_functions` IS snake_case — ClearedRecord is snake_case
    throughout (§5). Only the FIRM side is camelCase.
    """
    payload = json.loads((PREP_FIXTURES / "narrowing_golden.json").read_text(encoding="utf-8"))
    for case in payload["cases"]:
        firm = case["firmProfile"]
        assert "impactedFunctions" in firm, f"{case['name']}: firmProfile lacks impactedFunctions"
        assert "impacted_functions" not in firm, (
            f"{case['name']}: firmProfile uses snake_case impacted_functions — "
            f"FirmProfileSchema pins camelCase impactedFunctions"
        )
        assert set(firm) == {"jurisdiction", "sector", "industry", "size", "impactedFunctions"}, (
            f"{case['name']}: firmProfile keys {sorted(firm)} != FirmProfileSchema's"
        )


def test_scoring_golden_carries_all_four_named_groups():
    """§12 pins four named case groups, each naming the function it drives on
    each side. A fixture that lost a group would leave that predicate locked by
    nothing while every suite stayed green — which is exactly what happened to
    `predictsStageAViolation` before §12's round-1 fix added the fourth group."""
    payload = json.loads((PREP_FIXTURES / "scoring_golden.json").read_text(encoding="utf-8"))
    for group in ("citation_date_cases", "judge_cases", "obligation_cases",
                  "stage_a_predicate_cases"):
        assert group in payload, f"scoring_golden.json is missing the {group!r} group"
        assert payload[group], f"scoring_golden.json's {group!r} group is empty"


# `prep_only` marks a case the TypeScript side STRUCTURALLY cannot reproduce. It
# is a hole in the parity guarantee, so every one is named here with its
# justification and the whole set is pinned. Without an allowlist the flag
# quietly becomes a place to park inconvenient cases, and "locked by the golden
# fixture" degrades to a claim standing over a shrinking mechanism.
#
# SPEC STATUS: §4's seam note anticipates exactly ONE (the `not_applicable`
# case). The second — `confidence_nan_discarded` — is a SPEC GAP found by the RC
# review of P1.9 and FLAGGED for an orchestrator ruling; see the case's own
# `note` in the fixture. Do not add a third without one.
EXPECTED_PREP_ONLY_CASES: dict[str, str] = {
    "not_applicable_when_record_is_ineligible_for_the_scenario": (
        "obligation_cases — §4's seam note. The TS port is 3-arg (the template owns "
        "no ScenarioSpec and no isEligible), so `not_applicable` is unreachable there "
        "by construction."
    ),
    "confidence_nan_discarded": (
        "judge_cases — JSON's grammar differs across the seam. Python's json.loads "
        "accepts the non-standard bare `NaN` literal and reaches §4 step 3 (discard -> "
        "the out-of-range rationale); JS JSON.parse rejects it, so step 1 fires and the "
        "id takes the OMISSION fallback -> a different rationale, which §4:2088-2093 "
        "requires to name which case fired. No expected value satisfies both sides. "
        "SPEC GAP — flagged for a ruling."
    ),
}


def test_prep_only_cases_are_justified():
    """Every `prep_only` case is on the allowlist, and nothing else is flagged.

    §4's seam note pins the `obligation_cases` count at exactly 1 and this asserts
    it specifically — the second exception lives in a different group, for a
    different and separately-named structural reason, so it cannot dilute the pin
    the spec actually made.
    """
    payload = json.loads((PREP_FIXTURES / "scoring_golden.json").read_text(encoding="utf-8"))
    groups = ("citation_date_cases", "judge_cases", "obligation_cases", "stage_a_predicate_cases")

    flagged = {c["name"] for g in groups for c in payload[g] if c.get("prep_only")}
    assert flagged == set(EXPECTED_PREP_ONLY_CASES), (
        f"the prep_only set changed. Unexpected: {sorted(flagged - set(EXPECTED_PREP_ONLY_CASES))}; "
        f"missing: {sorted(set(EXPECTED_PREP_ONLY_CASES) - flagged)}. Each prep_only case is a "
        f"named hole in the cross-language parity guarantee and needs a justification here."
    )

    # §4's own pin, asserted as §4 states it — over obligation_cases specifically.
    obligation_prep_only = [c for c in payload["obligation_cases"] if c.get("prep_only")]
    assert len(obligation_prep_only) == 1, (
        f"exactly ONE obligation case may be prep_only (the not_applicable one, §4's "
        f"seam note); found {len(obligation_prep_only)}: "
        f"{[c.get('name') for c in obligation_prep_only]}"
    )
    assert obligation_prep_only[0]["expected_outcome"] == "not_applicable", (
        "the single prep_only obligation case must be the not_applicable one — it is "
        "the only outcome the template's 3-arg port cannot produce (§4's seam note)"
    )

    # These two groups have no structural asymmetry at all: both sides run every case.
    for group in ("citation_date_cases", "stage_a_predicate_cases"):
        offenders = [c.get("name") for c in payload[group] if c.get("prep_only")]
        assert not offenders, (
            f"{group} carries prep_only case(s) {offenders} — no structural asymmetry "
            f"justifies one there; both sides can run every case in this group"
        )


def test_prep_only_cases_each_explain_themselves_in_the_fixture():
    """The allowlist above lives in prep. The fixture is what the TS side reads —
    so the justification has to be IN the fixture too, or a TS implementer sees an
    unexplained skip and reasonably assumes a bug."""
    payload = json.loads((PREP_FIXTURES / "scoring_golden.json").read_text(encoding="utf-8"))
    for group in ("citation_date_cases", "judge_cases", "obligation_cases",
                  "stage_a_predicate_cases"):
        for case in payload[group]:
            if case.get("prep_only"):
                assert case.get("note", "").strip(), (
                    f"{case['name']} is prep_only but carries no `note` explaining why "
                    f"the TypeScript side cannot run it"
                )
