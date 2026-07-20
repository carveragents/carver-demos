/**
 * The third, internal-only agent (spec §8) — never one of the two compared
 * experiment branches.
 *
 * WHY IT MUST EXIST. The guardrail's verdict stage (§9b) and the eval harness's
 * Stage A scorer (§12) both run §4's Judge/Verdict prompt. Neither may run it
 * through `guardedAgent`: `guardedAgent` carries `CarverGuardrail` as an
 * `outputProcessor`, so calling it from INSIDE `processOutputResult()` would
 * recursively re-invoke the processor on the verdict call's own output — and the
 * verdict call is the guardrail's own machinery, not a business generation whose
 * output should itself be checked for compliance. This agent has NO
 * `outputProcessors` and NO business persona.
 *
 * It shares `MODEL_ID` (§9's controlled-experiment requirement is about the two
 * BUSINESS generations, not this internal one) and `GENERATION_CONFIG`: it is
 * the same model answering the same question prep's `run_judge` asks, so it must
 * reason at the same effort — otherwise the template's verdicts and prep's would
 * come from differently-configured judges.
 *
 * Imports `JUDGE_SYSTEM_PROMPT` from `judge/contract.ts` — NEVER from
 * `evals/scorers.ts`, which itself depends on this module (§8's dependency-cycle
 * note). It is invoked from exactly one place: `judge/callJudge.ts`.
 */
import { Agent } from "@mastra/core/agent";
import { GENERATION_CONFIG, MODEL_ID } from "../config";
import { JUDGE_SYSTEM_PROMPT } from "../judge/contract";

export const judgeAgent = new Agent({
  id: "judge-agent",
  name: "Obligation Judge",
  instructions: JUDGE_SYSTEM_PROMPT,   // the shared prompt, §4 — NOT the business persona
  model: MODEL_ID,
  defaultOptions: GENERATION_CONFIG,   // same effort as prep's run_judge (§3/§4)
});
