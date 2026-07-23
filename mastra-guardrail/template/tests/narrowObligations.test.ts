/**
 * `narrowObligations.ts` — §9a's deterministic narrowing tool.
 *
 * Golden parity against `narrowing_golden.json` is the primary guard: it is the
 * ONLY thing keeping this port and prep's `narrow_obligations_pure` in lockstep
 * (goal #1 forbids importing across the language boundary). Each golden case
 * name states the one behavior it exercises — required-AND semantics, ranking,
 * tie-breaks, the urgency-weight boundary — so the loop below is one real test
 * per behavior, not a hand-duplicated matrix.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";
import { z } from "zod";
import { narrowObligations, narrowObligationsPure } from "../src/tools/narrowObligations";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import { DEMO_FIRM_PROFILE, firmProfileForRecord, type FirmProfile } from "../src/firmProfile";
import { DEMO_TRIGGER_RECORD_ID } from "../src/config";
import { loadVendoredClearedSet } from "./fixtures";

const HERE = dirname(fileURLToPath(import.meta.url));

type NarrowingGoldenCase = {
  name: string;
  note?: string;
  firmProfile: FirmProfile;
  clearedSet: ClearedRecord[];
  expectedTopFiveIds: string[];
};

function loadNarrowingGolden(): { cases: NarrowingGoldenCase[] } {
  return JSON.parse(readFileSync(resolve(HERE, "./fixtures/narrowing_golden.json"), "utf-8"));
}

const golden = loadNarrowingGolden();
const vendoredRecords: ClearedRecord[] = ClearedRecordSchema.array().parse(loadVendoredClearedSet());

describe("narrowObligationsPure — golden parity (narrowing_golden.json, shared with prep)", () => {
  for (const goldenCase of golden.cases) {
    test(goldenCase.name, () => {
      expect(narrowObligationsPure(goldenCase.firmProfile, goldenCase.clearedSet)).toEqual(
        goldenCase.expectedTopFiveIds
      );
    });
  }
});

describe("§9a's proved guarantee, over the real vendored set", () => {
  test("test_every_cleared_record_is_relevant_to_its_own_profile", () => {
    // Isolate each record: against a clearedSet of ONLY itself, narrowing
    // returns exactly this record iff both required predicates hold against
    // its own generated profile — §9a's proof, exercised through the real
    // implementation rather than a re-implementation of its predicates.
    for (const record of vendoredRecords) {
      const firm = firmProfileForRecord(record);
      expect(narrowObligationsPure(firm, [record])).toEqual([record.id]);
    }
  });

  test("test_demo_trigger_record_survives_narrowing", () => {
    // P6.2's generator only ships a profile whose step-7 assertion already
    // proved the trigger survives narrowing under it — re-checked here through
    // the real implementation, no skip.
    expect(narrowObligationsPure(DEMO_FIRM_PROFILE, vendoredRecords)).toContain(DEMO_TRIGGER_RECORD_ID);
  });
});

describe("test_null_country_and_bloc_record_cannot_match", () => {
  test("a record with country AND bloc both null is provably unmatched by its own profile", () => {
    // The inherited issue's counterexample, from the other side: documents why
    // §7's eligibility gate must exclude this shape. A record that reaches
    // narrowing with both null is a curation bug, not a narrowing bug.
    const record: ClearedRecord = {
      ...vendoredRecords[0],
      id: "synthetic-null-jurisdiction",
      jurisdiction: { scope: "supranational", country: null, bloc: null, region_name: null },
    };
    const firm = firmProfileForRecord(record);
    expect(narrowObligationsPure(firm, [record])).toEqual([]);
  });
});

describe("narrowObligations tool — Zod schema shape", () => {
  test("pinned id and description", () => {
    expect(narrowObligations.id).toBe("narrow-obligations");
    expect(narrowObligations.description).toBe(
      "Filter the cleared regulatory set to obligations relevant to this firm."
    );
  });

  test("inputSchema requires a valid FirmProfile; outputSchema caps candidateIds at 5", () => {
    const inputSchema = narrowObligations.inputSchema as unknown as z.ZodTypeAny;
    const outputSchema = narrowObligations.outputSchema as unknown as z.ZodTypeAny;

    expect(inputSchema.safeParse({ firmProfile: DEMO_FIRM_PROFILE }).success).toBe(true);
    expect(inputSchema.safeParse({ firmProfile: { not: "a firm profile" } }).success).toBe(false);

    expect(outputSchema.safeParse({ candidateIds: ["a", "b", "c", "d", "e"] }).success).toBe(true);
    expect(outputSchema.safeParse({ candidateIds: ["a", "b", "c", "d", "e", "f"] }).success).toBe(false);
  });

  test("execute is a thin wrapper over narrowObligationsPure against the real vendored set", async () => {
    const result = await narrowObligations.execute!({ firmProfile: DEMO_FIRM_PROFILE }, {} as never);
    expect(result).toEqual({ candidateIds: narrowObligationsPure(DEMO_FIRM_PROFILE, vendoredRecords) });
  });
});
