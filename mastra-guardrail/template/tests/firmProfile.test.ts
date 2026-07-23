/**
 * `firmProfile.ts` — the schema, the generated demo profile, and the §9a match
 * guarantee `firmProfileForRecord` is claimed to satisfy.
 *
 * The guarantee is asserted here at the level this module owns: both of
 * `narrowObligationsPure`'s REQUIRED predicates hold for every record against its
 * own generated profile. `narrowObligations.test.ts` (P6.7) re-asserts it through
 * the real narrowing implementation once that exists; this file states it against
 * the predicates themselves, so a firmProfile regression is caught here rather
 * than surfacing as a narrowing failure two modules away.
 */
import { describe, expect, test } from "vitest";
import { DEMO_FIRM_PROFILE, FirmProfileSchema, firmProfileForRecord } from "../src/firmProfile";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import { DEMO_TRIGGER_RECORD_ID } from "../src/config";
import { loadVendoredClearedSet } from "./fixtures";

const records: ClearedRecord[] = ClearedRecordSchema.array().parse(loadVendoredClearedSet());

/** §9a's required predicate 1, restated against the profile only. */
function jurisdictionMatches(record: ClearedRecord, firm: { jurisdiction: { country: string; bloc: string | null } }): boolean {
  if (record.jurisdiction.country && record.jurisdiction.country === firm.jurisdiction.country) return true;
  if (record.jurisdiction.bloc && record.jurisdiction.bloc === firm.jurisdiction.bloc) return true;
  return false;
}

function intersects(left: readonly string[], right: readonly string[]): boolean {
  const lowered = new Set(right.map(v => v.toLowerCase()));
  return left.some(v => lowered.has(v.toLowerCase()));
}

describe("DEMO_FIRM_PROFILE", () => {
  test("is generated, well-formed, and parses with FirmProfileSchema", () => {
    expect(FirmProfileSchema.safeParse(DEMO_FIRM_PROFILE).success).toBe(true);
  });

  test("uses impactedFunctions (camelCase) — D18", () => {
    // In TypeScript a misspelled property is not an error, it is `undefined`, so
    // `impacted_functions` here would make narrowing silently lose one of its two
    // required predicates while still firing, still blocking, still looking
    // correct. That is why this is asserted rather than left to the type-checker:
    // the generator writes this object as JSON, and JSON does not type-check.
    expect(DEMO_FIRM_PROFILE).toHaveProperty("impactedFunctions");
    expect(DEMO_FIRM_PROFILE).not.toHaveProperty("impacted_functions");
  });

  test("is exactly firmProfileForRecord(trigger) — the generator emits no other construction", () => {
    const trigger = records.find(r => r.id === DEMO_TRIGGER_RECORD_ID);
    expect(trigger).toBeDefined();
    expect(DEMO_FIRM_PROFILE).toEqual(firmProfileForRecord(trigger!));
  });
});

describe("firmProfileForRecord — §9a's match guarantee", () => {
  test("every cleared record satisfies BOTH required predicates against its own profile", () => {
    for (const record of records) {
      const firm = firmProfileForRecord(record);
      expect({ id: record.id, jurisdiction: jurisdictionMatches(record, firm) })
        .toEqual({ id: record.id, jurisdiction: true });
      const topical =
        intersects(record.impacted_business.industry, [...firm.industry, firm.sector])
        || intersects(record.impacted_functions, firm.impactedFunctions);
      expect({ id: record.id, topical }).toEqual({ id: record.id, topical: true });
    }
  });

  test("copies country and bloc across, so one jurisdiction branch always fires", () => {
    for (const record of records) {
      const firm = firmProfileForRecord(record);
      expect(firm.jurisdiction.country).toBe(record.jurisdiction.country ?? "");
      expect(firm.jurisdiction.bloc).toBe(record.jurisdiction.bloc);
    }
  });

  test("duplicates industry[0] into sector — the duplication overlapCount's direction turns on", () => {
    // Not incidental: because `sector` is always a copy of `industry[0]`,
    // overlapCount MUST iterate the record's tags against a SET of the firm's
    // (D24 #1). Iterating the other direction double-counts this duplicate and
    // can flip top-5 membership.
    for (const record of records) {
      const firm = firmProfileForRecord(record);
      expect(firm.sector).toBe(record.impacted_business.industry[0] ?? "");
      expect(firm.industry).toEqual(record.impacted_business.industry);
    }
  });

  test("every generated profile parses with FirmProfileSchema", () => {
    for (const record of records) {
      expect(FirmProfileSchema.safeParse(firmProfileForRecord(record)).success).toBe(true);
    }
  });

  test("falls back to \"\" for a null country rather than dropping the key", () => {
    const nullCountry = records.find(r => r.jurisdiction.country === null);
    expect(nullCountry, "fixture must cover the bloc-only jurisdiction branch").toBeDefined();
    const firm = firmProfileForRecord(nullCountry!);
    expect(firm.jurisdiction.country).toBe("");
    expect(firm.jurisdiction.bloc).not.toBeNull();
  });
});
