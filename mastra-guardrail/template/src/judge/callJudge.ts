/**
 * The ONE judge call path (spec §8) — the only place `judgeAgent` is ever
 * invoked, and the single implementation of §4's retry-once-then-all-uncertain
 * degradation.
 *
 * WHY ONE MODULE. `evals/scorers.ts`'s Stage A scorer and
 * `processors/carverGuardrail.ts`'s verdict stage (§9b) must do the identical
 * thing: render §4's prompt, call `judgeAgent`, and degrade through §4's
 * six-step contract when the response is malformed or carries an out-of-range
 * confidence. Specifying that twice is exactly the drift §4's shared-algorithm
 * discipline exists to prevent — so the Stage A eval and runtime enforcement
 * follow the same contract by construction, not because two implementations
 * happen to agree.
 *
 * Imports `contract.ts` (prompt/schema/parsing) and `agents/judgeAgent.ts` (the
 * agent). Nothing imports it back — §8's DAG.
 */
import {
  GuardrailVerdictSchema,
  parseAndValidateVerdicts,
  renderJudgeUserPrompt,
  type JudgeObligationInput,
  type JudgeResult,
} from "./contract";
import { judgeAgent } from "../agents/judgeAgent";

export async function runJudge(obligations: JudgeObligationInput[], draftText: string): Promise<JudgeResult> {
  const prompt = renderJudgeUserPrompt(obligations, draftText);
  const requestedIds = obligations.map(o => o.id);

  // judgeAgent, NEVER baselineAgent/guardedAgent: guardedAgent carries
  // CarverGuardrail as an outputProcessor, so calling it from inside
  // processOutputResult() would recursively re-invoke the processor on the
  // verdict call's own output (§8).
  const once = async (): Promise<string> => {
    const response = await judgeAgent.generate(prompt, {
      structuredOutput: { schema: GuardrailVerdictSchema },
    });
    return JSON.stringify(response.object);
  };

  let raw: string;
  try {
    raw = await once();
  } catch {
    // Mastra surfaces malformed JSON, a missing field, AND an out-of-range
    // confidence (rejected by GuardrailVerdictSchema's .min(0).max(1), §4)
    // identically: as a THROW from generate(), never an inspectable value. §4
    // step 1's semantics apply to all three — retry ONCE with the same input,
    // then fall back to all-uncertain. The bound and this degradation were
    // specified together, on purpose: one without the other would trade an
    // unbounded value for an unhandled exception.
    try {
      raw = await once();
    } catch {
      raw = "";   // unparseable by construction -> §4 step 4's fallback for EVERY requestedId
    }
  }

  // §4's six steps, including the [0, 1] enforcement. A judge that cannot answer
  // yields "uncertain", which fails §9c's conjunction — so it never blocks, and
  // it never fabricates a violation.
  return parseAndValidateVerdicts(raw, requestedIds);
}
