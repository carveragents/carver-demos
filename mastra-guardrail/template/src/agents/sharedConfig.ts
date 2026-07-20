/**
 * `SHARED_AGENT_CONFIG` — the ONE object `baselineAgent` and `guardedAgent` are
 * both constructed from (spec §8), and this module is where every consumer
 * imports it from.
 *
 * WHY IT EXISTS. The two arms must differ ONLY in whether Carver data gates
 * their output. If they drifted in model, output cap or reasoning effort, the
 * scoreboard would be measuring a configuration difference and reporting it as
 * the guardrail working — goal #9's fatal case, in the direction that looks like
 * success. One object makes that drift structurally impossible rather than
 * merely discouraged: there is nothing for a future edit to update on one side
 * and forget on the other.
 *
 * WHY IT IS ONLY RE-EXPORTED HERE — a forced structure, and a SPEC DEFECT worth
 * an orchestrator ruling rather than a silent fix. §8 declares this object in
 * `agents/sharedConfig.ts` with `instructions: SCENARIO_PERSONA_INSTRUCTIONS`,
 * while §7 step 8 + P6.2 pin that generated constant to `agents/baselineAgent.ts`
 * — and §8 also has `baselineAgent` spread this object. Those three cannot all
 * hold:
 *
 *   - a module that reads the persona at evaluation time must evaluate AFTER
 *     `baselineAgent.ts`'s body;
 *   - a module `baselineAgent.ts` imports evaluates BEFORE its body;
 *   - so `baselineAgent.ts` importing a persona-reading `sharedConfig.ts` is an
 *     import cycle, and in BOTH evaluation orders the second module reads the
 *     first's uninitialised `const` — a TDZ `ReferenceError` at import, not a
 *     subtle bug. (`sharedConfig` first: `baselineAgent`'s body runs while
 *     `SHARED_AGENT_CONFIG` is still in its TDZ. `baselineAgent` first:
 *     `sharedConfig`'s body runs while the persona is still in ITS TDZ.)
 *
 * The object is therefore DECLARED beside the constant it closes over, and this
 * module keeps the public import site §8 specifies, so the shape every consumer
 * and test sees is exactly the specified one. The real fix is a one-line choice
 * the orchestrator owns: have the generator write the persona into THIS module,
 * or home the declaration in `baselineAgent.ts` in §1's module table. Either
 * way, the guarantee — one object, spread by both arms — is preserved as-is
 * today.
 */
export { SHARED_AGENT_CONFIG } from "./baselineAgent";
