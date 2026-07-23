/**
 * §8 — the Mastra instance. `mastra dev` discovers this file and serves Studio on
 * :4111 from it; `scripts/demo.ts` and the eval harness resolve the same singleton.
 *
 * `import "dotenv/config"` is FIRST and is load-bearing: it must run before any module
 * that reads `process.env` at import time, and the model router reads `OPENAI_API_KEY`.
 * An import moved above it is a `.env` that silently does nothing.
 *
 * ── ALL THREE WORKFLOWS ARE REGISTERED, AND THAT IS A DECIDED TRADE-OFF (§12) ───
 * `deliveryWorkflow` and `stageBWorkflow` are eval targets, not the demo. They are
 * registered anyway because they MUST be: their steps resolve agents via
 * `mastra.getAgent(...)`, and Mastra supplies that instance THROUGH registration — an
 * unregistered workflow's step context has no `mastra` at all, so both eval targets
 * would throw on their first item and `npm test` (SC#6) could not run.
 *
 * The cost is real and is paid deliberately: Studio auto-discovers registered
 * workflows, so Mastra's team opens the playground and sees THREE workflows where the
 * north star describes one. The alternative — importing the agents directly into the
 * eval steps and skipping registration — was rejected on two grounds: it diverges from
 * `compareWorkflow`, which resolves agents through `mastra.getAgent`, leaving two
 * step-authoring conventions in one small template; and it rests on the unverified
 * belief that `runEvals` can execute a workflow object with no instance bound. A tidier
 * Studio list is not worth buying with an assumption.
 *
 * So the cost is paid down in NAMING instead of in wiring: each workflow's own
 * `description` says which one it is (`compare-workflow` is the demo; the other two say
 * "EVAL TARGET (npm test), not the demo" in their first clause, where Studio shows it),
 * and `template/README.md`'s Studio section names `compareWorkflow` as the one to run.
 * `mastra.test.ts::test_all_targets_are_registered` fails the moment a workflow is
 * added to `evals/` and forgotten here.
 */
import "dotenv/config";
import { Mastra } from "@mastra/core/mastra";
import { baselineAgent } from "./agents/baselineAgent";
import { guardedAgent } from "./agents/guardedAgent";
import { judgeAgent } from "./agents/judgeAgent";
import { deliveryWorkflow, stageBWorkflow } from "./evals/deliveryWorkflow";
import { compareWorkflow } from "./workflows/compareWorkflow";

/**
 * The KEYS are the lookup names — `getAgent(name)` reads `agents[name]`, not
 * `agent.id`. Every `mastra.getAgent("baselineAgent")` / `getWorkflow("compareWorkflow")`
 * call site in this template resolves against these keys, so they are a contract rather
 * than a label.
 *
 * `judgeAgent` is registered too, though nothing resolves it by name: `judge/callJudge.ts`
 * imports it directly (it is the guardrail's own machinery, not one of the two compared
 * arms). Registering it puts it in Studio, where a developer inspecting why a block
 * happened can read the verdict call's own traces — which is the question they will
 * actually have.
 */
export const mastra = new Mastra({
  agents: { baselineAgent, guardedAgent, judgeAgent },
  workflows: { compareWorkflow, deliveryWorkflow, stageBWorkflow },
});
