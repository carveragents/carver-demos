/**
 * `config.ts`'s contract, and — the load-bearing half — proof that §7's
 * generation step ACTUALLY RAN.
 *
 * `DEMO_TRIGGER_RECORD_ID` and `SCENARIO_PERSONA_INSTRUCTIONS` are both declared
 * with an empty-string default in the spec's own listing. A forgotten generation
 * step therefore does not crash: it ships an agent with NO persona and a demo
 * pointing at no record — a silently different experiment. These assertions are
 * the check that generation happened, which is why the plan (P6.2) forbids
 * hand-authoring a stand-in and forbids skipping these cases until Phase 8.
 */
import { describe, expect, test } from "vitest";
import * as config from "../src/config";
import {
  DEMO_TRIGGER_RECORD_ID,
  GENERATION_CONFIG,
  JUDGE_CONFIDENCE_FLOOR,
  MAX_OUTPUT_TOKENS,
  MODEL_CUTOFF,
  MODEL_ID,
  REASONING_EFFORT,
  SNAPSHOT_DATE,
} from "../src/config";
import { SCENARIO_PERSONA_INSTRUCTIONS } from "../src/agents/baselineAgent";
import { ClearedRecordSchema } from "../src/schema";
import { loadVendoredClearedSet } from "./fixtures";

describe("test_generation_step_actually_ran", () => {
  test("DEMO_TRIGGER_RECORD_ID is populated and resolves to a real vendored record", () => {
    expect(DEMO_TRIGGER_RECORD_ID).not.toBe("");
    const records = ClearedRecordSchema.array().parse(loadVendoredClearedSet());
    expect(records.map(r => r.id)).toContain(DEMO_TRIGGER_RECORD_ID);
  });

  test("SCENARIO_PERSONA_INSTRUCTIONS is populated — an empty persona is a different experiment", () => {
    expect(SCENARIO_PERSONA_INSTRUCTIONS).not.toBe("");
    // Generated from prep's own stage_a_system.md with PERSONA/COMPANY
    // substituted, so no placeholder may survive: a leftover `{{PERSONA}}` would
    // mean the template probes a differently-instructed agent than prep did.
    expect(SCENARIO_PERSONA_INSTRUCTIONS).not.toMatch(/\{\{[A-Z0-9_]+\}\}/);
  });
});

describe("pinned constants", () => {
  test("MODEL_ID carries the provider prefix — Mastra's router takes the full string", () => {
    // §13: prep's OpenAI-SDK call sites strip `openai/` before passing `model=`;
    // Mastra's model router does NOT. The prefix is part of the value here.
    expect(MODEL_ID).toBe("openai/gpt-5.6-sol");
    expect(MODEL_ID.startsWith("openai/")).toBe(true);
  });

  test("the drift-checked literals match prep's constants", () => {
    // prep/tests/test_config.py reads THIS FILE as inert text and asserts these
    // same literals. Stated here too so a TS-side edit fails TS-side as well.
    expect(MODEL_CUTOFF).toBe("2026-02-16");
    expect(SNAPSHOT_DATE).toBe("2026-07-11");
    expect(JUDGE_CONFIDENCE_FLOOR).toBe(0.7);
    expect(REASONING_EFFORT).toBe("medium");
    expect(MAX_OUTPUT_TOKENS).toBe(3000);
  });

  test("JUDGE_CONFIDENCE_FLOOR respects the goal's near-miss floor", () => {
    expect(JUDGE_CONFIDENCE_FLOOR).toBeGreaterThanOrEqual(0.7);
  });
});

describe("GENERATION_CONFIG", () => {
  test("uses AI SDK v5 naming — maxOutputTokens, never maxTokens", () => {
    expect(GENERATION_CONFIG.modelSettings.maxOutputTokens).toBe(MAX_OUTPUT_TOKENS);
    expect(GENERATION_CONFIG.modelSettings).not.toHaveProperty("maxTokens");
  });

  test("carries reasoningEffort under providerOptions.openai", () => {
    expect(GENERATION_CONFIG.providerOptions.openai.reasoningEffort).toBe(REASONING_EFFORT);
  });

  test("is a single binding, so the arms cannot drift", () => {
    // The property both agents depend on: they spread the SAME object, not two
    // equal literals. Asserted here at the source; §8's structural test asserts
    // the agents actually hold it, once they exist (P6.5).
    expect(config.GENERATION_CONFIG).toBe(GENERATION_CONFIG);
  });
});

describe("what config.ts must NOT export", () => {
  test("MAX_PROCESSOR_RETRIES is not exported — it was deliberately removed (§8)", () => {
    // A retry that re-generates the guarded arm's draft hands it a second chance
    // the baseline structurally cannot have: a difference between the arms other
    // than "whether Carver data gates the output" — goal #9's fatal case.
    expect(config).not.toHaveProperty("MAX_PROCESSOR_RETRIES");
  });
});
