/**
 * §11 — `npm run demo:prompt`. Prints the demo's Stage A prompt to stdout and nothing
 * else, so it can be piped or pasted.
 *
 * WHY THIS EXISTS. Success criterion #2 requires the block be visible IN STUDIO, where
 * the developer types the prompt into `compareWorkflow`'s run form by hand. The README
 * could simply quote a prompt string — and then that quoted string is a hand-copied
 * approximation that drifts the moment the scenario is regenerated, silently making the
 * Studio path a different experiment from `npm run demo`. This renders the SAME
 * mechanical expression `scripts/demo.ts` runs, so the two paths cannot diverge.
 *
 * Deliberately does NOT import `src/mastra.ts`: no agent, no key, no model — this is a
 * pure string over the vendored set and the generated templates.
 */
import { DEMO_TRIGGER_RECORD_ID } from "../src/config";
import { buildStageAPrompt } from "../src/scenario/prompts";
import { ClearedRecordSchema, type ClearedRecord } from "../src/schema";
import clearedSetJson from "../src/data/cleared-set.json";

const vendoredClearedSet: ClearedRecord[] = ClearedRecordSchema.array().parse(clearedSetJson);

const record = vendoredClearedSet.find(r => r.id === DEMO_TRIGGER_RECORD_ID);
if (!record) {
  throw new Error(`DEMO_TRIGGER_RECORD_ID "${DEMO_TRIGGER_RECORD_ID}" is not in the vendored `
    + `cleared set — config.ts's generated constant and src/data/cleared-set.json have drifted apart`);
}

// `process.stdout.write`, not `console.log`: no trailing formatting, so the output is
// exactly the prompt plus one newline.
process.stdout.write(buildStageAPrompt(record) + "\n");
