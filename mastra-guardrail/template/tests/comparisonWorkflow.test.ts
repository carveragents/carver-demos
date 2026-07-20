/**
 * `comparisonWorkflow.test.ts` — §10's containment proof and `guardedStep`'s
 * soundness battery (P6.11).
 *
 * ── NO REAL API CALLS, AND WHY THAT IS NOT A WEAKER TEST ────────────────────────
 * §10 pins this file's containment proof as a LIVE, billed run, excluded from
 * `test:unit` and deferred to Phase 7's preflight. This task's brief requires
 * `npm test` to stay green with no API calls, and `npm test` runs `vitest run` with
 * no exclusions — a billed test here would fail the suite on every machine without a
 * key. So the proof runs against a STUB LANGUAGE MODEL and everything else REAL: a
 * real `Mastra` instance, real registered agents, the real `CarverGuardrail` as a real
 * output processor, the real `compareWorkflow`, the real `.parallel()` engine, the
 * real `normalizeDelivery`.
 *
 * What that does and does not prove, stated plainly:
 *   • PROVED here — that Mastra contains `abort()` and returns rather than throws,
 *     that the tripwire never escapes `guardedStep`, that the run resolves "success"
 *     and not "tripwire", and that the metadata survives the round trip. Those are
 *     facts about MASTRA, and a stub model does not soften any of them.
 *   • NOT proved here — that the real pinned model, given a real prompt, drafts
 *     something that violates the trigger obligation. That is a fact about the MODEL,
 *     it is what a billed run buys, and it remains R7.0's job.
 * Flagged to the orchestrator rather than quietly substituted.
 */
import { describe, expect, test, vi } from "vitest";
import { Agent } from "@mastra/core/agent";
import { Mastra } from "@mastra/core/mastra";
import type {
  OutputProcessorOrWorkflow,
  Processor,
  ProcessOutputResultArgs,
} from "@mastra/core/processors";
import { RequestContext } from "@mastra/core/request-context";
import { SCENARIO_PERSONA_INSTRUCTIONS } from "../src/agents/baselineAgent";
import { judgeAgent } from "../src/agents/judgeAgent";
import { DEMO_TRIGGER_RECORD_ID } from "../src/config";
import { deliveryWorkflow, stageBWorkflow } from "../src/evals/deliveryWorkflow";
import { DEMO_FIRM_PROFILE, type FirmProfile } from "../src/firmProfile";
import { CarverGuardrail, type AuditEntry, type AuditWriter } from "../src/processors/carverGuardrail";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import { buildStageAPrompt } from "../src/scenario/prompts";
import { narrowObligationsPure } from "../src/tools/narrowObligations";
import { compareWorkflow } from "../src/workflows/compareWorkflow";
import { loadVendoredClearedSet } from "./fixtures";

const vendoredRecords: ClearedRecord[] = ClearedRecordSchema.array().parse(loadVendoredClearedSet());

/** The exact set the guardrail narrows to under the demo profile — the same
 *  computation `guardedStep` makes, so the battery below forges metadata against the
 *  real candidate list rather than an invented one. */
const candidateIds = narrowObligationsPure(DEMO_FIRM_PROFILE, vendoredRecords);
const triggerRecord = vendoredRecords.find(r => r.id === DEMO_TRIGGER_RECORD_ID)!;

/** Built the SAME mechanical way `scripts/demo.ts` builds it (§11) — from the vendored
 *  set plus the winner-derived trigger constant, never a hand-typed prompt string. */
const prompt = buildStageAPrompt(triggerRecord);

const STUB_DRAFT = "Our new AI ranking decides what you see. No disclosure needed — it just works.";

/** A LanguageModelV2 that answers from memory: no network, no key, no cost. The same
 *  stub `carverGuardrail.test.ts` uses, for the same reason — everything else is REAL. */
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

/**
 * `new RequestContext({ firmProfile })` — the form §8/§10/§11/§12 all pin — does NOT
 * compile: TS2353, the constructor takes an ENTRY-TUPLE iterable.
 *
 * AND THE ENTRY TUPLE IS NOT THE WHOLE STORY. D28 rules that
 * `new RequestContext<unknown>([["firmProfile", p]])` is "the one form that works at
 * every boundary". It is not — that is true only where the boundary is untyped.
 * `compareWorkflow` declares a `requestContextSchema`, which makes its `TRequestContext`
 * `{firmProfile: FirmProfile}`, and `run.start()` then takes
 * `RequestContext<{firmProfile: FirmProfile}>`; the `<unknown>` form is REJECTED there
 * (`keys()` yields `string`, not `"firmProfile"`). The two forms are each required
 * somewhere and neither works everywhere:
 *   • `RequestContext<{firmProfile}>` — a schema-bearing workflow's `run.start()`
 *   • `RequestContext<unknown>`       — the Agent accessors and `runEvals`' data items
 * Flagged to the orchestrator; D28's rule needs the qualification.
 */
const contextFor = (firmProfile: FirmProfile) =>
  new RequestContext<{ firmProfile: FirmProfile }>([["firmProfile", firmProfile]]);

/**
 * A REAL Mastra instance with the stub-model arms registered under the names
 * `compareWorkflow`'s steps resolve (`mastra.getAgent("baselineAgent"/"guardedAgent")`).
 *
 * ALL THREE workflows are registered, exactly as every `new Mastra(` in this project
 * must: the eval workflows' steps resolve their agents through `mastra.getAgent(...)`,
 * and Mastra supplies that instance THROUGH registration — an unregistered workflow's
 * step context has no `mastra` at all.
 */
function mastraWith(outputProcessor: OutputProcessorOrWorkflow) {
  return new Mastra({
    agents: {
      baselineAgent: new Agent({
        id: "baselineAgent",
        name: "baselineAgent",
        instructions: SCENARIO_PERSONA_INSTRUCTIONS,
        model: stubModel,
      }),
      guardedAgent: new Agent({
        id: "guardedAgent",
        name: "guardedAgent",
        instructions: SCENARIO_PERSONA_INSTRUCTIONS,
        model: stubModel,
        outputProcessors: [outputProcessor],
      }),
    },
    workflows: { compareWorkflow, deliveryWorkflow, stageBWorkflow },
    // The stub model's stderr is noisy enough; the point of these tests is the result
    // shape, not Mastra's logging.
    logger: false,
  });
}

/**
 * A processor that aborts with WHATEVER metadata a case wants, wearing the real
 * guardrail's id. It stands in for a Mastra that mis-propagated the metadata, or for a
 * future processor that builds it wrong — the cases `guardedStep`'s soundness checks
 * exist for, and which the real `CarverGuardrail` cannot produce.
 */
class ForgingProcessor implements Processor {
  readonly id = "carver-guardrail";
  constructor(private readonly metadata: unknown) {}
  async processOutputResult({ abort }: ProcessOutputResultArgs) {
    return abort("a forged block", { metadata: this.metadata });
  }
}

const runCompare = async (outputProcessor: OutputProcessorOrWorkflow) => {
  const run = await mastraWith(outputProcessor).getWorkflow("compareWorkflow").createRun();
  return run.start({ inputData: { prompt }, requestContext: contextFor(DEMO_FIRM_PROFILE) });
};

/** Every forged case shares the fields that are NOT under test, so each case differs in
 *  exactly the one thing it is about. */
const forgedMetadata = (overrides: Record<string, unknown>) => ({
  processorId: "carver-guardrail",
  blocked_draft: STUB_DRAFT,
  violated_obligation_ids: [candidateIds[0]],
  record: { id: candidateIds[0] },
  ...overrides,
});

const violationOf = (id: string) => ({
  obligation_id: id,
  applies_to_draft: true,
  omission_material: true,
  verdict: "violation",
  confidence: 0.95,
  rationale: `The draft omits ${id}'s key requirement.`,
});

/** Stubs the ONE judge seam. No network, no key, no cost. */
const stubJudge = (verdicts: unknown[]) =>
  vi.spyOn(judgeAgent, "generate").mockResolvedValue({ object: { verdicts } } as never);

describe("unit: guardedStep invariants", () => {
  // THE POINT OF THIS BATTERY. `guardedStep` recomputes the authoritative candidate set
  // itself rather than reading it out of the tripwire metadata — because metadata is the
  // thing being validated, and letting it vouch for its own legitimacy is circular. Each
  // case below is a way metadata could be wrong while still looking plausible.
  //
  // A soundness failure surfaces as a FAILED run carrying the named error: that is the
  // designed behaviour. It is the one case where the red text is real — the guardrail
  // fired but cannot say what it fired on, which is a bug to surface, not a block to
  // render.
  const expectUnsound = async (metadata: unknown, fragment: RegExp) => {
    const result = await runCompare(new ForgingProcessor(metadata));
    expect(result.status).toBe("failed");
    if (result.status !== "failed") throw new Error("unreachable — narrowing for TS");
    expect(result.error.message).toMatch(/metadata is unsound/);
    expect(result.error.message).toMatch(fragment);
  };

  test("test_incomplete_metadata_fails_loudly: a block with no blocked_draft is refused", async () => {
    // §11's report cannot function without it, and a block that silently carried
    // `blocked_draft: null` would render as an empty panel where the demo's whole
    // point — "here is the draft that was stopped" — should be.
    await expectUnsound(forgedMetadata({ blocked_draft: undefined }), /blocked_draft is undefined/);
  });

  test("a duplicate obligation id is refused", async () => {
    // §4's parseAndValidateVerdicts returns exactly one verdict per id, so a duplicate
    // here means the metadata did not come from that code path.
    await expectUnsound(
      forgedMetadata({ violated_obligation_ids: [candidateIds[0], candidateIds[0]] }),
      /duplicate obligation ids/,
    );
  });

  test("an id that is not a vendored record at all is refused", async () => {
    await expectUnsound(
      forgedMetadata({ violated_obligation_ids: ["art-9999"], record: { id: "art-9999" } }),
      /not among this call's narrowed candidates: art-9999/,
    );
  });

  test("test_known_but_not_narrowed_id_rejected: a REAL record that this call never narrowed to", async () => {
    // THE case the weaker check would miss. `art-1006` is a genuine vendored record —
    // "is it real?" says yes. But it is not among THIS call's narrowed candidates, so
    // the judge was never asked about it, and a report citing it would name an
    // obligation the guardrail never considered. Membership in candidateIds, not
    // existence in the set, is the property that makes the citation honest.
    const knownButNotNarrowed = vendoredRecords.find(r => !candidateIds.includes(r.id))!;
    expect(knownButNotNarrowed).toBeDefined();   // the fixture must actually contain one
    await expectUnsound(
      forgedMetadata({
        violated_obligation_ids: [knownButNotNarrowed.id],
        record: { id: knownButNotNarrowed.id },
      }),
      new RegExp(`not among this call's narrowed candidates: ${knownButNotNarrowed.id}`),
    );
  });

  test("ids out of narrowing-rank order are refused", async () => {
    // §9c builds the array by filtering verdicts that are themselves in candidateIds
    // order, so any other order means the metadata did not come from it. This is what
    // makes "…[0] is the highest-ranked violated obligation" — relied on by the audit
    // entry, the report and the scorer — a checked fact rather than a comment.
    await expectUnsound(
      forgedMetadata({ violated_obligation_ids: [candidateIds[1], candidateIds[0]] }),
      /not in narrowing-rank order/,
    );
  });

  test("test_forged_record_metadata_is_ignored: the display record is DERIVED, never copied", async () => {
    // Validating metadata's record field-by-field would only catch a forgery by
    // comparing every one of them. Deriving from the vendored set makes forgery
    // unrepresentable — there is no field to forge.
    const real = vendoredRecords.find(r => r.id === candidateIds[0])!;
    const result = await runCompare(new ForgingProcessor(forgedMetadata({
      record: {
        id: candidateIds[0],
        title: "FORGED TITLE",
        regulator_name: "FORGED REGULATOR",
        citation: { name: "FORGED", url: "https://evil.example/forged" },
        compliance_date: "1999-01-01",
      },
    })));

    expect(result.status).toBe("success");
    if (result.status !== "success") throw new Error("unreachable — narrowing for TS");
    const { guarded } = result.result;
    expect(guarded.blocked).toBe(true);
    if (!guarded.blocked) throw new Error("unreachable — narrowing for TS");
    expect(guarded.record.title).toBe(real.title);
    expect(guarded.record.regulator_name).toBe(real.regulator_name);
    expect(guarded.record.citation).toEqual(real.citation);
    expect(guarded.record.title).not.toBe("FORGED TITLE");
  });
});

describe("unit: compareWorkflow presents a block as a BLOCK, not an error", () => {
  test("guarded branch tripwire never ends the workflow run", async () => {
    // §10's containment proof, run against the REAL CarverGuardrail through the REAL
    // Mastra machinery. Only the language model is stubbed (see this file's header).
    //
    // Watch stderr while this runs: Mastra prints `[WORKFLOW] Error executing step …`
    // plus a stack trace, because that is how it reports its own internal `abort()`.
    // THE GUARDRAIL WORKING CORRECTLY LOOKS LIKE A CRASH. Every assertion below is
    // about the thing a viewer actually reads — and every one of them says BLOCK.
    const writer = new FakeAuditWriter();
    stubJudge([violationOf(candidateIds[0])]);

    const result = await runCompare(new CarverGuardrail(writer));

    expect(result.status).toBe("success");            // NOT "tripwire" — the core assertion
    if (result.status !== "success") throw new Error("unreachable — narrowing for TS");

    // THE HEADLINE (D28.5). Top-level, first key, no schema needed to read it.
    expect(result.result.outcome).toBe("BLOCKED");

    const { guarded } = result.result;
    expect(guarded.blocked).toBe(true);
    if (!guarded.blocked) throw new Error("unreachable — narrowing for TS");
    expect(guarded.blocked_draft).toBe(STUB_DRAFT);   // the real underlying draft, not a placeholder
    expect(guarded.reason.length).toBeGreaterThan(0);
    expect(guarded.processorId).toBe("carver-guardrail");
    // MEMBERSHIP, matching §12's scorer: asserting `record.id === candidateIds[0]`
    // directly would fail whenever the draft also violated a higher-ranked narrowed
    // obligation — a correct, STRONGER block scored as a bug.
    expect(guarded.violated_obligation_ids).toContain(candidateIds[0]);
    expect(guarded.record.id).toBe(guarded.violated_obligation_ids[0]);

    // The baseline branch completed independently: .parallel() isolates step execution,
    // so whatever happens in the guarded arm cannot touch it. This is the "side by side"
    // the demo claims.
    expect(result.result.baseline.text).toBe(STUB_DRAFT);
    expect(writer.entries).toMatchObject([{ action: "aborted", obligationId: candidateIds[0] }]);
  });

  test("a draft the judge finds compliant is DELIVERED, and says so", async () => {
    // The other arm of the discriminated union, and the reason `outcome` is not simply
    // hard-coded: the guardrail is only interesting if it can also NOT fire.
    stubJudge([]);

    const result = await runCompare(new CarverGuardrail(new FakeAuditWriter()));

    expect(result.status).toBe("success");
    if (result.status !== "success") throw new Error("unreachable — narrowing for TS");
    expect(result.result.outcome).toBe("DELIVERED");
    expect(result.result.guarded.blocked).toBe(false);
    expect(result.result.guarded.text).toBe(STUB_DRAFT);
    expect(result.result.guarded.violated_obligation_ids).toEqual([]);
  });

  test("a run that forgets the firm profile fails AT THE BOUNDARY, not deep inside a step", async () => {
    // What `requestContextSchema` buys: the round-4 defect was a call site that never
    // passed a profile, which turned a wiring omission into a stack trace mid-step. Now
    // it is a named schema error at run.start(), before either agent is called.
    const run = await mastraWith(new CarverGuardrail(new FakeAuditWriter()))
      .getWorkflow("compareWorkflow").createRun();
    // Mastra REJECTS rather than resolving `status: "failed"` — the schema is checked
    // before the run is entered at all, so there is no run to report a status for. That
    // is the stronger form of what §10 asks for, and worth pinning: it is the one error
    // path here that is genuinely an error, and it names the missing key.
    await expect(run.start({ inputData: { prompt } }))
      .rejects.toThrow(/Request context validation failed[\s\S]*firmProfile/);
  });
});
