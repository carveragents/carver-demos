/**
 * The GUARDED arm — `baselineAgent`, plus the Carver guardrail. Nothing else
 * (spec §8).
 *
 * THAT IS THE ENTIRE EXPERIMENT (goal #9). The two arms must differ ONLY in
 * whether Carver data gates the output; if they also differed in model,
 * instructions, output cap or reasoning effort, the scoreboard would be
 * measuring a configuration difference and reporting it as the guardrail
 * working — and, as goal #9 warns about exactly this class of error, it would
 * LOOK LIKE SUCCESS. So both arms spread the SAME object (`SHARED_AGENT_CONFIG`
 * — one binding, not three fields that happen to agree), and
 * `carverGuardrail.test.ts` asserts the two resolve identically rather than
 * trusting inspection.
 *
 * NO `maxProcessorRetries` (§8). Mastra's default is no processor retries, and
 * that is deliberate: a retry that re-generated this arm's draft would hand it a
 * second chance the baseline structurally cannot have (the baseline has no
 * processor to retry, so the option is unequalisable). Exactly one draft each,
 * no second chances on either side. Verified in @mastra/core 1.51.0's own
 * runner: `maxProcessorRetries === undefined` -> *"Processor requested retry but
 * maxProcessorRetries is not set. Treating as abort."* Every failure mode the
 * option was implicitly covering is handled where it belongs — a malformed or
 * failed judge retries the VERDICT inside `judge/callJudge.ts`, never the draft.
 *
 * `SHARED_AGENT_CONFIG` is imported from `agents/sharedConfig.ts`, §8's public
 * home for it. (It is DECLARED in `baselineAgent.ts`, beside the generated
 * persona it closes over, and re-exported there — orchestrator D27: the
 * specified arrangement is a mandatory import cycle that TDZ-`ReferenceError`s
 * in both evaluation orders. The import site, the object's shape and the
 * one-object guarantee are exactly as specified.)
 */
import { Agent } from "@mastra/core/agent";
import { CarverGuardrail } from "../processors/carverGuardrail";
import { SHARED_AGENT_CONFIG } from "./sharedConfig";

export const guardedAgent = new Agent({
  id: "guarded-agent",
  name: "Guarded Assistant",
  ...SHARED_AGENT_CONFIG,                      // the SAME object baselineAgent spreads
  outputProcessors: [new CarverGuardrail()],   // THE ONLY DIFFERENCE between the two arms
  // NO maxProcessorRetries — see the note above. Do not add one.
});
