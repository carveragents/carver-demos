/**
 * `prompts.test.ts` — fair-test discipline, template-side (spec §3/§12, plan P6.13).
 *
 * The fair-test property: the prompt handed to the baseline MAY contain the
 * persona, the company, a `DOMAIN_BUCKETS` phrase and a jurisdiction phrase —
 * and NOTHING from the record itself. This is the template-side mirror of
 * `prep/tests/test_probe.py::test_task_instance_excludes_leaked_fields` (see
 * that docstring: the fixture there is real, non-trivial data specifically so
 * the assertion isn't vacuous — same reasoning applies here, against the real
 * vendored `cleared-set.json`). If record content leaks into the baseline's
 * prompt, the baseline isn't a baseline, the side-by-side comparison is
 * meaningless, and the demo's central claim is false.
 *
 * `src/scenario/prompts.ts` is GENERATED (do not hand-edit) — this test's
 * subject is real generated source from the first run, never a hand-authored
 * stand-in (P6.13's own rationale for being a task rather than a footnote:
 * nothing structural stops a future edit from interpolating `record.title`
 * "to make the prompt more realistic" and silently leaking the answer into
 * the question the whole experiment turns on).
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";
import {
  buildStageAPrompt,
  buildStageBPrompt,
  DOMAIN_BUCKETS,
  INDUSTRY_TAG_TO_BUCKET,
  NEGATIVE_CONTROL_PROMPTS,
  SCENARIO_TASK_TEMPLATES,
} from "../src/scenario/prompts";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import { loadVendoredClearedSet } from "./fixtures";

const HERE = dirname(fileURLToPath(import.meta.url));

const vendoredRecords: ClearedRecord[] = ClearedRecordSchema.array().parse(loadVendoredClearedSet());

// ── Every field spec §3's MUST-NOT list forbids from either prompt, for a
// given record: the regulator's name, the regulation's title/citation, any
// compliance date, and the free-text obligation fields. Mirrors
// `test_probe.py`'s `_forbidden_substrings` on the Python side. Deliberately
// excludes jurisdiction (country/bloc)/industry/update_type — those are the
// record-derived signals §3 explicitly ALLOWS into the prompt, funneled
// through the closed DOMAIN_BUCKETS / jurisdiction lookups rather than
// rendered verbatim.
function forbiddenSubstrings(record: ClearedRecord): string[] {
  const strings = [
    record.title,
    record.regulator_name,
    record.objective,
    record.what_changed,
    record.why_it_matters,
    record.citation.name,
    record.citation.url,
    ...record.key_requirements,
  ];
  if (record.compliance_date) strings.push(record.compliance_date);
  return strings.filter(s => s.trim().length > 0);
}

describe("fair-test discipline — prompt builders never leak record content (P6.13)", () => {
  test("fixture sanity: every vendored record actually carries forbidden content", () => {
    // If this were empty for any record, the leak checks below would pass
    // vacuously against that record — same guard prep's test asserts.
    for (const record of vendoredRecords) {
      expect(forbiddenSubstrings(record).length, `${record.id} carries no forbidden content`).toBeGreaterThan(0);
    }
  });

  test("buildStageAPrompt leaks nothing from any vendored record", () => {
    for (const record of vendoredRecords) {
      const prompt = buildStageAPrompt(record);
      expect(prompt, `${record.id}: unrendered {{...}} placeholder survived into Stage A prompt`).not.toContain("{{");
      for (const leaked of forbiddenSubstrings(record)) {
        expect(prompt, `${record.id}: record field leaked into Stage A prompt: ${JSON.stringify(leaked)}`).not.toContain(leaked);
      }
    }
  });

  test("buildStageBPrompt leaks nothing from any vendored record", () => {
    for (const record of vendoredRecords) {
      const prompt = buildStageBPrompt(record);
      expect(prompt, `${record.id}: unrendered {{...}} placeholder survived into Stage B prompt`).not.toContain("{{");
      for (const leaked of forbiddenSubstrings(record)) {
        expect(prompt, `${record.id}: record field leaked into Stage B prompt: ${JSON.stringify(leaked)}`).not.toContain(leaked);
      }
    }
  });

  test("buildStageAPrompt always carries a DOMAIN_BUCKETS phrase", () => {
    for (const record of vendoredRecords) {
      const prompt = buildStageAPrompt(record);
      const carriesBucket = DOMAIN_BUCKETS.some(bucket => prompt.includes(bucket));
      expect(carriesBucket, `${record.id}: no DOMAIN_BUCKETS phrase found in Stage A prompt: ${prompt}`).toBe(true);
    }
  });

  test("buildStageBPrompt always carries a DOMAIN_BUCKETS phrase", () => {
    for (const record of vendoredRecords) {
      const prompt = buildStageBPrompt(record);
      const carriesBucket = DOMAIN_BUCKETS.some(bucket => prompt.includes(bucket));
      expect(carriesBucket, `${record.id}: no DOMAIN_BUCKETS phrase found in Stage B prompt: ${prompt}`).toBe(true);
    }
  });
});

// ── buckets_golden.json parity ───────────────────────────────────────────
//
// Shared, byte-identical fixture (`tests/fixtures/buckets_golden.json`, dup'd
// in `prep/tests/fixtures/`) — asserted by prep's `test_buckets_golden_parity`
// against the Python `INDUSTRY_TAG_TO_BUCKET` and here against the TypeScript
// copy. If the two disagree, a record's prompt asks a DIFFERENT question than
// the one its baseline_failures evidence was recorded against.

type BucketCase = { tag: string; expected_bucket: string };
type UnmappedTagDefaultCase = { tag: string; scenario: string; expected_bucket: string; note?: string };
type BucketsGolden = {
  tag_bucket_cases: BucketCase[];
  unmapped_tag_default_cases: UnmappedTagDefaultCase[];
};

function loadBucketsGolden(): BucketsGolden {
  return JSON.parse(readFileSync(resolve(HERE, "./fixtures/buckets_golden.json"), "utf-8"));
}

const bucketsGolden = loadBucketsGolden();

describe("INDUSTRY_TAG_TO_BUCKET — buckets_golden.json parity (shared with prep/tests/test_scenarios.py)", () => {
  test("reproduces every tag_bucket_cases entry", () => {
    for (const { tag, expected_bucket } of bucketsGolden.tag_bucket_cases) {
      expect(INDUSTRY_TAG_TO_BUCKET[tag], `INDUSTRY_TAG_TO_BUCKET[${JSON.stringify(tag)}]`).toBe(expected_bucket);
    }
  });

  test("reproduces the unmapped-tag default for the shipped scenario", () => {
    // buckets_golden.json's own `_groups.unmapped_tag_default_cases` note
    // documents why the template can only run the case matching the shipped
    // scenario: DOMAIN_BUCKETS here is a FLAT, single-scenario list (goal #10
    // ships exactly one scenario), unlike prep's per-scenario dict — so only
    // the shipped scenario's default is expressible on this side.
    const shippedCase = bucketsGolden.unmapped_tag_default_cases.find(
      c => c.scenario === SCENARIO_TASK_TEMPLATES.id
    );
    expect(shippedCase, `no unmapped_tag_default_cases entry for shipped scenario ${SCENARIO_TASK_TEMPLATES.id}`).toBeDefined();
    // The tag really is unmapped — otherwise the fallback path is never exercised.
    expect(INDUSTRY_TAG_TO_BUCKET[shippedCase!.tag]).toBeUndefined();

    const base = vendoredRecords[0];
    const record: ClearedRecord = {
      ...base,
      impacted_business: { ...base.impacted_business, industry: [shippedCase!.tag] },
      impacted_functions: [],
    };
    expect(buildStageAPrompt(record)).toContain(shippedCase!.expected_bucket);
  });
});

// ── NEGATIVE_CONTROL_PROMPTS — benign against the same standard (D16) ───────
//
// D16 (docs/orchestrator-decisions.md): the spec's own negative-control task
// once contained a trigger keyword ("marketing"), failing the very
// benign-ness property it exists to police for the specificity measurement
// (V1). Re-check the generated copy here rather than assume it is clean.
// `keywordAppears` mirrors prompts.ts's own (unexported) `tagMatchesKeyword`:
// multi-word keywords match as a plain substring, single-word keywords are
// word-bounded (so "ai" cannot false-positive on "email"/"campaign"/etc.).
function keywordAppears(text: string, keyword: string): boolean {
  const lower = text.toLowerCase();
  const kw = keyword.toLowerCase();
  if (kw.includes(" ")) return lower.includes(kw);
  return new RegExp(`\\b${kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(lower);
}

describe("NEGATIVE_CONTROL_PROMPTS — benign against the same standard (D16)", () => {
  test("closed set: exactly 30 unique, non-empty prompts (10 topics x 3 framings)", () => {
    expect(NEGATIVE_CONTROL_PROMPTS.length).toBe(30);
    expect(new Set(NEGATIVE_CONTROL_PROMPTS).size).toBe(30);
    for (const prompt of NEGATIVE_CONTROL_PROMPTS) {
      expect(prompt.trim().length).toBeGreaterThan(0);
    }
  });

  test("no prompt contains an INDUSTRY_TAG_TO_BUCKET trigger keyword", () => {
    const keywords = Object.keys(INDUSTRY_TAG_TO_BUCKET);
    for (const prompt of NEGATIVE_CONTROL_PROMPTS) {
      const hits = keywords.filter(kw => keywordAppears(prompt, kw));
      expect(hits, `"${prompt}" contains trigger keyword(s): ${JSON.stringify(hits)}`).toEqual([]);
    }
  });
});
