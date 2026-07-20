"""Tests for `mastra_prep.scenarios` (spec §7).

Covers `SCENARIO_A`/`SCENARIO_B`, the eligibility predicates (`is_eligible` and
its two module-private NARROWABILITY preconditions), `build_task_instance`, and
the closed negative-control contract (`NEGATIVE_CONTROL_TASKS`,
`NEGATIVE_CONTROL_ARTIFACTS`, `build_negative_control_prompts`).

**Record shape note (spec disagreement, resolved in this file's favor -- see the
task report).** Spec §7's illustrative `is_eligible`/`_jurisdiction_usable`
pseudocode reads `record["jurisdiction"]["country"]` -- a NESTED sub-object. The
already-implemented `mastra_prep.extract.extract_record` (spec §2's own
`FIELD_MAP`, already landed under `mastra_prep/extract.py`) instead FLATTENS
jurisdiction into top-level `jurisdiction_country`/`jurisdiction_bloc` keys --
there is no nested `"jurisdiction"` key anywhere in an extracted record. Every
record `is_eligible`/`build_task_instance` are ever called on, throughout this
package (candidates -> sampling -> scenarios -> curate -> scoring ->
scenario_decision -> run_prep), is `extract_record`'s flat shape. This module
and its tests use that real, already-landed shape rather than the spec
pseudocode's nested illustration, which would KeyError against every real
record. `impacted_business`/`impacted_functions` ARE consistent between the two
(both nest `impacted_business.industry` as a sub-object) -- only `jurisdiction`
differs.

**`buckets_golden.json` note -- RESOLVED (P1.9 has landed).** P1.9 owns
`prep/tests/fixtures/buckets_golden.json` and its `template/` twin. Until it
landed, this file asserted the same invariants INLINE against
`INDUSTRY_TAG_TO_BUCKET` directly (D16 records that deferral as correct: better
than creating a file outside its owning task's scope). The fixture now exists,
so `test_buckets_golden_parity` and `test_buckets_golden_unmapped_tag_defaults`
below read it and make the cross-language mechanism REAL -- `prompts.test.ts`
runs the identical cases against the TypeScript `INDUSTRY_TAG_TO_BUCKET`, so the
two halves cannot drift without one going red. The inline assertions are
deliberately KEPT: they are cheap, they document the intent in place, and a
fixture that silently lost a case would otherwise take its coverage with it.
`prep/tests/test_fixture_parity.py` (P1.10) asserts the two copies of the
fixture are byte-identical -- without that, each side could drift its own copy
and both suites would stay green.
"""
from __future__ import annotations

import json
from pathlib import Path

from mastra_prep.scenarios import (
    DOMAIN_BUCKETS,
    INDUSTRY_TAG_TO_BUCKET,
    NEGATIVE_CONTROL_ARTIFACTS,
    NEGATIVE_CONTROL_TASKS,
    SCENARIO_A,
    SCENARIO_A_KEYWORDS,
    SCENARIO_B,
    SCENARIO_B_COMBINED_TERMS,
    SCENARIO_B_FINANCIAL_TERMS,
    SCENARIO_B_PROMOTIONAL_TERMS,
    _jurisdiction_usable,
    _tag_matches_keyword,
    _topical_signal_usable,
    build_negative_control_prompts,
    build_task_instance,
    is_eligible,
)


def _record(
    *,
    artifact_id: str = "rec-1",
    update_type: str = "guidance",
    country: str | None = None,
    bloc: str | None = None,
    industry: list[str] | None = None,
    functions: list[str] | None = None,
) -> dict:
    """A record in `extract_record`'s REAL, already-landed shape -- flat
    `jurisdiction_country`/`jurisdiction_bloc`, nested `impacted_business`."""
    return {
        "artifact_id": artifact_id,
        "update_type": update_type,
        "jurisdiction_country": country,
        "jurisdiction_bloc": bloc,
        "impacted_business": {"industry": industry if industry is not None else []},
        "impacted_functions": functions if functions is not None else [],
    }


# ---------------------------------------------------------------------------
# `_tag_matches_keyword` -- word-boundary behavior (plan P1.8's own naming)
# ---------------------------------------------------------------------------

def test_tag_matches_keyword_single_word_is_boundary_safe():
    assert _tag_matches_keyword("Generative AI", "ai") is True
    assert _tag_matches_keyword("retail", "ai") is False
    assert _tag_matches_keyword("email", "ai") is False


def test_tag_matches_keyword_multi_word_is_plain_substring():
    assert _tag_matches_keyword("Retail investor protection", "retail investor") is True
    assert _tag_matches_keyword("investor retail protection", "retail investor") is False


# ---------------------------------------------------------------------------
# Scenario A eligibility -- keyword AND jurisdiction (EU/EEA only)
# ---------------------------------------------------------------------------

def test_us_jurisdiction_ai_record_not_eligible_for_a():
    record = _record(country="US", industry=["Artificial Intelligence"])

    assert is_eligible(record, SCENARIO_A) is False


def test_de_jurisdiction_ai_record_eligible_for_a():
    record = _record(country="DE", industry=["Artificial Intelligence"])

    assert is_eligible(record, SCENARIO_A) is True


def test_a_ineligible_without_any_scenario_a_keyword():
    record = _record(country="DE", industry=["Banking"])

    assert is_eligible(record, SCENARIO_A) is False


def test_a_eligible_via_bloc_eu_even_without_country():
    record = _record(country=None, bloc="EU", industry=["algorithmic decision-making"])

    assert is_eligible(record, SCENARIO_A) is True


# ---------------------------------------------------------------------------
# Scenario B eligibility -- financial-domain AND promotional-framing (or a
# single combined term) -- goal's own anti-padding rule, not a flat OR-set.
# ---------------------------------------------------------------------------

def test_marketing_alone_not_eligible_for_b():
    record = _record(country="GB", industry=["marketing"])

    assert is_eligible(record, SCENARIO_B) is False


def test_marketing_plus_consumer_credit_eligible_for_b():
    record = _record(country="GB", industry=["marketing", "consumer credit"])

    assert is_eligible(record, SCENARIO_B) is True


def test_single_combined_term_sufficient_for_b():
    record = _record(country="GB", industry=["financial promotion"])

    assert is_eligible(record, SCENARIO_B) is True


def test_food_advertising_record_not_eligible_for_b():
    """The exact case the task description names: a flat OR-set over
    marketing/advertising alone would wrongly admit food/tobacco advertising.
    Neither term names a financial domain, so this must be False."""
    record = _record(country="GB", industry=["food advertising", "tobacco marketing"])

    assert is_eligible(record, SCENARIO_B) is False


def test_financial_domain_alone_without_promotional_framing_not_eligible_for_b():
    record = _record(country="GB", industry=["securities"])

    assert is_eligible(record, SCENARIO_B) is False


def test_b_is_jurisdiction_general_any_recorded_country_eligible():
    record = _record(country="US", industry=["crypto", "advertising"])

    assert is_eligible(record, SCENARIO_B) is True


# ---------------------------------------------------------------------------
# Narrowability preconditions -- structural, identical for both scenarios.
# A record failing either can never be surfaced by the guardrail's own
# narrowing stage under ANY firm profile (spec §7's Revision callout).
# ---------------------------------------------------------------------------

def test_null_country_and_bloc_not_eligible_for_b():
    record = _record(country=None, bloc=None, industry=["securities", "marketing"])

    assert is_eligible(record, SCENARIO_B) is False


def test_null_country_but_recorded_bloc_eligible_for_b():
    record = _record(country=None, bloc="EU", industry=["securities", "marketing"])

    assert is_eligible(record, SCENARIO_B) is True


def test_recorded_country_no_bloc_eligible_for_b():
    record = _record(country="GB", bloc=None, industry=["securities", "marketing"])

    assert is_eligible(record, SCENARIO_B) is True


def test_empty_topical_signal_not_eligible():
    """Both impacted_business.industry AND impacted_functions empty -> False
    for both scenarios, even with a fully usable jurisdiction, because
    narrowing has neither axis to match on."""
    record_a = _record(country="DE", industry=[], functions=[])
    record_b = _record(country="GB", industry=[], functions=[])

    assert is_eligible(record_a, SCENARIO_A) is False
    assert is_eligible(record_b, SCENARIO_B) is False


def test_empty_topical_signal_becomes_eligible_once_either_list_is_non_empty():
    # industry empty but impacted_functions carries the matching signal
    record = _record(country="DE", industry=[], functions=["algorithmic decision-making"])

    assert is_eligible(record, SCENARIO_A) is True


def test_jurisdiction_usable_true_when_only_bloc_present():
    assert _jurisdiction_usable(_record(country=None, bloc="EU")) is True


def test_jurisdiction_usable_false_when_both_null():
    assert _jurisdiction_usable(_record(country=None, bloc=None)) is False


def test_topical_signal_usable_true_when_only_functions_present():
    assert _topical_signal_usable(_record(industry=[], functions=["Compliance"])) is True


def test_topical_signal_usable_false_when_both_empty():
    assert _topical_signal_usable(_record(industry=[], functions=[])) is False


# ---------------------------------------------------------------------------
# Closed keyword lists -- copied verbatim from spec §7, complete, not a
# "TBD, enumerate at implementation time" placeholder.
# ---------------------------------------------------------------------------

def test_scenario_a_keywords_are_the_closed_spec_set():
    assert SCENARIO_A_KEYWORDS == frozenset({
        "artificial intelligence", "ai", "algorithm", "algorithmic",
        "automated decision-making", "automated profiling", "profiling", "biometric",
        "biometric data", "facial recognition", "emotion recognition", "data protection",
        "data privacy", "gdpr", "personal data", "content moderation",
        "recommender system", "machine learning", "generative ai", "foundation model",
        "ai act", "algorithmic decision-making",
    })


def test_scenario_b_keyword_sets_are_the_closed_spec_sets():
    assert SCENARIO_B_FINANCIAL_TERMS == frozenset({
        "securities", "investment product", "investment advice", "robo-advice",
        "consumer credit", "digital asset", "cryptocurrency", "crypto",
        "consumer finance", "retail investor", "asset management",
        "wealth management", "mifid",
    })
    assert SCENARIO_B_PROMOTIONAL_TERMS == frozenset({
        "marketing", "advertising", "promotion", "promotional", "campaign",
        "solicitation",
    })
    assert SCENARIO_B_COMBINED_TERMS == frozenset({
        "financial promotion", "financial promotions", "credit advertising",
    })


# ---------------------------------------------------------------------------
# ScenarioSpec instances
# ---------------------------------------------------------------------------

def test_scenario_a_fields():
    assert SCENARIO_A["id"] == "A"
    assert SCENARIO_A["PERSONA"] == "a product engineering assistant"
    assert SCENARIO_A["COMPANY"] == "Aldergrove Labs"
    assert SCENARIO_A["TASK_NOUN_PHRASE"] == "feature"
    assert SCENARIO_A["TASK_VERB_PHRASE"] == "shipping"


def test_scenario_b_fields():
    assert SCENARIO_B["id"] == "B"
    assert SCENARIO_B["PERSONA"] == "a marketing copy assistant"
    assert SCENARIO_B["COMPANY"] == "Solmark Capital"
    assert SCENARIO_B["TASK_NOUN_PHRASE"] == "campaign"
    assert SCENARIO_B["TASK_VERB_PHRASE"] == "launching"


# ---------------------------------------------------------------------------
# `build_task_instance` -- no {{}} placeholders survive; fair-test discipline
# spot-check (the FULL leak battery is P2.1's test_probe.py, over real prompt
# files -- this is a sanity check that scenarios.py's own contribution is
# clean).
# ---------------------------------------------------------------------------

def test_build_task_instance_leaves_no_placeholders():
    record = _record(country="DE", industry=["artificial intelligence"])

    instance = build_task_instance(record, SCENARIO_A)

    assert "{{" not in instance["TASK_INSTANCE"]
    assert "}}" not in instance["TASK_INSTANCE"]


def test_build_task_instance_uses_a_domain_bucket_phrase():
    record = _record(country="DE", industry=["artificial intelligence"])

    instance = build_task_instance(record, SCENARIO_A)

    assert instance["DOMAIN_PHRASE"] in DOMAIN_BUCKETS["A"]
    assert instance["DOMAIN_PHRASE"] in instance["TASK_INSTANCE"]


def test_build_task_instance_renders_jurisdiction_phrase_country():
    record = _record(country="DE", industry=["artificial intelligence"])

    instance = build_task_instance(record, SCENARIO_A)

    assert instance["JURISDICTION_PHRASE"] == "Germany"
    assert "Germany" in instance["TASK_INSTANCE"]


def test_build_task_instance_renders_jurisdiction_phrase_eu_bloc():
    record = _record(country=None, bloc="EU", industry=["gdpr"])

    instance = build_task_instance(record, SCENARIO_A)

    assert instance["JURISDICTION_PHRASE"] == "the EU"


def test_build_task_instance_carries_persona_and_company():
    record = _record(country="DE", industry=["artificial intelligence"])

    instance = build_task_instance(record, SCENARIO_A)

    assert instance["PERSONA"] == SCENARIO_A["PERSONA"]
    assert instance["COMPANY"] == SCENARIO_A["COMPANY"]


def test_build_task_instance_falls_back_to_default_bucket_for_unmapped_tags():
    record = _record(country="DE", industry=["some-totally-unmapped-tag"])

    instance = build_task_instance(record, SCENARIO_A)

    assert instance["DOMAIN_PHRASE"] == DOMAIN_BUCKETS["A"][0]


def test_build_task_instance_never_leaks_the_other_scenarios_bucket():
    """A record eligible for BOTH scenarios (spec §7 explicitly allows this)
    whose FIRST tag happens to be the other scenario's keyword must still
    get a bucket phrase from ITS OWN scenario's vocabulary -- the exact
    cross-scenario bucket leak a global (unscoped) keyword search would
    produce: a Scenario-B prompt about a "data processing & retention"
    campaign would be nonsensical and would also violate
    `DOMAIN_PHRASE in DOMAIN_BUCKETS[scenario_id]`."""
    # "data protection" is an A keyword; "asset management" and "marketing"
    # are B keywords (financial + promotional) -- this record is eligible
    # for both scenarios, and "data protection" is listed FIRST.
    record = _record(
        country="GB", industry=["data protection", "asset management", "marketing"],
    )
    assert is_eligible(record, SCENARIO_A) is False  # GB is not EU/EEA -- not A-eligible
    assert is_eligible(record, SCENARIO_B) is True

    instance = build_task_instance(record, SCENARIO_B)

    assert instance["DOMAIN_PHRASE"] in DOMAIN_BUCKETS["B"]
    assert instance["DOMAIN_PHRASE"] not in DOMAIN_BUCKETS["A"]


def test_domain_phrase_stays_within_its_own_scenario_for_every_keyword():
    """For every closed keyword and every scenario, the bucket it resolves to
    (when searched under that scenario) is one of that scenario's OWN bucket
    names -- the general form of the leak-fix invariant above."""
    for scenario_id, keywords in (
        ("A", SCENARIO_A_KEYWORDS),
        ("B", SCENARIO_B_FINANCIAL_TERMS | SCENARIO_B_PROMOTIONAL_TERMS | SCENARIO_B_COMBINED_TERMS),
    ):
        scenario = SCENARIO_A if scenario_id == "A" else SCENARIO_B
        for keyword in keywords:
            record = _record(country="DE" if scenario_id == "A" else "GB", industry=[keyword])
            instance = build_task_instance(record, scenario)
            assert instance["DOMAIN_PHRASE"] in DOMAIN_BUCKETS[scenario_id], (
                f"keyword {keyword!r} under scenario {scenario_id} resolved to "
                f"{instance['DOMAIN_PHRASE']!r}, not in {DOMAIN_BUCKETS[scenario_id]}"
            )


def test_domain_phrase_prefers_more_specific_keyword_over_shorter_substring():
    """"credit advertising" (a SCENARIO_B_COMBINED_TERMS keyword, its own
    bucket) must win over the shorter "advertising" (a
    SCENARIO_B_PROMOTIONAL_TERMS keyword, a different bucket) for a tag
    containing both -- proven by keyword LENGTH, not by which happens to sit
    earlier in `INDUSTRY_TAG_TO_BUCKET`'s literal declaration order."""
    record = _record(country="GB", industry=["credit advertising"])

    instance = build_task_instance(record, SCENARIO_B)

    assert instance["DOMAIN_PHRASE"] == "credit advertising"


# ---------------------------------------------------------------------------
# INDUSTRY_TAG_TO_BUCKET -- inline assertions, KEPT alongside the
# buckets_golden.json parity tests below (P1.9 has landed; see module docstring).
# They are cheap, they document the intent in place, and a fixture that silently
# lost a case would otherwise take its coverage with it.
# ---------------------------------------------------------------------------

def test_industry_tag_to_bucket_maps_representative_scenario_a_tags():
    assert INDUSTRY_TAG_TO_BUCKET["biometric data"] == "biometric/emotion inference"
    assert INDUSTRY_TAG_TO_BUCKET["gdpr"] == "data processing & retention"
    assert INDUSTRY_TAG_TO_BUCKET["recommender system"] == "algorithmic content ranking"


def test_industry_tag_to_bucket_maps_representative_scenario_b_tags():
    assert INDUSTRY_TAG_TO_BUCKET["robo-advice"] == "robo-advice disclosures"
    assert INDUSTRY_TAG_TO_BUCKET["consumer credit"] == "credit advertising"
    assert INDUSTRY_TAG_TO_BUCKET["crypto"] == "crypto/digital-asset promotion"


def test_industry_tag_to_bucket_covers_every_closed_keyword():
    """Every keyword in every closed §7 set has a bucket -- the mapping is
    complete over the vocabulary eligibility already recognizes, never a
    'TBD, enumerate later' partial table."""
    all_keywords = (
        SCENARIO_A_KEYWORDS | SCENARIO_B_FINANCIAL_TERMS
        | SCENARIO_B_PROMOTIONAL_TERMS | SCENARIO_B_COMBINED_TERMS
    )
    assert all_keywords <= set(INDUSTRY_TAG_TO_BUCKET)


def test_buckets_golden_parity():
    """The cross-language lock (spec §8). `prompts.test.ts` runs these SAME cases
    against the TypeScript `INDUSTRY_TAG_TO_BUCKET`.

    Why this fixture exists at all: the mapping decides which bucket phrase a
    record's prompt uses. If prep and template disagree, the eval asks a
    DIFFERENT question than the one the record's evidence was recorded against
    -- and the >= 0.8 bar absorbs the difference as noise rather than failing.
    """
    golden = json.loads(
        (Path(__file__).parent / "fixtures" / "buckets_golden.json").read_text(encoding="utf-8")
    )
    for case in golden["tag_bucket_cases"]:
        actual = INDUSTRY_TAG_TO_BUCKET.get(case["tag"])
        assert actual == case["expected_bucket"], (
            f"INDUSTRY_TAG_TO_BUCKET[{case['tag']!r}] == {actual!r}, "
            f"golden expects {case['expected_bucket']!r}"
        )


def test_buckets_golden_covers_every_bucket_phrase():
    """A fixture that covered only two of the ten buckets would pass the parity
    test above while locking almost nothing. (This assertion is not decorative:
    it caught a missing `retail financial promotions` case when the fixture was
    first authored.)"""
    golden = json.loads(
        (Path(__file__).parent / "fixtures" / "buckets_golden.json").read_text(encoding="utf-8")
    )
    covered = {c["expected_bucket"] for c in golden["tag_bucket_cases"]}
    assert covered == set(DOMAIN_BUCKETS["A"]) | set(DOMAIN_BUCKETS["B"])


def test_buckets_golden_unmapped_tag_defaults():
    """§8's "incl. an unmapped tag -> the default bucket".

    The default is SCENARIO-SCOPED (`DOMAIN_BUCKETS[scenario][0]`), which is why
    these cases carry a `scenario` field and the `tag_bucket_cases` above do not
    -- `INDUSTRY_TAG_TO_BUCKET` is one flat, scenario-free table. Driven through
    `build_task_instance` (the real renderer), not by reading the default
    constant back, so this asserts the fallback actually fires."""
    golden = json.loads(
        (Path(__file__).parent / "fixtures" / "buckets_golden.json").read_text(encoding="utf-8")
    )
    specs = {"A": SCENARIO_A, "B": SCENARIO_B}
    for case in golden["unmapped_tag_default_cases"]:
        assert case["tag"] not in INDUSTRY_TAG_TO_BUCKET, (
            f"{case['tag']!r} is supposed to be UNMAPPED, but the table maps it — "
            f"this case no longer tests the fallback"
        )
        record = {
            "impacted_business": {"industry": [case["tag"]], "size": [], "type": []},
            "impacted_functions": [],
            "jurisdiction_country": "DE",
            "jurisdiction_bloc": "EU",
            "jurisdiction_scope": "national",
            "update_type": "guidance",
            "title": "Unmapped-tag fixture record",
        }
        instance = build_task_instance(record, specs[case["scenario"]])
        assert instance["DOMAIN_PHRASE"] == case["expected_bucket"]


def test_domain_buckets_are_the_closed_spec_vocabulary():
    assert DOMAIN_BUCKETS["A"] == (
        "AI-assisted decisioning", "automated profiling", "biometric/emotion inference",
        "data processing & retention", "algorithmic content ranking",
    )
    assert DOMAIN_BUCKETS["B"] == (
        "investment product marketing", "retail financial promotions",
        "crypto/digital-asset promotion", "robo-advice disclosures", "credit advertising",
    )


# ---------------------------------------------------------------------------
# Negative controls -- closed contract (spec §12/§7): 10 topics x 3 artifacts
# = exactly 30, deterministic, order-stable, benign (no scenario keyword).
# ---------------------------------------------------------------------------

def test_negative_control_tasks_are_closed_and_ten_per_scenario():
    assert len(NEGATIVE_CONTROL_TASKS["A"]) == 10
    assert len(NEGATIVE_CONTROL_TASKS["B"]) == 10


def test_negative_control_artifacts_are_the_closed_three():
    assert NEGATIVE_CONTROL_ARTIFACTS == (
        "the two-paragraph internal announcement",
        "the short all-staff email",
        "the three-bullet FAQ entry",
    )


def test_negative_control_tasks_are_benign():
    """None of the closed negative-control topics contains any scenario
    keyword -- the very predicates §7 uses to decide a record IS in the
    regulated domain."""
    all_keywords = (
        SCENARIO_A_KEYWORDS | SCENARIO_B_FINANCIAL_TERMS
        | SCENARIO_B_PROMOTIONAL_TERMS | SCENARIO_B_COMBINED_TERMS
    )
    for scenario_id in ("A", "B"):
        for task in NEGATIVE_CONTROL_TASKS[scenario_id]:
            for keyword in all_keywords:
                assert not _tag_matches_keyword(task, keyword), (
                    f"negative control task {task!r} (scenario {scenario_id}) "
                    f"unexpectedly contains keyword {keyword!r}"
                )


def test_build_negative_control_prompts_returns_exactly_thirty():
    prompts = build_negative_control_prompts(SCENARIO_A)

    assert len(prompts) == 30
    assert len(set(prompts)) == 30  # all distinct


def test_build_negative_control_prompts_is_deterministic_and_order_stable():
    first = build_negative_control_prompts(SCENARIO_A)
    second = build_negative_control_prompts(SCENARIO_A)

    assert first == second


def test_build_negative_control_prompts_is_topic_major_cross_product():
    prompts = build_negative_control_prompts(SCENARIO_A)
    tasks = NEGATIVE_CONTROL_TASKS["A"]

    # First 3 prompts are all the same topic (topic-major ordering), each with
    # a distinct artifact framing.
    for artifact in NEGATIVE_CONTROL_ARTIFACTS:
        assert any(tasks[0] in p and artifact in p for p in prompts[:3])


def test_build_negative_control_prompts_differ_by_scenario():
    a_prompts = build_negative_control_prompts(SCENARIO_A)
    b_prompts = build_negative_control_prompts(SCENARIO_B)

    assert a_prompts != b_prompts
    assert len(b_prompts) == 30
