/**
 * `mastra.test.ts` — §8/§12's registration contract (P6.14).
 *
 * ALL THREE WORKFLOWS MUST BE REGISTERED OR `npm test` CANNOT RUN AT ALL. The eval
 * workflows' steps resolve their arms through `mastra.getAgent(...)`, and Mastra
 * supplies that instance THROUGH registration — an unregistered workflow's step context
 * has no `mastra`, so both eval targets would throw on their first item. This file
 * fails the moment a workflow is added to `evals/` and forgotten in `src/mastra.ts`,
 * which is the whole of that defect.
 *
 * ── NO REAL API CALLS ───────────────────────────────────────────────────────────
 * The `src/mastra.ts` under test here is the REAL one: the real agents, pinned to the
 * real router string, and the real registered workflow singletons. Only the ONE seam
 * that would spend money — `agent.generate` — is stubbed, and it is stubbed on the real
 * registered agent objects, so a step that failed to resolve them through
 * `mastra.getAgent(...)` would not reach the stub and the test would fail. Constructing
 * an `Agent` with a router string makes no network call and needs no key, so this file
 * passes with `OPENAI_API_KEY` unset.
 */
import { afterEach, describe, expect, test, vi } from "vitest";
import { RequestContext } from "@mastra/core/request-context";
import { baselineAgent } from "../src/agents/baselineAgent";
import { guardedAgent } from "../src/agents/guardedAgent";
import { DEMO_FIRM_PROFILE, type FirmProfile } from "../src/firmProfile";
import { mastra } from "../src/mastra";

const STUB_DRAFT = "A draft that never left this process.";

/** §10/§12's contract: a schema-bearing workflow's `run.start()` takes the TYPED form
 *  (orchestrator D29.1 — the `<unknown>` form is rejected there). */
const contextFor = (firmProfile: FirmProfile) =>
  new RequestContext<{ firmProfile: FirmProfile }>([["firmProfile", firmProfile]]);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("unit: mastra registration", () => {
  test("test_all_targets_are_registered: all three workflows and all three agents resolve", () => {
    // The DEMO plus the two eval targets. §12 decided to register all three and
    // disambiguate in naming rather than hide the eval targets from Studio — so the
    // check is that all three resolve, and that their descriptions say which is which.
    expect(mastra.getWorkflow("compareWorkflow")).toBeDefined();
    expect(mastra.getWorkflow("deliveryWorkflow")).toBeDefined();
    expect(mastra.getWorkflow("stageBWorkflow")).toBeDefined();

    // Resolution is by REGISTRATION KEY (`getAgent(name)` reads `agents[name]`), not by
    // `agent.id` — every `mastra.getAgent("baselineAgent")` in the eval steps and in
    // compareWorkflow depends on these exact keys.
    expect(mastra.getAgent("baselineAgent")).toBe(baselineAgent);
    expect(mastra.getAgent("guardedAgent")).toBe(guardedAgent);
    expect(mastra.getAgent("judgeAgent")).toBeDefined();

    // The Studio-clutter cost of registering the eval targets is paid down in naming:
    // a developer opening the playground must be able to tell the demo from the two
    // targets without reading this file.
    expect(mastra.getWorkflow("deliveryWorkflow").description).toMatch(/EVAL TARGET/);
    expect(mastra.getWorkflow("stageBWorkflow").description).toMatch(/EVAL TARGET/);
    expect(mastra.getWorkflow("compareWorkflow").description).toMatch(/THE DEMO/);
  });

  test("deliveryWorkflow's step reaches mastra.getAgent(\"baselineAgent\") through registration", async () => {
    // The property that actually matters, driven rather than inspected: the step body
    // calls `mastra.getAgent("baselineAgent")` on the instance MASTRA injects, and an
    // unregistered workflow's step context has no `mastra` at all. Stubbing the real
    // registered agent's `generate` and watching it get called proves the whole path —
    // registration, injection, lookup by key — with no API call.
    const generate = vi.spyOn(baselineAgent, "generate")
      .mockResolvedValue({ text: STUB_DRAFT } as never);

    const run = await mastra.getWorkflow("deliveryWorkflow").createRun();
    const result = await run.start({
      inputData: { prompt: "Draft the launch announcement", arm: "baseline", recordId: "art-1003" },
      requestContext: contextFor(DEMO_FIRM_PROFILE),
    });

    expect(generate).toHaveBeenCalledOnce();
    expect(result.status).toBe("success");
    if (result.status !== "success") throw new Error("unreachable — narrowing for TS");
    expect(result.result).toEqual({
      blocked: false, delivered_text: STUB_DRAFT, violated_obligation_ids: [],
    });
  });

  test("stageBWorkflow's step reaches mastra.getAgent(\"baselineAgent\") through registration", async () => {
    // The second eval target, through the same registration. Its step asks for a
    // STRUCTURED answer, so the stub returns `.object` — the field the step reads.
    const answer = {
      knows_source: true,
      source_name: "A regulation the model believes exists",
      source_url: "https://example.invalid/does-not-matter-here",
      compliance_date: "2026-09-01",
      confidence_note: "stubbed",
    };
    const generate = vi.spyOn(baselineAgent, "generate")
      .mockResolvedValue({ object: answer } as never);

    const run = await mastra.getWorkflow("stageBWorkflow").createRun();
    const result = await run.start({
      inputData: { prompt: "What is the deadline?", recordId: "art-1003" },
    });

    expect(generate).toHaveBeenCalledOnce();
    expect(result.status).toBe("success");
    if (result.status !== "success") throw new Error("unreachable — narrowing for TS");
    expect(result.result).toEqual(answer);
  });
});
