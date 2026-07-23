/**
 * P6.8 — goal #8's KNOWN RISK, resolved empirically.
 *
 * The goal says: *"Verify this in the first hour of the template stage; do not assume
 * either way."* So these cases drive a **REAL `@mastra/core` Agent** with a **REAL
 * output processor calling the REAL `abort()`**, and a **REAL `TripWire`** instance —
 * never a hand-rolled imitation of what we assume Mastra does. The only stub is the
 * language model, which is what keeps this free and offline (NO API CALLS).
 *
 * That distinction is the whole point: a test that mocks `abort()`'s behavior would
 * pass against our assumption and prove nothing about Mastra.
 */
import { describe, expect, test } from "vitest";
import { Agent } from "@mastra/core/agent";
import { TripWire } from "@mastra/core/agent";
import {
  isTripWireError,
  normalizeDelivery,
  type DeliveryCallResult,
} from "../src/processors/tripwireContainment.js";

const DRAFTED_TEXT = "Our fund guarantees a 12% annual return with no risk.";

/** A LanguageModelV2 that answers from memory. No network, no key, no cost. */
const stubModel = {
  specificationVersion: "v2",
  provider: "stub",
  modelId: "stub-model",
  supportedUrls: {},
  async doGenerate() {
    return {
      content: [{ type: "text", text: DRAFTED_TEXT }],
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
          controller.enqueue({
            type: "response-metadata",
            id: "1",
            modelId: "stub-model",
            timestamp: new Date(),
          });
          controller.enqueue({ type: "text-start", id: "t1" });
          controller.enqueue({ type: "text-delta", id: "t1", delta: DRAFTED_TEXT });
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

/** A REAL output processor that calls Mastra's REAL `abort()`, as §9c's will. */
const abortingProcessor = {
  id: "carver-guardrail",
  name: "carver-guardrail",
  async processOutputResult({ messages, abort }: any) {
    abort("Draft violates art-1003 (financial promotion must carry a risk warning)", {
      metadata: {
        blocked_draft: DRAFTED_TEXT,
        violated_obligation_ids: ["art-1003"],
      },
    });
    return messages;
  },
} as any;

/** A processor that fails the way BUGGY CODE fails — the case that must never be
 *  mistaken for a block. */
const crashingProcessor = {
  id: "crashing-processor",
  name: "crashing-processor",
  async processOutputResult() {
    throw new TypeError("genuine bug: cannot read properties of undefined");
  },
} as any;

const makeAgent = (name: string, outputProcessors: any[] = []) =>
  new Agent({
    id: name,
    name,
    instructions: "draft what is asked",
    model: stubModel,
    outputProcessors,
  });

describe("unit: normalizeDelivery — the block/error distinction", () => {
  test("a REAL tripwire abort is classified as a BLOCK, not an error", async () => {
    const agent = makeAgent("guardedStub", [abortingProcessor]);

    // If normalizeDelivery mis-contained this, it would REJECT here and fail the test.
    const outcome = await normalizeDelivery(() => agent.generate("draft a promo"));

    expect(outcome.tripped).toBe(true);
    if (!outcome.tripped) throw new Error("unreachable — narrowing for TS");
    expect(outcome.reason).toContain("art-1003");
    expect(outcome.processorId).toBe("carver-guardrail");
    // The metadata §10/§12 map from survives the containment intact.
    expect(outcome.metadata).toEqual({
      blocked_draft: DRAFTED_TEXT,
      violated_obligation_ids: ["art-1003"],
    });
  });

  test("a GENUINE exception is classified as an ERROR, not a block", async () => {
    const agent = makeAgent("crashingStub", [crashingProcessor]);

    // The catastrophic failure this module exists to prevent is this call RESOLVING to
    // {tripped: true} — a crash silently reported as a working guardrail.
    await expect(normalizeDelivery(() => agent.generate("draft a promo"))).rejects.toThrow(
      /genuine bug/,
    );
  });

  test("a clean call is DELIVERED — the outcome shape callers map from", async () => {
    const agent = makeAgent("baselineStub");

    const outcome = await normalizeDelivery(() => agent.generate("draft a promo"));

    expect(outcome).toEqual({ tripped: false, text: DRAFTED_TEXT });
  });

  test("a THROWN TripWire (layer 2) normalizes identically to the returned form", async () => {
    // Mastra's REAL TripWire, built exactly as its own abort() builds it:
    //   new TripWire(reason, options, processorId)
    const thrown = new TripWire(
      "Draft violates art-1003 (financial promotion must carry a risk warning)",
      { metadata: { blocked_draft: DRAFTED_TEXT, violated_obligation_ids: ["art-1003"] } },
      "carver-guardrail",
    );

    const returnedForm = await normalizeDelivery(async () => ({
      text: "",
      tripwire: {
        reason: thrown.message,
        metadata: thrown.options.metadata,
        processorId: thrown.processorId,
      },
    }));
    const thrownForm = await normalizeDelivery(async (): Promise<DeliveryCallResult> => {
      throw thrown;
    });

    // Neither caller can tell which form Mastra used — that is the containment.
    expect(thrownForm).toEqual(returnedForm);
    expect(thrownForm.tripped).toBe(true);
  });

  test("isTripWireError separates a real TripWire from a look-alike", () => {
    expect(isTripWireError(new TripWire("blocked", {}, "p1"))).toBe(true);
    expect(isTripWireError(new Error("blocked"))).toBe(false);
    // A duck-typed impostor is NOT a tripwire: misreading a crash as a block is the
    // silent-failure direction, so this check is instanceof-only by design.
    expect(isTripWireError({ reason: "blocked", processorId: "p1", metadata: {} })).toBe(false);
  });
});
