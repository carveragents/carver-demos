/**
 * §12 — the eval transport. ONE agent call per run, normalized to a typed result.
 *
 * WHY THIS EXISTS AT ALL. `runEvals` hands an AGENT scorer
 * `targetResult.scoringData.output` — the persisted response-message array
 * (`MastraDBMessage[]`). `tripwire`, `text` and `object` live on the full generate
 * result, which an agent scorer never sees. So "was this draft blocked?" — the one
 * question the whole scoreboard turns on — is INVISIBLE to an agent scorer. A
 * WORKFLOW scorer, by contrast, receives the workflow's own output. These two
 * one-step workflows exist solely to make the delivery decision and the structured
 * Stage B answer into workflow outputs a scorer can read.
 *
 * This module imports NO agent (§8). `deliveryStep` resolves its arm through
 * `mastra.getAgent(...)` at run time, which is what makes the paired population
 * structural: both arms are the SAME registered agents the template ships, not
 * eval-only clones.
 */
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";
import { FirmProfileSchema } from "../firmProfile";
import { normalizeDelivery } from "../processors/tripwireContainment";
import { StageBResponseSchema } from "../schema";

export const DeliveryInputSchema = z.object({
  prompt: z.string(),
  arm: z.enum(["baseline", "guarded"]),
  /**
   * The ground truth travels HERE, in the workflow's own input — NOT via runEvals'
   * `groundTruth` data-item field. A scorer's `run` object carries `runId`, `input`,
   * `output` and `requestContext`, and `groundTruth` is not among the fields the
   * reference documents for it. `run.input` IS documented and IS this workflow's own
   * input, so the record id rides there and the scorer resolves it against the
   * vendored set it already imports.
   *
   * Null for negative controls, which have no ground-truth record by construction.
   */
  recordId: z.string().nullable(),
});

// NOTE: no `DeliveryInput` type is exported here. `evals/scorers.ts` infers its own
// from `DeliveryInputSchema` (§12), which is the value this module exports.

export const DeliveryResultSchema = z.discriminatedUnion("blocked", [
  z.object({
    blocked: z.literal(true),
    delivered_text: z.null(),
    violated_obligation_ids: z.array(z.string()).min(1),
  }),
  z.object({
    blocked: z.literal(false),
    delivered_text: z.string(),
    violated_obligation_ids: z.array(z.string()).length(0),
  }),
]);

export type DeliveryResult = z.infer<typeof DeliveryResultSchema>;

const deliveryStep = createStep({
  id: "delivery",
  description: "One agent call on the named arm, normalized to a blocked/delivered decision.",
  inputSchema: DeliveryInputSchema,
  outputSchema: DeliveryResultSchema,
  execute: async ({ inputData, mastra, requestContext }): Promise<DeliveryResult> => {
    // The SAME registered agents the template ships — not eval-only clones. `arm`
    // selects which; everything else about the call is identical, which is what makes
    // the paired population structural rather than a claim two functions have to agree
    // on.
    const agent = mastra.getAgent(inputData.arm === "baseline" ? "baselineAgent" : "guardedAgent");

    // Contains nothing itself (D26): `normalizeDelivery` answers the return-vs-throw
    // question once, in one place, and this step MAPS its outcome. It cannot return a
    // DeliveryResult directly — `guardedStep` (§10) needs a richer shape from the same
    // call, and no single return type expresses both.
    const outcome = await normalizeDelivery(() => agent.generate(inputData.prompt, { requestContext }));
    if (!outcome.tripped) {
      return { blocked: false, delivered_text: outcome.text, violated_obligation_ids: [] };
    }

    const violatedIds = (outcome.metadata as { violated_obligation_ids?: unknown } | undefined)
      ?.violated_obligation_ids;
    if (!Array.isArray(violatedIds) || violatedIds.length === 0) {
      // Same standard as §10's buildBlockedResult: a tripwire whose metadata cannot say
      // WHAT it fired on is not a result to score, it is a bug to surface. Never a
      // silent empty array — that would read as "blocked on nothing" and score as a
      // miss.
      throw new Error(`CarverGuardrail tripwire fired but violated_obligation_ids is `
        + `${JSON.stringify(violatedIds)} — refusing to build a delivery result the scorers `
        + `would silently mis-attribute`);
    }
    return { blocked: true, delivered_text: null, violated_obligation_ids: violatedIds as string[] };
  },
});

export const deliveryWorkflow = createWorkflow({
  id: "delivery-workflow",
  description: "EVAL TARGET (npm test), not the demo — run `compareWorkflow` in Studio instead. "
    + "One agent call on a named arm, normalized to a blocked/delivered decision.",
  inputSchema: DeliveryInputSchema,
  requestContextSchema: z.object({ firmProfile: FirmProfileSchema }),   // §10's contract, same reason
  outputSchema: DeliveryResultSchema,
})
  .then(deliveryStep)
  .commit();

const StageBInputSchema = z.object({ prompt: z.string(), recordId: z.string() });

/**
 * Stage B asks a KNOWLEDGE question and needs the structured answer, not a delivery
 * decision — so it gets its own thin workflow for the same reason the others do:
 * `.object` lives on the generate result, which an agent scorer cannot see either.
 * `targetOptions` WOULD forward `structuredOutput` to `agent.generate()`, but the
 * resulting `.object` still lands on the generate result: same wall, one step later.
 */
const stageBStep = createStep({
  id: "stage-b",
  description: "One structured knowledge call on the baseline arm: what source, what deadline?",
  inputSchema: StageBInputSchema,
  outputSchema: StageBResponseSchema,
  execute: async ({ inputData, mastra }) => {
    // `{ structuredOutput: { schema } }`, NOT §8/§4's `{ output: schema }` — the latter
    // is TS2769 against the pinned @mastra/core (it survives only on the legacy
    // AgentGenerateOptions). Flagged, not silently fixed.
    const result = await mastra.getAgent("baselineAgent").generate(inputData.prompt, {
      structuredOutput: { schema: StageBResponseSchema },
    });
    return result.object;
  },
});

export const stageBWorkflow = createWorkflow({
  id: "stage-b-workflow",
  description: "EVAL TARGET (npm test), not the demo — run `compareWorkflow` in Studio instead. "
    + "One structured Stage B knowledge call on the baseline arm.",
  inputSchema: StageBInputSchema,
  outputSchema: StageBResponseSchema,
})
  .then(stageBStep)
  .commit();
