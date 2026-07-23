/**
 * §11 — `npm run demo`. Runs the REAL `compareWorkflow` against the real model and
 * writes `output/demo-report.html` from that run's own output.
 *
 * The prompt is built the SAME mechanical way `comparisonWorkflow.test.ts` builds it:
 * `buildStageAPrompt(clearedSet.find(r => r.id === DEMO_TRIGGER_RECORD_ID))` — an
 * expression over the vendored cleared set and the generated scenario templates, never
 * a hand-typed string. That is what makes the demo ask the same question the evidence
 * in `data/cleared/` was recorded for.
 *
 * ── THIS SCRIPT'S CONSOLE IS PART OF THE DEMO SURFACE (orchestrator D28.5) ──────
 * Mastra runs output processors inside a workflow, so a correct `abort()` — the
 * guardrail working — prints `[WORKFLOW] Error executing step …` plus a stack trace to
 * stderr. Suppressing Mastra's own stderr is not this script's business; making sure it
 * is not the demo's headline IS. So the banner below warns before the run, and the
 * outcome is restated afterwards, in the last thing printed, in the terms the demo is
 * actually about.
 *
 * ── EXIT CODES ─────────────────────────────────────────────────────────────────
 *   0  the guardrail blocked; the report was written
 *   1  infrastructure broke — the run did not reach `success`
 *   2  the run worked and the guardrail declined to block. NOT a crash: §12's live
 *      catch-rate bar is `>= 0.9`, not 1.0, so this is an expected minority outcome.
 *      Distinct from 1 so a wrapper can tell the two apart.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { RequestContext } from "@mastra/core/request-context";
import { DEMO_TRIGGER_RECORD_ID } from "../src/config";
import { DEMO_FIRM_PROFILE, type FirmProfile } from "../src/firmProfile";
import { mastra } from "../src/mastra";
import { generateHtmlReport } from "../src/report/generateHtmlReport";
import { buildStageAPrompt } from "../src/scenario/prompts";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import clearedSetJson from "../src/data/cleared-set.json";

/** No module exports the vendored set (§8) — every consumer reads the JSON and parses
 *  it with the schema, so a drifted file fails loudly at import in each of them. */
const vendoredClearedSet: ClearedRecord[] = ClearedRecordSchema.array().parse(clearedSetJson);

/** Resolved from THIS module, not from `process.cwd()`: `npm run demo` sets the cwd to
 *  the package root and the two agree, but `tsx template/scripts/demo.ts` from anywhere
 *  else would otherwise scatter the artifact wherever it was invoked from. §11's
 *  `template/output/demo-report.html` either way. */
const OUTPUT_PATH = resolve(dirname(fileURLToPath(import.meta.url)), "../output/demo-report.html");

async function main(): Promise<void> {
  const record = vendoredClearedSet.find(r => r.id === DEMO_TRIGGER_RECORD_ID);
  if (!record) {
    throw new Error(`DEMO_TRIGGER_RECORD_ID "${DEMO_TRIGGER_RECORD_ID}" is not in the vendored `
      + `cleared set — config.ts's generated constant and src/data/cleared-set.json have drifted `
      + `apart, and the demo would run against a record that does not exist`);
  }
  const prompt = buildStageAPrompt(record);

  console.log(
    `\n  Carver × Mastra — the same agent, with and without Carver's data.\n`
    + `  Drafting the same task on both arms. One has Carver's cleared set gating its output.\n\n`
    + `  NOTE: if the guardrail fires you will see a red "[WORKFLOW] Error executing step …"\n`
    + `  and a stack trace below. THAT IS THE GUARDRAIL WORKING — Mastra runs output\n`
    + `  processors inside a workflow, so its own abort() surfaces that way. The verdict is\n`
    + `  the last line printed, and the report is the artifact.\n`,
  );

  const run = await mastra.getWorkflow("compareWorkflow").createRun();
  const result = await run.start({
    inputData: { prompt },
    // The TYPED form: `compareWorkflow` declares a `requestContextSchema`, so
    // `run.start()` requires `RequestContext<{firmProfile: FirmProfile}>` and rejects
    // the `<unknown>` form (orchestrator D29.1). §11's `new RequestContext({ firmProfile })`
    // does not compile at all — TS2353, the constructor takes an entry-tuple iterable.
    requestContext: new RequestContext<{ firmProfile: FirmProfile }>([["firmProfile", DEMO_FIRM_PROFILE]]),
  });

  if (result.status !== "success") {
    // §10 proves this cannot be "tripwire": the tripwire is contained inside guardedStep
    // and never propagates out of a step. So reaching here means something genuinely broke.
    console.error(`\n  workflow run ended "${result.status}", expected "success" — see the trace in `
      + `Studio (npm run dev). No report written.`);
    process.exit(1);
  }

  if (!result.result.guarded.blocked) {
    // A real, correct, reportable outcome — not a crash.
    console.error(
      `\n  The guarded agent did not block on trigger record ${DEMO_TRIGGER_RECORD_ID}.\n`
      + `  This is an expected minority outcome (npm test's live catch rate bar is >= 0.9, not\n`
      + `  1.0) and NOT a bug on its own. No report was written — a demo report is only ever\n`
      + `  generated from a run that really blocked (§11).\n`
      + `  Re-run to resample; if it recurs, run \`npm test\` for the full scoreboard, which\n`
      + `  measures the catch rate across the whole scored population rather than this one\n`
      + `  record.`);
    process.exit(2);   // distinct from 1: "the run worked, the guardrail declined to block"
  }

  mkdirSync(dirname(OUTPUT_PATH), { recursive: true });
  writeFileSync(OUTPUT_PATH, generateHtmlReport(result.result));

  // THE LAST THING PRINTED. Mastra's stack trace is above; this is the verdict.
  const { record: fired } = result.result.guarded;
  console.log(
    `\n  OUTCOME: ${result.result.outcome} — the designed outcome. The guardrail fired.\n`
    + `  Obligation: ${fired.title}\n`
    + `  Regulator:  ${fired.regulator_name}\n`
    + `  Compliance: ${fired.compliance_date ?? "none recorded"}\n`
    + `  Citation:   ${fired.citation.url}\n\n`
    + `  wrote ${OUTPUT_PATH}\n`
    + `  Open it in a browser — no server, no network.\n`,
  );
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
