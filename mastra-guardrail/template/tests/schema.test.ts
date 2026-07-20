/**
 * §5's seam test: the vendored cleared set parses, for every record, with the
 * TypeScript half's own Zod schema.
 *
 * This is what makes P8.1's wholesale swap of `src/data/cleared-set.json` (the
 * synthetic set out, the real reviewed set in) safe: the two halves hand-maintain
 * their schema objects because goal #1 forbids the import, so a key or type wrong
 * on either side drifts SILENTLY and surfaces as a demo that does not fire. Here
 * it is a red test instead.
 */
import { describe, expect, test } from "vitest";
import { ClearedRecordSchema, StageBResponseSchema } from "../src/schema";
import { loadVendoredClearedSet } from "./fixtures";

const vendored = loadVendoredClearedSet() as unknown[];

describe("vendored cleared set", () => {
  test("is a non-empty array", () => {
    expect(Array.isArray(vendored)).toBe(true);
    expect(vendored.length).toBeGreaterThan(0);
  });

  test("every record parses with ClearedRecordSchema", () => {
    for (const [index, record] of vendored.entries()) {
      const parsed = ClearedRecordSchema.safeParse(record);
      // The id (when readable at all) makes a failure locatable without
      // eyeballing 300 lines of JSON.
      const id = (record as { id?: unknown })?.id ?? `index ${index}`;
      expect(parsed.success ? null : { id, issues: parsed.error.issues }).toBeNull();
    }
  });

  test("record ids are unique — narrowing and the eval ledger both key on them", () => {
    const ids = vendored.map(r => (r as { id: string }).id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("ClearedRecordSchema", () => {
  const valid = ClearedRecordSchema.parse(vendored[0]);

  test("is .strict() — an unlisted top-level key is rejected", () => {
    // Mirrors validate_cleared_record()'s Python-side rejection of unlisted keys.
    // `relevance` is the field goal.md names explicitly as never shipping.
    const withExtra = { ...valid, relevance: "high" };
    expect(ClearedRecordSchema.safeParse(withExtra).success).toBe(false);
  });

  test("rejects an empty baseline_failures — no evidence, no record (goal #2)", () => {
    expect(ClearedRecordSchema.safeParse({ ...valid, baseline_failures: [] }).success).toBe(false);
  });

  test("rejects an attestation other than exactly 'approved'", () => {
    const human_review = { ...valid.human_review, attestation: "rejected" };
    expect(ClearedRecordSchema.safeParse({ ...valid, human_review }).success).toBe(false);
  });

  test("rejects a citation url that is not a URL — goal #8 cannot be attempted against one", () => {
    const citation = { ...valid.citation, url: "not-a-url" };
    expect(ClearedRecordSchema.safeParse({ ...valid, citation }).success).toBe(false);
  });

  test("allows a null compliance_date — many records legitimately have none", () => {
    expect(ClearedRecordSchema.safeParse({ ...valid, compliance_date: null }).success).toBe(true);
  });
});

describe("StageBResponseSchema", () => {
  test("parses Stage B's structured answer, nulls and all", () => {
    const parsed = StageBResponseSchema.safeParse({
      knows_source: false,
      source_name: null,
      source_url: null,
      compliance_date: null,
      confidence_note: "Not confident of a real, correctly-dated source.",
    });
    expect(parsed.success).toBe(true);
  });

  test("requires knows_source — the field the citation scorer branches on", () => {
    expect(StageBResponseSchema.safeParse({
      source_name: null, source_url: null, compliance_date: null, confidence_note: "",
    }).success).toBe(false);
  });
});
