/**
 * Test-side loaders for the vendored cleared set and the shared golden fixtures.
 *
 * Read with `fs` + `JSON.parse` rather than `import ... from "*.json"`: the point
 * of `schema.test.ts` is that the vendored file is parsed by
 * `ClearedRecordSchema` at test time, and a JSON import would have TypeScript
 * infer the shape from the file itself — making a drifted file type-check
 * against its own drift. Reading it as inert text keeps Zod the only thing that
 * decides whether it conforms.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));

function readJson(relativePath: string): unknown {
  return JSON.parse(readFileSync(resolve(HERE, relativePath), "utf-8"));
}

/** The real, shipped `src/data/cleared-set.json` — the file the processor, the
 *  workflow and the eval harness all read at runtime. */
export function loadVendoredClearedSet(): unknown {
  return readJson("../src/data/cleared-set.json");
}

/** `scoring_golden.json` — the shared, byte-identical-across-the-seam fixture
 *  (§12). Its duplicate lives in `prep/tests/fixtures/`. EDIT BOTH OR NEITHER. */
export function loadScoringGolden(): ScoringGolden {
  return readJson("./fixtures/scoring_golden.json") as ScoringGolden;
}

export type GoldenCase<Payload> = Payload & {
  name: string;
  note?: string;
  prep_only?: boolean;
};

export type StageAPredicateCase = GoldenCase<{ record: unknown; expected: boolean }>;

/** `judge_cases` — §4's six-step post-processing, run through
 *  `parseAndValidateVerdicts` here and through `parse_and_validate_verdicts` on
 *  prep's side. `expected_verdicts` is typed `unknown[]`, not `JudgeVerdict[]`:
 *  the fixture is the thing under test, so it must not borrow the
 *  implementation's own type and thereby type-check against its own drift (the
 *  same reason `record` above is `unknown`). */
export type JudgeCase = GoldenCase<{
  raw_response: string;
  requested_ids: string[];
  expected_verdicts: unknown[];
}>;

/** `citation_date_cases` — §4's citation/date algorithms. `record` and
 *  `stage_b_result` are typed `unknown` for the same reason as everywhere else here:
 *  the fixture is the thing under test and must not borrow the implementation's own
 *  type. Note these records are PREP-shaped (`reg_rules`/`reg_statutes`/
 *  `reg_other_ref`), not `ClearedRecord`s — see `evals/scorers.ts`'s header, issue 1. */
export type CitationDateCase = GoldenCase<{
  record: unknown;
  stage_b_result: unknown;
  url_cache: Record<string, string>;
  expected_citation_outcome: string;
  expected_date_outcome: string;
  expected_citation_is_failure: boolean;
  expected_date_is_failure: boolean;
}>;

/** `obligation_cases` — §4's `score_missed_obligation`. Exactly one case is
 *  `prep_only` (the `not_applicable` branch the 3-arg TS port structurally cannot
 *  reach); its count is pinned by prep's `test_prep_only_cases_are_justified`. */
export type ObligationCase = GoldenCase<{
  record: unknown;
  scenario: string;
  obligation_id: string;
  judge_result: unknown;
  expected_outcome: string;
  expected_is_failure: boolean;
}>;

export type ScoringGolden = {
  stage_a_predicate_cases: StageAPredicateCase[];
  judge_cases: JudgeCase[];
  citation_date_cases: CitationDateCase[];
  obligation_cases: ObligationCase[];
  [group: string]: unknown;
};
