/**
 * The TypeScript side of `scoring_golden.json` — the shared, byte-identical
 * cross-language drift fixture (§12). Each side runs EVERY group through its own
 * independent implementation, so a behaviour drift shows up as a red test on
 * whichever side drifted, without either side reading the other's code.
 *
 * FILE STRUCTURE — pinned here, once, for the two tasks that follow (P6.3 →
 * P6.4 → P6.12b, matching the phase's task order): **one `describe` per golden
 * group, named exactly after the group**, so each owning task can verify its own
 * group with `vitest -t '<group>'`. The spec pins no literal test name in this
 * file, so this convention is free to adopt.
 *
 *   stage_a_predicate_cases  — P6.3, owner: src/schema.ts
 *   judge_cases              — P6.4 (landed), owner: src/judge/contract.ts
 *   citation_date_cases      — P6.12b (landed), owner: src/evals/scorers.ts
 *   obligation_cases         — P6.12b (landed), owner: src/evals/scorers.ts
 */
import { describe, expect, test } from "vitest";
import { ClearedRecordSchema, StageBResponseSchema, predictsStageAViolation } from "../src/schema";
import { GuardrailVerdictSchema, parseAndValidateVerdicts } from "../src/judge/contract";
import {
  scoreCitation,
  scoreComplianceDate,
  scoreMissedObligation,
  type CitationGroundTruth,
  type UrlCache,
} from "../src/evals/scorers";
import type { ClearedRecord } from "../src/schema";
import type { JudgeResult } from "../src/judge/contract";
import { loadScoringGolden } from "./fixtures";

const golden = loadScoringGolden();

describe("stage_a_predicate_cases", () => {
  const cases = golden.stage_a_predicate_cases.filter(c => !c.prep_only);

  test("the fixture group is present and non-empty", () => {
    // `name` IS asserted against, not decoration: a fixture that quietly dropped
    // the boundary case would otherwise still pass every case it kept.
    expect(cases.length).toBeGreaterThan(0);
    const names = cases.map(c => c.name);
    expect(names).toContain("citation_only");
    expect(names).toContain("missed_obligation_all_three_confirmed");
    expect(names).toContain("missed_obligation_one_confirmation_false");
  });

  test.each(golden.stage_a_predicate_cases.filter(c => !c.prep_only).map(c => [c.name, c] as const))(
    "%s",
    (_name, goldenCase) => {
      // Parsed, not cast: every golden record is a real ClearedRecord, and a
      // fixture that drifted from §5's shape must fail here rather than feed the
      // predicate an object the runtime would never see.
      const record = ClearedRecordSchema.parse(goldenCase.record);
      expect(predictsStageAViolation(record)).toBe(goldenCase.expected);
    },
  );
});

describe("judge_cases", () => {
  // D19: `confidence_nan_discarded` is `prep_only` and MUST stay filtered out.
  // Python's `json.loads` accepts the bare `NaN` literal and reaches §4 step 3
  // (discard -> the out-of-range rationale); JS's `JSON.parse` rejects it, so
  // step 1 fires and the id takes the omission fallback -> a different
  // rationale. Both sides discard the value; only the diagnostic differs, so the
  // parity guarantee is made narrower and true rather than broad and false.
  const cases = golden.judge_cases.filter(c => !c.prep_only);

  test("the fixture group is present, and the prep_only allowlist is exactly D19's one case", () => {
    expect(cases.length).toBeGreaterThan(0);
    // The allowlist is a bounded, named hole in the parity guarantee — never a
    // place to park inconvenient cases. Pinned by name, so a case that quietly
    // escaped into it fails here rather than vanishing from this side's run.
    expect(golden.judge_cases.filter(c => c.prep_only).map(c => c.name)).toEqual([
      "confidence_nan_discarded",
    ]);
    // THE case (§4 step 3): asserted present, because a fixture that dropped it
    // would leave a clamping implementation green.
    expect(cases.map(c => c.name)).toContain("confidence_above_range_discarded_not_clamped");
  });

  test.each(cases.map(c => [c.name, c] as const))("%s", (_name, goldenCase) => {
    const result = parseAndValidateVerdicts(goldenCase.raw_response, goldenCase.requested_ids);
    expect(result.verdicts).toEqual(goldenCase.expected_verdicts);
  });

  test("every returned confidence is in [0, 1] whatever the provider returned (step 6's invariant)", () => {
    // The point of discarding rather than clamping is that NOTHING out of range
    // survives — so the schema that declares the bound must accept the OUTPUT of
    // every case, including the ones whose input carried 5.0, -0.2 or "high".
    for (const goldenCase of cases) {
      const result = parseAndValidateVerdicts(goldenCase.raw_response, goldenCase.requested_ids);
      expect(() => GuardrailVerdictSchema.parse(result)).not.toThrow();
    }
  });
});

describe("citation_date_cases", () => {
  const cases = golden.citation_date_cases.filter(c => !c.prep_only);

  test("the fixture group is present, and the two failure cases §4 names are in it", () => {
    expect(cases.length).toBeGreaterThan(0);
    const names = cases.map(c => c.name);
    // The ONLY two deterministic failures in §4's whole citation/date taxonomy. A
    // fixture that dropped either would leave an implementation that never fails —
    // i.e. one that could never admit a record — perfectly green.
    expect(names).toContain("citation_fabricated_the_only_deterministic_citation_failure");
    expect(names).toContain("citation_correct_and_date_wrong");
  });

  test.each(cases.map(c => [c.name, c] as const))("%s", (_name, goldenCase) => {
    const record = goldenCase.record as CitationGroundTruth;
    // Parsed, not cast: the fixture's `stage_b_result` also carries prep's own
    // bookkeeping (`record_id`/`usage`/`called_at`), which is NOT part of the model's
    // answer. Parsing keeps the port reading exactly the fields §3's response schema
    // defines, and fails if the fixture ever drops one of them.
    const stageB = StageBResponseSchema.parse(goldenCase.stage_b_result);
    const urlCache = goldenCase.url_cache as UrlCache;

    // Call ORDER is a §4 contract, not a style choice — scoreComplianceDate takes the
    // resulting CitationScore, because a date claim can only be judged wrong once the
    // baseline has proved WHICH document it is talking about.
    const citation = scoreCitation(stageB, record, urlCache);
    const date = scoreComplianceDate(stageB, record, citation);

    expect(citation.outcome).toBe(goldenCase.expected_citation_outcome);
    expect(citation.is_failure).toBe(goldenCase.expected_citation_is_failure);
    expect(date.outcome).toBe(goldenCase.expected_date_outcome);
    expect(date.is_failure).toBe(goldenCase.expected_date_is_failure);
  });

  test("is_failure is true for citation_fabricated and date_wrong, and NOTHING else", () => {
    // The taxonomy's whole point: honest abstention, a plausible alternative source and
    // an unverifiable server are evidence of NOTHING. If any of them ever scored as a
    // failure, prep would admit records on evidence that the baseline got it right —
    // the one direction every degenerate path here is designed to avoid.
    for (const goldenCase of cases) {
      const record = goldenCase.record as CitationGroundTruth;
      const stageB = StageBResponseSchema.parse(goldenCase.stage_b_result);
      const citation = scoreCitation(stageB, record, goldenCase.url_cache as UrlCache);
      const date = scoreComplianceDate(stageB, record, citation);
      expect(citation.is_failure).toBe(citation.outcome === "citation_fabricated");
      expect(date.is_failure).toBe(date.outcome === "date_wrong");
    }
  });
});

describe("obligation_cases", () => {
  // The `not_applicable` case is prep_only and MUST stay filtered out: it gates on
  // `is_eligible(record, scenario)`, and the template owns no ScenarioSpec and no
  // isEligible — every vendored record was admitted under its scenario, so the branch
  // is dead by construction on this side (§4's seam note).
  const cases = golden.obligation_cases.filter(c => !c.prep_only);

  test("the prep_only allowlist is exactly the one case §4's seam note names", () => {
    expect(cases.length).toBeGreaterThan(0);
    expect(golden.obligation_cases.filter(c => c.prep_only).map(c => c.name)).toEqual([
      "not_applicable_when_record_is_ineligible_for_the_scenario",
    ]);
    // The boundary IS the near-miss guard. Pinned by name, because a fixture that
    // dropped it would leave a `> 0.7` implementation green against a `>= 0.7` spec.
    expect(cases.map(c => c.name)).toContain("violation_at_the_confidence_floor_is_a_failure");
  });

  test.each(cases.map(c => [c.name, c] as const))("%s", (_name, goldenCase) => {
    // The fixture's records are PREP-shaped, and `scoreMissedObligation`'s `record`
    // parameter is unused by the 3-arg port (see scorers.ts, header issue 3) — the cast
    // is honest rather than convenient: there is no ClearedRecord here to parse, and
    // nothing reads it.
    const record = goldenCase.record as unknown as ClearedRecord;
    const judgeResult = goldenCase.judge_result as JudgeResult;
    const score = scoreMissedObligation(record, judgeResult, goldenCase.obligation_id);
    expect(score.outcome).toBe(goldenCase.expected_outcome);
    expect(score.is_failure).toBe(goldenCase.expected_is_failure);
  });
});
