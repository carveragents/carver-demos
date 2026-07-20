"""The generator's tests (spec §7, plan P3.2).

Focused, one per real behavior. The three that matter most, and why:

  * `test_trigger_never_citation_only` — evidence TYPE gates candidacy before
    strength ranks it. A record admitted purely for citation/date evidence
    proves a Stage B knowledge failure and cannot license "the guardrail blocks
    this draft"; picking it produces a demo that reliably does nothing, for a
    reason no amount of debugging the guardrail would reveal.
  * `test_trigger_skips_crowded_out_candidate` — §9a proves every record is
    RELEVANT to its own profile, never that it wins one of the five slots. Step
    4's narrowing filter is therefore real, not a formality.
  * `test_emit_is_idempotent` — the Phase-8 re-run over the real dataset happens
    against files Phase 6 has since filled in with hand-authored code. Without
    idempotent replacement that re-run either deletes hand-authored code or
    emits a duplicate `export const` (orchestrator D2).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastra_prep import generate_template_config as gtc
from mastra_prep.generate_template_config import (
    emit_template_config,
    firm_profile_for_record,
    narrow_obligations_pure,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture builders — §5's shape, only the fields this module reads vary.
# ---------------------------------------------------------------------------

def _failure(mode: str) -> dict:
    return {
        "mode": mode,
        "stage": "A" if mode == "missed_obligation" else "B",
        "baseline_response_excerpt": f"excerpt for {mode}",
        "judge_rationale": "the draft omits it" if mode == "missed_obligation" else None,
    }


def _cleared(
    record_id: str,
    *,
    scenario: str = "A",
    modes: tuple[str, ...] = ("missed_obligation",),
    country: str | None = "DE",
    bloc: str | None = "EU",
    industry: tuple[str, ...] = ("Artificial Intelligence",),
    functions: tuple[str, ...] = ("Compliance",),
    compliance_date: str | None = None,
    confirmed: bool = True,
    update_type: str = "guidance",
) -> dict:
    """A §5-shaped ClearedRecord. `confirmed` drives the three sub-attestations,
    which `predicts_stage_a_violation` requires alongside missed_obligation."""
    has_obligation = "missed_obligation" in modes
    confirmation = (confirmed if has_obligation else None)
    return {
        "id": record_id,
        "title": f"Obligation {record_id}",
        "regulator_name": "BaFin",
        "jurisdiction": {"scope": "national", "country": country, "bloc": bloc,
                         "region_name": None},
        "update_type": update_type,
        "impact_label": "high",
        "objective": f"Objective for {record_id}.",
        "what_changed": f"What changed for {record_id}.",
        "why_it_matters": f"Why {record_id} matters.",
        "key_requirements": [f"Requirement for {record_id}."],
        "compliance_date": compliance_date,
        "citation": {"name": f"Citation {record_id}", "url": f"https://example.eu/{record_id}"},
        "impacted_business": {"size": ["medium"], "type": ["technology provider"],
                              "industry": list(industry)},
        "impacted_functions": list(functions),
        "scenario": scenario,
        "baseline_failures": [_failure(m) for m in modes],
        "human_review": {
            "reviewer": "achint",
            "reviewed_at": "2026-07-16T10:00:00Z",
            "attestation": "approved",
            "obligation_applies_confirmed": confirmation,
            "artifact_capable_of_violation_confirmed": confirmation,
            "omission_materiality_confirmed": confirmation,
        },
        "source": {"artifact_id": record_id, "topic_id": "topic-1", "source_id": "src-1",
                   "snapshot_date": "2026-07-11"},
        "probed_at": "2026-07-15T09:30:00Z",
        "model_id": "openai/gpt-5.6-sol",
        "model_cutoff": "2026-02-16",
    }


def _decision(winner: str | None = "A") -> dict:
    """Only `winner` is read by emit_template_config; the rest is §7's shape."""
    return {
        "outcome": "decided" if winner else "insufficient_trial",
        "winner": winner,
        "stop_reason": "complete",
        "discarded_rounds": 0,
        "strength_scores": {"A": 1.5, "B": 0.5},
        "survivor_counts": {"A": 3, "B": 1},
        "stage_a_survivor_counts": {"A": 2, "B": 0},
        "probed_ids": {"A": [], "B": []},
        "trial_planned": {"A": 30, "B": 30},
        "trial_completed": {"A": 30, "B": 30},
        "decided_at": "2026-07-16T12:00:00Z",
        "evidence_path": "data/scratch/scenario_decision.json",
    }


# ---------------------------------------------------------------------------
# firm_profile_for_record — camelCase, because it is serialized straight into a
# TS object literal with no key-transform step (§7/§8, orchestrator D18).
# ---------------------------------------------------------------------------

def test_firm_profile_keys_are_camel_case_and_match_the_record():
    record = _cleared("rec-1", industry=("Artificial Intelligence", "Fintech"),
                      functions=("Compliance", "Engineering"))

    profile = firm_profile_for_record(record)

    assert profile == {
        "jurisdiction": {"country": "DE", "bloc": "EU"},
        "sector": "Artificial Intelligence",
        "industry": ["Artificial Intelligence", "Fintech"],
        "size": "medium",
        "impactedFunctions": ["Compliance", "Engineering"],
    }
    # The key FirmProfileSchema pins and §9a's snippet gets wrong (D18): reading
    # `impacted_functions` TS-side is not an error, it is `undefined` — narrowing
    # would silently drop one of its two required predicates.
    assert "impacted_functions" not in profile


def test_firm_profile_falls_back_when_country_and_sector_are_absent():
    """`?? ""` on country, `[0] ?? ""` on sector — the record still narrow-matches
    itself via its bloc and its functions (§9a's proof)."""
    record = _cleared("rec-1", country=None, industry=())

    profile = firm_profile_for_record(record)

    assert profile["jurisdiction"] == {"country": "", "bloc": "EU"}
    assert profile["sector"] == ""
    assert narrow_obligations_pure(profile, [record]) == ["rec-1"]


# ---------------------------------------------------------------------------
# narrow_obligations_pure — the Python port of §9a.
# ---------------------------------------------------------------------------

def test_narrowing_golden_parity():
    """The shared fixture is the ONLY thing holding this port and §9a's
    TypeScript original together — they are never imported across the seam."""
    golden = json.loads((FIXTURES / "narrowing_golden.json").read_text(encoding="utf-8"))

    for case in golden["cases"]:
        result = narrow_obligations_pure(case["firmProfile"], case["clearedSet"])
        assert result == case["expectedTopFiveIds"], f"case {case['name']!r}"


# ---------------------------------------------------------------------------
# emit_template_config — steps 2/3/4/7.
# ---------------------------------------------------------------------------

def test_trigger_tie_broken_by_id_ascending(tmp_path: Path):
    """`sorted()` ascending, not `max()` — which would pick the lexicographically
    LARGEST id on a tie, the opposite of what the rule says (§7 step 3)."""
    records = [_cleared("rec-zulu"), _cleared("rec-alpha")]

    bundle = emit_template_config(records, _decision("A"), template_src_dir=tmp_path)

    assert bundle["trigger_record_id"] == "rec-alpha"


def test_trigger_never_citation_only(tmp_path: Path):
    """Evidence TYPE gates candidacy BEFORE strength ranks it (§7 step 2).

    `rec-loud` carries the higher failure count and would win step 3's ranking
    outright; it is excluded at step 2 because citation/date evidence proves a
    Stage B knowledge failure and licenses no expectation about a DRAFT.

    (Two Stage-B modes on one record is deliberately over-strong: §4's
    exclusivity makes it unreachable in production. The point is that NO failure
    count, however high, promotes citation/date evidence past the gate.)
    """
    records = [
        _cleared("rec-loud", modes=("citation_fabricated", "date_wrong")),
        _cleared("rec-quiet", modes=("missed_obligation",)),
    ]

    bundle = emit_template_config(records, _decision("A"), template_src_dir=tmp_path)

    assert bundle["trigger_record_id"] == "rec-quiet"
    assert bundle["trigger_candidate_count"] == 1


def test_raises_when_no_stage_a_evidence(tmp_path: Path):
    """Step 2's loud failure — and it must not half-write a demo on the way out."""
    records = [_cleared("rec-1", modes=("citation_fabricated",)),
               _cleared("rec-2", modes=("date_wrong",))]

    with pytest.raises(ValueError) as excinfo:
        emit_template_config(records, _decision("A"), template_src_dir=tmp_path)

    message = str(excinfo.value)
    assert "missed_obligation" in message
    assert "2 cleared records" in message and "scenario A" in message
    assert list(tmp_path.rglob("*")) == []


def test_raises_when_winner_has_no_cleared_records(tmp_path: Path):
    """Step 1 — nothing to build a demo around, and it fails at generation time
    rather than silently shipping an empty demo."""
    records = [_cleared("rec-1", scenario="A")]

    with pytest.raises(ValueError, match="scenario B"):
        emit_template_config(records, _decision("B"), template_src_dir=tmp_path)

    assert list(tmp_path.rglob("*")) == []


def test_trigger_skips_crowded_out_candidate(tmp_path: Path):
    """§9a proves RELEVANCE, not a top-5 slot (§7 step 4).

    `rec-crowded` is the strongest candidate by failure count, but five
    same-tag records with nearer compliance dates outrank it on urgencyWeight
    under its own generated profile, so it never reaches the guardrail. The
    generator falls through to the next candidate that demonstrably survives.
    """
    crowders = [
        _cleared(f"rec-crowd-{i}", modes=("citation_fabricated",),
                 compliance_date="2026-08-01")
        for i in range(5)
    ]
    crowded_out = _cleared("rec-crowded", modes=("missed_obligation", "date_wrong"),
                           compliance_date=None)
    # A different industry AND a different function, so none of the crowders is
    # even relevant to this record's own profile.
    survivor = _cleared("rec-survivor", modes=("missed_obligation",),
                        industry=("Payments",), functions=("Treasury",))
    records = [*crowders, crowded_out, survivor]

    assert "rec-crowded" not in narrow_obligations_pure(
        firm_profile_for_record(crowded_out), records)

    bundle = emit_template_config(records, _decision("A"), template_src_dir=tmp_path)

    assert bundle["trigger_record_id"] == "rec-survivor"
    assert bundle["trigger_candidate_count"] == 2


def test_raises_when_no_candidate_survives_narrowing(tmp_path: Path):
    """Step 4's own loud failure — never a silently non-firing demo."""
    crowders = [
        _cleared(f"rec-crowd-{i}", modes=("citation_fabricated",),
                 compliance_date="2026-08-01")
        for i in range(5)
    ]
    records = [*crowders, _cleared("rec-crowded", compliance_date=None)]

    with pytest.raises(ValueError, match="narrowing"):
        emit_template_config(records, _decision("A"), template_src_dir=tmp_path)

    assert list(tmp_path.rglob("*")) == []


def test_step_seven_assertion_fires_on_a_non_matching_profile(tmp_path: Path, monkeypatch):
    """Step 7 re-runs step 4's check against the profile actually being emitted.

    Redundant by construction (steps 4 and 5 share their inputs) and kept
    deliberately — so the test has to break that construction to reach it: the
    profile handed to step 5 is swapped for one the trigger cannot match. The
    assertion is the one thing standing between "the demo works" and "the demo
    silently doesn't fire", and a dead assertion looks exactly like a live one.
    """
    real = gtc.firm_profile_for_record
    calls: list[int] = []

    def _profile_that_rots_after_selection(record):
        calls.append(1)
        if len(calls) == 1:          # step 4's candidacy check — the real profile
            return real(record)
        return {**real(record), "jurisdiction": {"country": "JP", "bloc": None}}

    monkeypatch.setattr(gtc, "firm_profile_for_record", _profile_that_rots_after_selection)

    with pytest.raises(AssertionError, match="narrow"):
        emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)

    assert list(tmp_path.rglob("*")) == []


# ---------------------------------------------------------------------------
# Step 8 — the write.
# ---------------------------------------------------------------------------

def test_emit_writes_all_four_targets(tmp_path: Path):
    bundle = emit_template_config([_cleared("rec-1")], _decision("A"),
                                  template_src_dir=tmp_path)

    assert bundle["written_files"] == [
        "config.ts", "firmProfile.ts", "agents/baselineAgent.ts", "scenario/prompts.ts",
    ]
    assert bundle["winner"] == "A"
    assert bundle["firm_profile"] == firm_profile_for_record(_cleared("rec-1"))

    config_ts = (tmp_path / "config.ts").read_text(encoding="utf-8")
    assert 'export const DEMO_TRIGGER_RECORD_ID: string = "rec-1";' in config_ts

    firm_ts = (tmp_path / "firmProfile.ts").read_text(encoding="utf-8")
    assert "export const DEMO_FIRM_PROFILE: FirmProfile = {" in firm_ts
    assert '"impactedFunctions"' in firm_ts

    persona_ts = (tmp_path / "agents" / "baselineAgent.ts").read_text(encoding="utf-8")
    # Scenario A won, so the persona is Aldergrove Labs' — never hand-authored
    # against an assumed winner (rubric #5).
    assert "export const SCENARIO_PERSONA_INSTRUCTIONS: string = " in persona_ts
    assert "Aldergrove Labs" in persona_ts
    assert "Solmark Capital" not in persona_ts

    prompts_ts = (tmp_path / "scenario" / "prompts.ts").read_text(encoding="utf-8")
    for symbol in ("buildStageAPrompt", "buildStageBPrompt", "INDUSTRY_TAG_TO_BUCKET",
                   "DOMAIN_BUCKETS", "SCENARIO_TASK_TEMPLATES", "NEGATIVE_CONTROL_PROMPTS"):
        assert f"export const {symbol}" in prompts_ts or f"export function {symbol}" in prompts_ts
    # §8's closed contract: 10 benign topics x 3 artifact framings.
    assert len(json.loads(_ts_array_literal(prompts_ts, "NEGATIVE_CONTROL_PROMPTS"))) == 30


def _ts_literal(source: str, symbol: str, terminator: str) -> str:
    """The JSON literal assigned to `symbol` — valid TS object/array syntax is a
    strict subset of JSON, which is why generation needs no format conversion.

    Anchored on the `= ` (not on the first bracket after the symbol), because the
    declaration's TYPE carries brackets of its own: `readonly string[] = [...]`.
    """
    start = source.index(f"export const {symbol}")
    assignment = source.index(" = ", start) + 3
    end = source.index(terminator, assignment)
    return source[assignment:end + 2]   # through the closing bracket, before the `;`


def _ts_array_literal(source: str, symbol: str) -> str:
    return _ts_literal(source, symbol, "\n];")


def _ts_object_literal(source: str, symbol: str) -> str:
    return _ts_literal(source, symbol, "\n};")


def test_emit_is_idempotent(tmp_path: Path):
    """Orchestrator D2: the write is idempotent REPLACEMENT.

    The Phase-8 re-run happens against files Phase 6 filled in with
    hand-authored code. Blind appending emits a duplicate `export const` (a TS
    compile error at best, the stale value winning at worst); blind overwriting
    deletes the hand-authored half of the file.
    """
    (tmp_path / "config.ts").write_text(
        'export const MODEL_ID = "openai/gpt-5.6-sol";\n'
        'export const SNAPSHOT_DATE = "2026-07-11";\n'
        'export const DEMO_TRIGGER_RECORD_ID: string = "rec-stale";\n'
        'export const JUDGE_CONFIDENCE_FLOOR = 0.7;\n',
        encoding="utf-8",
    )
    records = [_cleared("rec-1")]

    emit_template_config(records, _decision("A"), template_src_dir=tmp_path)
    first = {p: p.read_bytes() for p in sorted(tmp_path.rglob("*.ts"))}
    emit_template_config(records, _decision("A"), template_src_dir=tmp_path)
    second = {p: p.read_bytes() for p in sorted(tmp_path.rglob("*.ts"))}

    assert first == second, "a second emit must be byte-identical to the first"

    config_ts = (tmp_path / "config.ts").read_text(encoding="utf-8")
    assert config_ts.count("export const DEMO_TRIGGER_RECORD_ID") == 1
    assert 'DEMO_TRIGGER_RECORD_ID: string = "rec-1";' in config_ts
    assert "rec-stale" not in config_ts
    # The hand-authored exports survive, in place.
    assert 'export const MODEL_ID = "openai/gpt-5.6-sol";' in config_ts
    assert 'export const SNAPSHOT_DATE = "2026-07-11";' in config_ts
    assert "export const JUDGE_CONFIDENCE_FLOOR = 0.7;" in config_ts

    firm_ts = (tmp_path / "firmProfile.ts").read_text(encoding="utf-8")
    assert firm_ts.count("export const DEMO_FIRM_PROFILE") == 1


def test_emit_replaces_a_multi_line_generated_declaration(tmp_path: Path):
    """DEMO_FIRM_PROFILE spans many lines — replacing only its FIRST line would
    leave the previous object's tail behind as syntactic rubble."""
    (tmp_path / "firmProfile.ts").write_text(
        "export const FirmProfileSchema = z.object({});\n"
        "export const DEMO_FIRM_PROFILE: FirmProfile = {\n"
        '  "jurisdiction": {\n'
        '    "country": "JP",\n'
        '    "bloc": null\n'
        "  },\n"
        '  "sector": "Stale",\n'
        '  "industry": [],\n'
        '  "size": "medium",\n'
        '  "impactedFunctions": []\n'
        "};\n"
        "export function firmProfileForRecord(record) { return DEMO_FIRM_PROFILE; }\n",
        encoding="utf-8",
    )

    emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)

    firm_ts = (tmp_path / "firmProfile.ts").read_text(encoding="utf-8")
    assert firm_ts.count("export const DEMO_FIRM_PROFILE") == 1
    assert '"JP"' not in firm_ts and '"Stale"' not in firm_ts
    assert "export const FirmProfileSchema = z.object({});" in firm_ts
    assert "export function firmProfileForRecord(record)" in firm_ts


def test_emit_inserts_into_a_file_that_lacks_the_symbol(tmp_path: Path):
    """D2's other half. The realistic Phase-6 state for `agents/baselineAgent.ts`
    is a hand-authored agent file that does not yet declare the generated symbol
    — the generator must append to it, not replace it and not glue the
    declaration onto the last line."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "baselineAgent.ts").write_text(
        'import { Agent } from "@mastra/core";\n'
        "export const baselineAgent = new Agent({ model: MODEL_ID });\n",
        encoding="utf-8",
    )

    emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)
    first = (agents / "baselineAgent.ts").read_bytes()
    emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)

    persona_ts = (agents / "baselineAgent.ts").read_text(encoding="utf-8")
    assert (agents / "baselineAgent.ts").read_bytes() == first
    assert persona_ts.count("export const SCENARIO_PERSONA_INSTRUCTIONS") == 1
    assert "export const baselineAgent = new Agent({ model: MODEL_ID });" in persona_ts
    # Appended on its own line, never glued onto the hand-authored one.
    assert ";export const SCENARIO_PERSONA_INSTRUCTIONS" not in persona_ts


def test_emit_survives_an_apostrophe_in_a_hand_authored_comment(tmp_path: Path):
    """The scanner must skip comments, not read them as string literals.

    `// the firm's primary sector` opens an apostrophe "string" that never
    closes; a scanner that misses this runs to end-of-text and the replacement
    eats every line below the declaration — while reporting success. §8 puts
    `firmProfileForRecord` immediately after `DEMO_FIRM_PROFILE`, so this is the
    real file's real shape, not a contrived input.
    """
    (tmp_path / "firmProfile.ts").write_text(
        "export const DEMO_FIRM_PROFILE: FirmProfile = {\n"
        '  "jurisdiction": { "country": "JP", "bloc": null },  // the firm\'s home\n'
        '  "sector": "Stale",  /* the firm\'s primary sector */\n'
        '  "industry": [], "size": "medium", "impactedFunctions": []\n'
        "};\n"
        "export function firmProfileForRecord(record) { return DEMO_FIRM_PROFILE; }\n",
        encoding="utf-8",
    )

    emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)

    firm_ts = (tmp_path / "firmProfile.ts").read_text(encoding="utf-8")
    assert "export function firmProfileForRecord(record)" in firm_ts, "hand-authored code eaten"
    assert firm_ts.count("export const DEMO_FIRM_PROFILE") == 1
    assert '"JP"' not in firm_ts


def test_emit_refuses_to_write_over_an_unterminated_declaration(tmp_path: Path):
    """A truncated file and a scanner that lost its place are indistinguishable
    here, and they demand opposite responses. Refusing to guess is the only
    answer that cannot destroy a reviewer's work."""
    (tmp_path / "config.ts").write_text(
        'export const MODEL_ID = "openai/gpt-5.6-sol";\n'
        "export const DEMO_TRIGGER_RECORD_ID: string = \n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="truncated"):
        emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)


def test_rotten_compliance_date_does_not_kill_the_generator(tmp_path: Path):
    """The corpus's date extraction has real rot and `validate_cleared_record`
    type-checks `compliance_date` without parsing it, so a rotten value ships.
    Narrowing sorts the ENTIRE cleared set, so one such record anywhere would
    otherwise kill generation from inside a sort key. Weight 1 — the reading
    that matches the TS, where `NaN <= 180` is `false`."""
    rotten = _cleared("rec-rot", modes=("citation_fabricated",), compliance_date="Q3 2026")
    near = _cleared("rec-near", compliance_date="2026-08-01")

    profile = firm_profile_for_record(near)
    assert narrow_obligations_pure(profile, [rotten, near]) == ["rec-near", "rec-rot"]

    bundle = emit_template_config([rotten, near], _decision("A"), template_src_dir=tmp_path)
    assert bundle["trigger_record_id"] == "rec-near"


def test_raises_on_an_insufficient_trial_decision(tmp_path: Path):
    """`winner is None` IFF the trial was insufficient (§7). Reachable: this is
    its own CLI branch, run by hand against whatever decision the last run
    wrote."""
    with pytest.raises(ValueError, match="insufficient_trial"):
        emit_template_config([_cleared("rec-1")], _decision(None), template_src_dir=tmp_path)

    assert list(tmp_path.rglob("*")) == []


def test_prompts_ts_is_generated_from_the_winning_scenarios_own_constants(tmp_path: Path):
    """§8 resolves this module as GENERATED — that is what makes §12's eval ask
    the same question the evidence was recorded for.

    The bucket VOCABULARY is the winner's five phrases (goal #10 ships exactly
    one scenario); the tag MAPPING ships whole, because it is scenario-free and
    both sides run every `buckets_golden.json` tag case against it.
    """
    from mastra_prep.scenarios import DOMAIN_BUCKETS, INDUSTRY_TAG_TO_BUCKET

    emit_template_config([_cleared("rec-1")], _decision("A"), template_src_dir=tmp_path)

    prompts_ts = (tmp_path / "scenario" / "prompts.ts").read_text(encoding="utf-8")
    assert json.loads(_ts_array_literal(prompts_ts, "DOMAIN_BUCKETS")) == list(DOMAIN_BUCKETS["A"])
    assert json.loads(_ts_object_literal(prompts_ts, "INDUSTRY_TAG_TO_BUCKET")) == INDUSTRY_TAG_TO_BUCKET
    # Scenario B's persona never leaks into a Scenario-A build.
    assert "Solmark Capital" not in prompts_ts
    assert "Aldergrove Labs" in prompts_ts
    # The Stage A template's own placeholders survive generation — the generated
    # buildStageAPrompt substitutes them at runtime, per record.
    assert "{{DOMAIN_PHRASE}}" in prompts_ts and "{{JURISDICTION_PHRASE}}" in prompts_ts


# ---------------------------------------------------------------------------
# The package surface (spec §1:396-412).
# ---------------------------------------------------------------------------

REEXPORTED_NAMES = (
    "Settings", "load_settings",
    "stream_annotations",
    "FIELD_MAP", "extract_record",
    "is_candidate", "filter_candidates",
    "extract_urls", "resolve_url",
    "stratified_sample_sequence",
    "SpendBudget", "BudgetExhausted", "BudgetPoisoned",
    "run_curation",
    "SCENARIO_A", "SCENARIO_B", "is_eligible",
    "decide_scenario",
    "ClearedRecord", "to_json", "validate_cleared_record", "predicts_stage_a_violation",
    "load_env", "make_client",
    "emit_template_config", "firm_profile_for_record",
)

# Deliberately absent (spec:414). Not an oversight: re-exporting them at package
# level is what re-creates the probe -> judge -> curate -> probe cycle that
# extracting the leaf `budget.py` fixed. They take an injected client and are
# imported directly by callers that need to control cost.
#
# The check is on the SYMBOLS, not on `mastra_prep.probe` — the submodule
# attribute is bound by the interpreter itself the moment `curate.py` imports
# `.probe`, so asserting its absence would assert something no `__init__.py`
# can control (and would fail for a package whose surface is perfectly correct).
# What IS controllable, and what the rule actually protects, is whether these
# modules' public functions are part of the package's namespace.
NOT_REEXPORTED_SYMBOLS = (
    "run_stage_a", "run_stage_b", "StageAResult", "StageBResult",          # probe.py
    "run_judge", "parse_and_validate_verdicts", "JUDGE_RESPONSE_SCHEMA",   # judge.py
    "score_citation", "score_compliance_date", "score_missed_obligation",  # scoring.py
    "passes_failure_bar",
)

INIT_PATH = Path(__file__).resolve().parents[1] / "mastra_prep" / "__init__.py"


def test_package_reexports():
    import mastra_prep

    missing = [name for name in REEXPORTED_NAMES if not hasattr(mastra_prep, name)]
    assert not missing, f"pinned re-exports missing from mastra_prep: {missing}"


def test_probe_judge_scoring_are_not_reexported():
    import mastra_prep

    present = [name for name in NOT_REEXPORTED_SYMBOLS if hasattr(mastra_prep, name)]
    assert not present, (
        f"{present} must NOT be re-exported at package level (spec:414) — they take "
        f"an injected client and are imported directly by cost-controlling callers"
    )

    source = INIT_PATH.read_text(encoding="utf-8")
    for module in ("probe", "judge", "scoring"):
        assert f"from .{module} import" not in source, (
            f"__init__.py must not import from {module}.py (spec:414)"
        )
