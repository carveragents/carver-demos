/**
 * The template's whole config surface (§13: no `config.yaml` — Mastra templates
 * are TypeScript-config-native; the only other input is `.env`'s OPENAI_API_KEY,
 * read implicitly by the model router).
 *
 * PARTLY GENERATED. `DEMO_TRIGGER_RECORD_ID` at the foot of this file is written
 * by `prep/mastra_prep/generate_template_config.py` (§7 step 8) via idempotent
 * replacement of that one declaration. Everything above it is hand-authored and
 * survives a re-run. Add around the generated line; never re-author this file
 * whole.
 */

/** The ONE shared pinned constant (goal #9). Imported by BOTH compared agents —
 *  no second literal anywhere; swapping providers means editing this one line.
 *
 *  The `openai/` prefix is part of the value, not decoration: Mastra's model
 *  router takes the full `provider/model` router string (§13's framework claims
 *  table). Prep's OpenAI-SDK call sites strip it before passing `model=`; the
 *  full string is kept on BOTH sides so goal #9's "one shared pinned constant"
 *  holds at the config-value level. `prep/tests/test_config.py::
 *  test_model_id_matches_template` reads this file as inert text, regex-extracts
 *  the literal, strips `openai/` from both sides and asserts equality with
 *  config.yaml's `model_router_string` — the one mechanical guard against the two
 *  halves' pinned model silently drifting apart (§8). */
export const MODEL_ID = "openai/gpt-5.6-sol";

/** The pinned model's documented knowledge cutoff. Locked to prep's `budget.py`
 *  MODEL_CUTOFF by §2's drift check; every ClearedRecord carries it (§5). */
export const MODEL_CUTOFF = "2026-02-16";

/** The corpus snapshot date — this project's fixed reference point for "now"
 *  (§2, §13). `urgencyWeight` (§9a) ranks against THIS, never `Date.now()`, so
 *  narrowing is deterministic on every run, on every machine, forever. */
export const SNAPSHOT_DATE = "2026-07-11";

/** Mechanically locked to prep's `config.yaml` by §9c's drift-check test. A
 *  floor (goal's near-miss guard, §4), not a tunable default. */
export const JUDGE_CONFIDENCE_FLOOR = 0.7;

// No MAX_PROCESSOR_RETRIES — deliberately removed (§8). A retry that re-generates
// the guarded arm's draft would hand it a second chance the baseline structurally
// cannot have, which is a difference between the arms other than "whether Carver
// data gates the output" — goal #9's fatal case. `config.test.ts` asserts this
// module does not export it, so it cannot come back by accident.

/** Mirrors prep's `budget.py` REASONING_EFFORT (§3). A CODE CONSTANT, never a
 *  config key: reasoning_effort is a dial on BASELINE STRENGTH — "low" makes the
 *  same pinned model reason less, which makes more probes fail, which grows the
 *  cleared set. That is goal #9's named rigging mode reached through a knob goal
 *  #9 never anticipated. Locked to prep's constant by
 *  `test_reasoning_effort_matches_template` (§8), so curation and the scoreboard
 *  cannot silently measure the same model at different strengths. */
export const REASONING_EFFORT = "medium" as const;

/** Mirrors prep's Stage A `max_completion_tokens` (§3). Prep recorded the
 *  evidence in `data/cleared/` at this cap; `npm test` must replay the same arm,
 *  not whatever the provider happens to default to. */
export const MAX_OUTPUT_TOKENS = 3000;

/**
 * The ONE place either half's generation parameters live, TS-side (§8).
 *
 * Verified against Mastra's model docs: provider-specific knobs travel in
 * `providerOptions.<provider>` (OpenAI's `reasoningEffort` is named there
 * explicitly), and model settings use the AI SDK v5 convention
 * `maxOutputTokens` — NOT `maxTokens`. Mastra merges per-call options over agent
 * defaults, so pinning at the agent level makes these the value for every call
 * either agent makes unless a call overrides them, and nothing in this template
 * does.
 *
 * Both compared agents spread the SAME binding (not two equal literals — the
 * same object, so they cannot drift), attached as `defaultOptions`. `judgeAgent`
 * takes it too: it is the same model answering the same judge question prep's
 * `run_judge` asks, so it must reason at the same effort.
 */
export const GENERATION_CONFIG = {
  modelSettings: { maxOutputTokens: MAX_OUTPUT_TOKENS },
  providerOptions: { openai: { reasoningEffort: REASONING_EFFORT } },
} as const;

// ── GENERATED (§7 step 8) — do not hand-edit; re-run the generator ───────────
export const DEMO_TRIGGER_RECORD_ID: string = "art-1003";
