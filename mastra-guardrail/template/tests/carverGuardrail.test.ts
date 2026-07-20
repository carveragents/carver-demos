/**
 * `carverGuardrail.test.ts` — the guardrail's own suite, written incrementally
 * by four tasks (P6.5 → P6.6 → P6.9 → P6.10) in the order the phase runs them.
 * Each task adds ONLY its own `describe` block and ONLY that block's imports: a
 * file that imports a not-yet-created export fails to LOAD, and every case in it
 * errors — `-t` filters which tests execute, it does not stop the module load.
 *
 *   shared agent config — P6.5 (landed), owners: src/agents/*
 *   runJudge            — P6.6 (landed), owner: src/judge/callJudge.ts
 *   the three stages    — P6.9, owner: src/processors/carverGuardrail.ts
 *   the guarded arm     — P6.10, owner: src/agents/guardedAgent.ts
 *
 * NO REAL API CALLS. Constructing an Agent makes no network call (§8's module
 * table: "none (construction only)"), and every test that needs a model response
 * stubs `judgeAgent.generate` (below).
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, test, vi } from "vitest";
import { Agent, TripWire } from "@mastra/core/agent";
import { RequestContext } from "@mastra/core/request-context";
import { GENERATION_CONFIG, JUDGE_CONFIDENCE_FLOOR, MODEL_ID } from "../src/config";
import { SHARED_AGENT_CONFIG } from "../src/agents/sharedConfig";
import { SCENARIO_PERSONA_INSTRUCTIONS, baselineAgent } from "../src/agents/baselineAgent";
import { guardedAgent } from "../src/agents/guardedAgent";
import { judgeAgent } from "../src/agents/judgeAgent";
import { JUDGE_SYSTEM_PROMPT, RATIONALE_OMITTED } from "../src/judge/contract";
import { runJudge } from "../src/judge/callJudge";
import {
  CarverGuardrail,
  type AuditEntry,
  type AuditWriter,
  type Severity,
} from "../src/processors/carverGuardrail";
import { normalizeDelivery } from "../src/processors/tripwireContainment";
import { narrowObligationsPure } from "../src/tools/narrowObligations";
import { DEMO_FIRM_PROFILE, firmProfileForRecord, type FirmProfile } from "../src/firmProfile";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import { loadVendoredClearedSet } from "./fixtures";

describe("shared agent config", () => {
  test("every agent holds GENERATION_CONFIG by reference — the same object, never an equal copy", async () => {
    // THE experiment (goal #9): the baseline and guarded arms must differ ONLY
    // in whether Carver data gates the output. If they drifted in model, output
    // cap or reasoning effort, the scoreboard would be measuring a configuration
    // difference — and, worse, it would LOOK like the guardrail working.
    //
    // Asserted as identity, not equality: two equal literals can drift on the
    // next edit; one object cannot. guardedAgent (P6.10) spreads THIS same
    // object, so proving here that the spread preserves the reference proves it
    // for the arm that does not exist yet — which is the assertion P6.3's test
    // list asked for and could not yet make.
    expect(SHARED_AGENT_CONFIG.defaultOptions).toBe(GENERATION_CONFIG);
    expect(await baselineAgent.getDefaultOptions()).toBe(GENERATION_CONFIG);

    // judgeAgent is NOT one of the compared arms — the controlled-experiment
    // discipline is about the two BUSINESS generations. It takes the same object
    // for a different reason: it answers the same judge question prep's
    // `run_judge` asks, so it must reason at the same effort, or the template's
    // verdicts and prep's would come from differently-configured judges.
    expect(await judgeAgent.getDefaultOptions()).toBe(GENERATION_CONFIG);
  });

  test("the shared instructions and model are static strings — a dynamic config function is the only path from requestContext into a prompt", async () => {
    // STRUCTURAL (§8): `requestContext` is a dependency-injection container, not
    // prompt content. Its values reach the model ONLY through a dynamic
    // configuration function — `instructions`/`model` written as a function of
    // ({ requestContext }). Static values cannot close over a context they never
    // receive. If the firm profile could reach the guarded arm's prompt, the two
    // arms would differ in their INPUT, not only in whether Carver data gates
    // their OUTPUT — goal #9's fatal case.
    expect(typeof SHARED_AGENT_CONFIG.instructions).toBe("string");
    expect(typeof SHARED_AGENT_CONFIG.model).toBe("string");
    expect(SHARED_AGENT_CONFIG.instructions).toBe(SCENARIO_PERSONA_INSTRUCTIONS);
    expect(SHARED_AGENT_CONFIG.model).toBe(MODEL_ID);

    // BEHAVIOURAL, via the public accessors — `instructions` and `tools` are not
    // public fields on Agent, so reading them off the instance proves nothing.
    expect(await baselineAgent.getInstructions()).toBe(SCENARIO_PERSONA_INSTRUCTIONS);
    expect(await baselineAgent.listTools()).toEqual({});   // the baseline has no tools (§8)
  });

  test("judgeAgent shares the pinned model but never the business persona", async () => {
    // Its instructions are the judge prompt, not the persona: it is internal
    // machinery, never a branch of the experiment. Reference equality, because
    // §4's contract is that BOTH halves ask the identical question — a hand-copy
    // of the prompt here would be a second, drifting judge.
    expect(await judgeAgent.getInstructions()).toBe(JUDGE_SYSTEM_PROMPT);
    expect(await judgeAgent.getInstructions()).not.toBe(SCENARIO_PERSONA_INSTRUCTIONS);
    expect(await judgeAgent.listTools()).toEqual({});   // no tools, and no outputProcessors (§8)
  });
});

describe("runJudge", () => {
  const OBLIGATIONS = [
    { id: "ob-1", title: "Disclosure duty", key_requirements: ["Disclose the thing"], objective: "Protect consumers" },
    { id: "ob-2", title: "Record keeping", key_requirements: ["Keep the records"], objective: "Auditability" },
  ];

  const uncertainFallbackFor = (id: string) => ({
    obligation_id: id,
    applies_to_draft: false,
    omission_material: false,
    verdict: "uncertain",
    confidence: 0,
    rationale: RATIONALE_OMITTED,
  });

  // The ONLY judgeAgent call path is stubbed at its one seam — no network, and
  // no `mastra.getAgent` indirection to fake.
  const stubGenerate = () => vi.spyOn(judgeAgent, "generate");

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("a judge that fails on both attempts degrades to all-uncertain — it never propagates, so a broken judge cannot block", async () => {
    // Mastra surfaces malformed JSON, a missing field, AND an out-of-range
    // confidence (rejected by GuardrailVerdictSchema's .min(0).max(1)) the same
    // way: as a THROW from generate(), never an inspectable value. Adding the
    // Zod bound introduced that path; this is the test that it did not become a
    // new crash. "uncertain" fails §9c's four-condition conjunction, so the
    // guarded arm passes the draft through — the guardrail blocks only on
    // affirmative, in-range, applicable, material evidence, never because
    // something went wrong.
    const generate = stubGenerate().mockRejectedValue(new Error("provider exploded"));

    const result = await runJudge(OBLIGATIONS, "a draft about something");

    expect(generate).toHaveBeenCalledTimes(2);   // retried exactly ONCE (§15), never a loop
    expect(result.verdicts).toEqual([uncertainFallbackFor("ob-1"), uncertainFallbackFor("ob-2")]);
  });

  test("a malformed first attempt is retried once with the same input, and the retry's verdicts are returned", async () => {
    const verdicts = [{
      obligation_id: "ob-1",
      applies_to_draft: true,
      omission_material: true,
      verdict: "violation",
      confidence: 0.91,
      rationale: "The draft omits the disclosure requirement.",
    }];
    const generate = stubGenerate()
      .mockRejectedValueOnce(new Error("could not parse structured output"))
      .mockResolvedValueOnce({ object: { verdicts } } as never);

    const result = await runJudge([OBLIGATIONS[0]], "a draft about something");

    expect(generate).toHaveBeenCalledTimes(2);
    // The SAME input — a retry that re-rendered or re-worded the prompt would be
    // asking the judge a different question than the one that failed.
    expect(generate.mock.calls[1][0]).toBe(generate.mock.calls[0][0]);
    expect(result.verdicts).toEqual(verdicts);
  });
});

// ── P6.9 / P6.10 shared harness ─────────────────────────────────────────────

const HERE = dirname(fileURLToPath(import.meta.url));

/** Parsed by Zod from the file itself, never a JSON import: the vendored set is
 *  the thing under test everywhere else, and it must not type-check against its
 *  own drift (`fixtures.ts`'s rule). */
const vendoredRecords: ClearedRecord[] = ClearedRecordSchema.array().parse(loadVendoredClearedSet());

/** The exact args Mastra hands `processOutputResult` — taken FROM the method,
 *  so a stub cannot drift from the real signature. The end-to-end case below
 *  drives a REAL Agent through the REAL machinery, which is what proves the
 *  fields these stubs fill are the fields Mastra actually populates. */
type ProcessorArgs = Parameters<CarverGuardrail["processOutputResult"]>[0];

const DRAFT = "Smart ranking is now live for every customer in Germany. It just works.";

/** What the stub language model below "drafts" — kept distinct from DRAFT so the
 *  end-to-end case proves the blocked text came from the REAL generation path
 *  and not from a fixture that happens to match. */
const STUB_DRAFT = "Our new AI ranking decides what you see. No disclosure needed — it just works.";

/** A LanguageModelV2 that answers from memory: no network, no key, no cost.
 *  The same stub `tripwireContainment.test.ts` uses, for the same reason —
 *  everything else in the end-to-end case must be REAL. */
const stubModel = {
  specificationVersion: "v2",
  provider: "stub",
  modelId: "stub-model",
  supportedUrls: {},
  async doGenerate() {
    return {
      content: [{ type: "text", text: STUB_DRAFT }],
      finishReason: "stop",
      usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2 },
      warnings: [],
    };
  },
  async doStream() {
    return {
      stream: new ReadableStream({
        start(controller) {
          controller.enqueue({ type: "stream-start", warnings: [] });
          controller.enqueue({ type: "response-metadata", id: "1", modelId: "stub-model", timestamp: new Date() });
          controller.enqueue({ type: "text-start", id: "t1" });
          controller.enqueue({ type: "text-delta", id: "t1", delta: STUB_DRAFT });
          controller.enqueue({ type: "text-end", id: "t1" });
          controller.enqueue({
            type: "finish",
            finishReason: "stop",
            usage: { inputTokens: 1, outputTokens: 1, totalTokens: 2 },
          });
          controller.close();
        },
      }),
    };
  },
} as any;

class FakeAuditWriter implements AuditWriter {
  readonly entries: AuditEntry[] = [];
  write(entry: AuditEntry): void {
    this.entries.push(entry);
  }
}

/** `new RequestContext({ firmProfile })` — the form §8/§10/§11/§12 all pin —
 *  does NOT compile against @mastra/core 1.51.0 (TS2353: the constructor takes
 *  an ENTRY-TUPLE iterable, not an object literal). Flagged, not silently fixed;
 *  this is the form that compiles. Deliberately left as `RequestContext<unknown>`
 *  — the typed `RequestContext<{firmProfile: FirmProfile}>` is NOT assignable to
 *  the `RequestContext<unknown>` the Agent accessors take. */
const contextFor = (firmProfile: FirmProfile) =>
  new RequestContext<unknown>([["firmProfile", firmProfile]]);

const assistantMessage = (text: string) => ({
  id: "assistant-1",
  role: "assistant" as const,
  createdAt: new Date(),
  content: { format: 2 as const, parts: [{ type: "text" as const, text }], content: text },
});

/** A REAL `TripWire`, thrown exactly as Mastra's own `abort()` throws it
 *  (`new TripWire(reason, options, processorId)`) — never an imitation of what
 *  we assume abort() does. */
function recordingAbort() {
  const calls: { reason?: string; metadata?: any }[] = [];
  const abort = ((reason?: string, options?: { metadata?: unknown }) => {
    calls.push({ reason, metadata: options?.metadata });
    throw new TripWire(reason ?? "", options ?? {}, "carver-guardrail");
  }) as ProcessorArgs["abort"];
  return { calls, abort };
}

function makeArgs(options: {
  abort: ProcessorArgs["abort"];
  firmProfile?: FirmProfile;
  text?: string;
}): ProcessorArgs {
  const text = options.text ?? DRAFT;
  return {
    messages: [assistantMessage(text)],
    // `result.text` is what the processor judges and what `blocked_draft`
    // carries — Mastra's own resolved draft (verified below against a real run).
    result: { text, usage: {}, finishReason: "stop", steps: [] },
    requestContext: options.firmProfile === undefined ? undefined : contextFor(options.firmProfile),
    abort: options.abort,
    state: {},
    retryCount: 0,
  } as unknown as ProcessorArgs;
}

const violationOf = (id: string, overrides: Record<string, unknown> = {}) => ({
  obligation_id: id,
  applies_to_draft: true,
  omission_material: true,
  verdict: "violation",
  confidence: 0.95,
  rationale: `The draft omits ${id}'s key requirement.`,
  ...overrides,
});

/** Stubs the ONE judge seam (`judge/callJudge.ts` is the only caller). No
 *  network, no key, no cost. */
const stubJudge = (verdicts: unknown[]) =>
  vi.spyOn(judgeAgent, "generate").mockResolvedValue({ object: { verdicts } } as never);

/**
 * A single-record cleared set at a chosen severity, narrowed by that record's
 * OWN generated profile (§9a's proved guarantee makes the match certain).
 *
 * The cast is the point, and it is honest: `ClearedRecordSchema.impact_label` is
 * the literal `"high"` because goal #3's candidate filter admits nothing else,
 * so `medium`/`low` are unreachable by any record that could legitimately exist
 * — the spec's own Goal-issue callout. §14 nonetheless requires both branches be
 * exercised, and a fixture that deliberately violates the schema's literal is
 * the only way to reach code that real data never can.
 */
function syntheticSetAt(severity: Severity): { clearedSet: ClearedRecord[]; firmProfile: FirmProfile; record: ClearedRecord } {
  const base = vendoredRecords.find(record => record.id === "art-1003")!;
  const record = { ...base, impact_label: severity } as unknown as ClearedRecord;
  return { clearedSet: [record], firmProfile: firmProfileForRecord(base), record };
}

describe("the three stages — narrow, verdict, enforce", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // The rank order every case below asserts against: narrowObligationsPure's
  // output for the demo profile, read from the real implementation rather than
  // hard-coded, so a ranking change surfaces as a narrowing failure (its own
  // suite's job) instead of silently rewriting this file's expectations.
  const candidateIds = narrowObligationsPure(DEMO_FIRM_PROFILE, vendoredRecords);

  test("no candidate obligations: the draft passes through untouched, the judge is never called, and nothing is audited", async () => {
    // §9a's zero-candidate case. NO audit write — the log's semantics are "a
    // violation occurred", and a narrowing miss is not one.
    const writer = new FakeAuditWriter();
    const generate = stubJudge([]);
    const { calls, abort } = recordingAbort();
    const unrelatedFirm: FirmProfile = {
      jurisdiction: { country: "ZZ", bloc: null },
      sector: "Deep sea fishing",
      industry: ["Deep sea fishing"],
      size: "medium",
      impactedFunctions: ["Navigation"],
    };
    expect(narrowObligationsPure(unrelatedFirm, vendoredRecords)).toEqual([]);   // premise, not assumed

    const args = makeArgs({ abort, firmProfile: unrelatedFirm });
    const out = await new CarverGuardrail(writer).processOutputResult(args);

    expect(out).toBe(args.messages);
    expect(generate).not.toHaveBeenCalled();   // no LLM call at all — narrowing gates the spend
    expect(writer.entries).toEqual([]);
    expect(calls).toEqual([]);
  });

  test("test_judge_parse_failure_passes_through: a judge that fails twice yields the draft unchanged — never a block, never an exception", async () => {
    // The [0,1] confidence bound (§4) turned malformed JSON, a missing field and
    // an out-of-range confidence into a THROW from generate(). This is the test
    // that adding it did not create a new crash path: runJudge degrades to
    // all-"uncertain", "uncertain" fails §9c's conjunction, and the guarded arm
    // ships the draft. A broken judge must never block, and must never surface
    // to a Studio user as a crashed agent call.
    const writer = new FakeAuditWriter();
    const generate = stubJudge([]).mockRejectedValue(new Error("could not parse structured output"));
    const { calls, abort } = recordingAbort();

    const args = makeArgs({ abort, firmProfile: DEMO_FIRM_PROFILE });
    const out = await new CarverGuardrail(writer).processOutputResult(args);

    expect(generate).toHaveBeenCalledTimes(2);   // tried, and retried once
    expect(out).toBe(args.messages);
    expect(calls).toEqual([]);
    expect(writer.entries).toEqual([]);
  });

  test("a bare \"violation\" never blocks: each of the other three conditions, alone, is enough to pass the draft through", async () => {
    // §9c's four-condition conjunction, the same one prep's
    // score_missed_obligation applies. Narrowing proved topical relevance — it
    // did NOT prove this draft triggers this obligation (applies_to_draft), that
    // the omission is material to a document of this type (omission_material),
    // or that the judge is confident enough to act (the floor). Each verdict
    // below is a "violation" failing exactly one of them.
    const writer = new FakeAuditWriter();
    stubJudge([
      violationOf(candidateIds[0], { confidence: JUDGE_CONFIDENCE_FLOOR - 0.01 }),
      violationOf(candidateIds[1], { applies_to_draft: false }),
      violationOf(candidateIds[2], { omission_material: false }),
    ]);
    const { calls, abort } = recordingAbort();

    const args = makeArgs({ abort, firmProfile: DEMO_FIRM_PROFILE });
    const out = await new CarverGuardrail(writer).processOutputResult(args);

    expect(out).toBe(args.messages);
    expect(calls).toEqual([]);
    expect(writer.entries).toEqual([]);
  });

  test("test_multi_violation_reports_full_set: every violated obligation is reported, in narrowing-rank order, with the audit written BEFORE the abort", async () => {
    // A tripwire can foreground only ONE record, but a draft can violate
    // several. If the block reported only the display record, §12's guarded
    // scorer ("was the ground-truth obligation caught?") would score a MISS
    // whenever a higher-ranked obligation took the display slot — a correct
    // block scored as a failure. The set is the finding; the record is the
    // headline.
    const [first, second, , , fifth] = candidateIds;
    const writer = new FakeAuditWriter();
    // Returned in SCRAMBLED order on purpose: rank order must come from
    // §4's requestedIds-ordered contract, not from the model's whim.
    stubJudge([violationOf(fifth), violationOf(second), violationOf(first)]);
    const { calls, abort } = recordingAbort();
    const expectedIds = [first, second, fifth];
    const display = vendoredRecords.find(record => record.id === first)!;

    const args = makeArgs({ abort, firmProfile: DEMO_FIRM_PROFILE });

    // abort() throws Mastra's REAL TripWire; the processor never contains it.
    await expect(new CarverGuardrail(writer).processOutputResult(args)).rejects.toBeInstanceOf(TripWire);

    // THE METADATA. §10's soundness check REJECTS a block missing any of this
    // and throws — turning a correct block into a loud crash (D26 found exactly
    // that live). So this is not bookkeeping; it is the block's payload.
    expect(calls).toHaveLength(1);
    expect(calls[0].reason).toBe(`The draft omits ${first}'s key requirement.`);
    expect(calls[0].metadata).toEqual({
      processorId: "carver-guardrail",
      blocked_draft: DRAFT,
      violated_obligation_ids: expectedIds,
      record: {
        id: display.id,
        regulator_name: display.regulator_name,
        citation: display.citation,
        compliance_date: display.compliance_date,
        title: display.title,
      },
    });

    // The audit entry carries the same complete finding, and it was written
    // BEFORE abort() threw — abort() never returns, so a write placed after it
    // would mean the ONE branch real data reaches is the one never logged.
    expect(writer.entries).toHaveLength(1);
    expect(writer.entries[0]).toMatchObject({
      processorId: "carver-guardrail",
      obligationId: first,                    // the display record IS violated[0]
      violatedObligationIds: expectedIds,
      severity: "high",
      action: "aborted",
      rationale: `The draft omits ${first}'s key requirement.`,
    });
  });

  test("medium severity annotates the draft with a visible warning instead of blocking it", async () => {
    // Unreachable against real data (every vendored record is impact_label
    // "high" by construction) — the Goal-issue callout's dead branch, exercised
    // here and nowhere else.
    const { clearedSet, firmProfile, record } = syntheticSetAt("medium");
    const writer = new FakeAuditWriter();
    stubJudge([violationOf(record.id)]);
    const { calls, abort } = recordingAbort();

    const args = makeArgs({ abort, firmProfile });
    const out = await new CarverGuardrail(writer, clearedSet).processOutputResult(args);

    expect(calls).toEqual([]);                        // annotated, NOT blocked
    const text = (out[0].content.parts[0] as { text: string }).text;
    expect(text).toContain("COMPLIANCE WARNING");
    expect(text).toContain(record.title);
    expect(out[0].content.content).toContain(DRAFT);  // the draft itself survives
    expect(writer.entries).toMatchObject([{ severity: "medium", action: "annotated", obligationId: record.id }]);
  });

  test("low severity logs the violation and ships the draft exactly as written", async () => {
    const { clearedSet, firmProfile, record } = syntheticSetAt("low");
    const writer = new FakeAuditWriter();
    stubJudge([violationOf(record.id)]);
    const { calls, abort } = recordingAbort();

    const args = makeArgs({ abort, firmProfile });
    const out = await new CarverGuardrail(writer, clearedSet).processOutputResult(args);

    expect(out).toBe(args.messages);
    expect(calls).toEqual([]);
    expect(writer.entries).toMatchObject([{ severity: "low", action: "logged", obligationId: record.id }]);
  });

  test("a missing firm profile fails loudly — it never silently turns the guarded arm into the baseline", async () => {
    // The one non-block exception this processor may raise. Passing through
    // would leave the guardrail switched off by a wiring omission nobody sees,
    // with every test still green. It cannot be mistaken for a block:
    // normalizeDelivery re-throws anything that is not a TripWire (§10).
    const writer = new FakeAuditWriter();
    const { abort } = recordingAbort();

    await expect(new CarverGuardrail(writer).processOutputResult(makeArgs({ abort })))
      .rejects.toThrow(/no firmProfile in requestContext/);
  });

  test("end to end through the REAL Mastra machinery: the block's metadata arrives intact at the caller", async () => {
    // The case that cannot be faked. Everything above stubs `abort` and the
    // args; this drives a REAL Agent with the REAL CarverGuardrail registered as
    // a REAL outputProcessor, and reads the result through the REAL
    // normalizeDelivery. It proves, against Mastra rather than against our
    // assumptions:
    //   1. requestContext REACHES processOutputResult (nothing else in this
    //      project would notice if it stopped);
    //   2. Mastra's own machinery catches abort()'s TripWire and RETURNS
    //      result.tripwire — it does not throw (orchestrator D26);
    //   3. the metadata §10 validates SURVIVES the round trip. D26's live
    //      failure was reading the wrong TripWire properties, which yields a
    //      block with no reason and no obligation ids — which §10 then rejects,
    //      converting a correct block into a crash. This is the assertion that
    //      the payload actually arrives.
    // The ONLY stub is the language model, which is what keeps it free/offline.
    const writer = new FakeAuditWriter();
    stubJudge([violationOf(candidateIds[0])]);
    const agent = new Agent({
      id: "guarded-stub",
      name: "guarded-stub",
      instructions: SCENARIO_PERSONA_INSTRUCTIONS,
      model: stubModel,
      outputProcessors: [new CarverGuardrail(writer)],
    });

    const outcome = await normalizeDelivery(() =>
      agent.generate("Draft the launch announcement", { requestContext: contextFor(DEMO_FIRM_PROFILE) }));

    expect(outcome.tripped).toBe(true);
    if (!outcome.tripped) throw new Error("unreachable — narrowing for TS");
    expect(outcome.processorId).toBe("carver-guardrail");
    expect(outcome.reason).toBe(`The draft omits ${candidateIds[0]}'s key requirement.`);
    expect(outcome.metadata).toMatchObject({
      // The draft the model really produced, blocked before delivery — §11's
      // report shows it, and §10 rejects a block without it.
      blocked_draft: STUB_DRAFT,
      violated_obligation_ids: [candidateIds[0]],
      record: { id: candidateIds[0] },
    });
    expect(writer.entries).toMatchObject([{ action: "aborted", obligationId: candidateIds[0] }]);
  });
});

describe("guarded arm", () => {
  test("test_requestContext_cannot_reach_either_prompt: the firm profile is invisible to both compared agents", async () => {
    // WHY THIS IS THE EXPERIMENT'S GUARD, NOT A LINT. The firm profile goes to
    // the guarded arm only. If Mastra surfaced requestContext into the
    // generation context, guardedAgent would draft KNOWING the firm's
    // jurisdiction, sector and impacted functions while baselineAgent drafts
    // blind — the arms would differ in their INPUT, not only in whether Carver
    // data gates their OUTPUT. That is goal #9's explicitly fatal case, and it
    // would LOOK LIKE SUCCESS: the better-informed arm writes more compliant
    // drafts and the scoreboard reads it as the guardrail working.
    //
    // A dynamic configuration function — instructions/model written as a
    // function of ({ requestContext }) — is the ONLY documented path from the
    // context into a prompt. Static values cannot close over a context they
    // never receive.
    expect(typeof SHARED_AGENT_CONFIG.instructions).toBe("string");
    expect(typeof SHARED_AGENT_CONFIG.model).toBe("string");

    // BEHAVIOURAL: resolve each arm's configuration WITH a populated context and
    // prove the profile's own values are absent from what the model receives.
    const requestContext = contextFor(DEMO_FIRM_PROFILE);
    for (const agent of [baselineAgent, guardedAgent]) {
      const instructions = await agent.getInstructions({ requestContext });
      expect(instructions).toBe(SCENARIO_PERSONA_INSTRUCTIONS);   // unchanged BY the context
      expect(instructions).not.toContain(DEMO_FIRM_PROFILE.jurisdiction.country);
      expect(instructions).not.toContain(DEMO_FIRM_PROFILE.sector);
      expect(await agent.listTools({ requestContext })).toEqual({});   // neither arm has tools (§8)
    }
  });

  test("the two arms are the SAME configuration — same model, same instructions, same generation settings", async () => {
    // §8 asserts `getModel(...) === MODEL_ID`. It cannot pass: getModel()
    // resolves to a model OBJECT, never the router string (orchestrator D27).
    // Re-expressed as the property the experiment actually needs — the two arms
    // are the same model — because that sameness IS the basis of the whole
    // baseline-vs-guarded claim, while string equality tests a coincidence of
    // representation. No key, no network: model RESOLUTION is offline.
    const baselineModel = await baselineAgent.getModel();
    const guardedModel = await guardedAgent.getModel();

    expect(guardedModel.provider).toBe(baselineModel.provider);
    expect(guardedModel.modelId).toBe(baselineModel.modelId);
    // ...and each is the ONE pinned constant, not merely equal to each other.
    expect(`${guardedModel.provider}/${guardedModel.modelId}`).toBe(MODEL_ID);

    expect(await guardedAgent.getInstructions()).toBe(await baselineAgent.getInstructions());
    // Identity, not equality: the Agent constructor preserves the reference, so
    // both arms hold the SAME GENERATION_CONFIG object — there is nothing for a
    // future edit to change on one side and forget on the other.
    expect(await guardedAgent.getDefaultOptions()).toBe(GENERATION_CONFIG);
    expect(await guardedAgent.getDefaultOptions()).toBe(await baselineAgent.getDefaultOptions());
  });

  test("the Carver guardrail is the ONLY difference between the arms", async () => {
    const guardedProcessors = await guardedAgent.listConfiguredOutputProcessors();
    expect(guardedProcessors.map(processor => processor.id)).toEqual(["carver-guardrail"]);
    expect(guardedProcessors[0]).toBeInstanceOf(CarverGuardrail);
    expect(await baselineAgent.listConfiguredOutputProcessors()).toEqual([]);
  });

  test("test_guarded_agent_has_no_processor_retries: the guarded arm cannot get a second draft the baseline structurally cannot have", async () => {
    // §8 asserts `guardedAgent.maxProcessorRetries` is undefined. VERIFIED
    // AGAINST @mastra/core 1.51.0: the Agent constructor keeps it in a private
    // field and exposes NO accessor, so that expression is `undefined` whatever
    // the agent was built with — it passes just as happily with
    // `maxProcessorRetries: 1` set. A vacuous assertion on the one option that
    // would silently make the guarded arm a materially stronger system is worse
    // than none: it manufactures confidence. Flagged, not silently fixed.
    //
    // Re-expressed as a source-text check — the same "read the file as inert
    // text" pattern the cross-language drift checks use (§8). It is what §8 said
    // this test was for: the option cannot be reintroduced without a reviewer
    // being asked why the guarded arm needs a second attempt the baseline cannot
    // have.
    const source = readFileSync(resolve(HERE, "../src/agents/guardedAgent.ts"), "utf-8");
    const uncommented = source
      .replace(/\/\*[\s\S]*?\*\//g, "")   // block comments (incl. the module docstring, which names it)
      .replace(/\/\/.*$/gm, "");          // line comments
    expect(uncommented).toContain("new Agent(");   // the check is looking at the real construction
    expect(uncommented).not.toContain("maxProcessorRetries");

    // Mastra's default with the option unset, from its own runner: "Processor
    // requested retry but maxProcessorRetries is not set. Treating as abort."
    // — exactly one draft per arm, no second chances on either side.
  });
});
