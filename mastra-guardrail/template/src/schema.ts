/**
 * The cleared-record schema — the TypeScript half of the seam (spec §5).
 *
 * This mirrors `prep/mastra_prep/schema.py` key-for-key, `snake_case` on BOTH
 * sides deliberately (§5: one fewer moving part, and the vendored JSON stays
 * human-readable as shipped). The two halves hand-maintain their own schema
 * objects because goal #1 forbids `template/` depending on `prep/` — so a key or
 * a type wrong on either side does not fail loudly, it drifts silently and
 * surfaces as a demo that does not fire. `schema.test.ts` Zod-parses the real
 * `src/data/cleared-set.json` with `ClearedRecordSchema`, which is what turns
 * that drift into a red test.
 *
 * `predictsStageAViolation` is homed HERE, beside the schema it reads, never in
 * `evals/` (§5:2399): §7's generation contract and §10's demo both depend on the
 * concept and neither may depend on the eval harness.
 *
 * Does NOT export `GuardrailVerdictSchema` — that has exactly one owner,
 * `judge/contract.ts` (§8's module table).
 */
import { z } from "zod";

export const BaselineFailureSchema = z.object({
  mode: z.enum(["citation_fabricated", "date_wrong", "missed_obligation"]),
  stage: z.enum(["A", "B"]),
  baseline_response_excerpt: z.string(),
  judge_rationale: z.string().nullable(),
});

export const ClearedRecordSchema = z.object({
  id: z.string(),
  title: z.string(),
  regulator_name: z.string(),
  jurisdiction: z.object({
    scope: z.string(),
    country: z.string().nullable(),
    bloc: z.string().nullable(),
    region_name: z.string().nullable(),
  }),
  update_type: z.string(),
  impact_label: z.literal("high"),
  objective: z.string(),
  what_changed: z.string(),
  why_it_matters: z.string(),
  key_requirements: z.array(z.string()).min(1),
  compliance_date: z.string().nullable(),
  citation: z.object({ name: z.string(), url: z.string().url() }),
  impacted_business: z.object({
    size: z.array(z.string()),
    type: z.array(z.string()),
    industry: z.array(z.string()),
  }),
  impacted_functions: z.array(z.string()),
  scenario: z.enum(["A", "B"]),
  baseline_failures: z.array(BaselineFailureSchema).min(1),
  human_review: z.object({
    reviewer: z.string(),
    reviewed_at: z.string(),
    attestation: z.literal("approved"),
    obligation_applies_confirmed: z.boolean().nullable(),
    artifact_capable_of_violation_confirmed: z.boolean().nullable(),
    omission_materiality_confirmed: z.boolean().nullable(),
  }),
  source: z.object({
    artifact_id: z.string(),
    topic_id: z.string(),
    source_id: z.string(),
    snapshot_date: z.literal("2026-07-11"),
  }),
  probed_at: z.string(),
  model_id: z.literal("openai/gpt-5.6-sol"),
  model_cutoff: z.literal("2026-02-16"),
}).strict();   // rejects any unlisted key, mirroring validate_cleared_record()'s
               // Python-side rejection of unlisted top-level keys

export type ClearedRecord = z.infer<typeof ClearedRecordSchema>;

/**
 * Stage B's structured answer (§3's `stage_b_response` JSON schema, §12's
 * `stageBWorkflow` output). The RESPONSE fields only — prep's `StageBResult`
 * additionally carries `record_id`/`usage`/`called_at`, which are bookkeeping
 * the probe adds around the model's answer, not part of the answer itself.
 */
export const StageBResponseSchema = z.object({
  knows_source: z.boolean(),
  source_name: z.string().nullable(),
  source_url: z.string().nullable(),
  compliance_date: z.string().nullable(),
  confidence_note: z.string(),
});

/**
 * TRUE iff this record's OWN recorded evidence licenses the expectation: "the
 * guardrail blocks a Stage A draft written for this record's scenario."
 * Mirrors prep's `predicts_stage_a_violation` (§5) exactly — the two copies are
 * locked to the same behaviour by `scoring_golden.json`'s
 * `stage_a_predicate_cases` group, which each side runs through its own
 * implementation.
 *
 * WHY THIS EXISTS — do not widen it. A record admitted SOLELY for
 * `citation_fabricated`/`date_wrong` proves a Stage B KNOWLEDGE failure: the
 * baseline does not know this regulation. That is a perfectly good cleared
 * record, and it proves NOTHING about whether a *draft* violates the obligation.
 * Expecting a block anyway makes the demo and the guarded scoreboard fail while
 * the system behaves exactly as its own curated evidence says it should — the
 * most dangerous error available in this design, because it fails in the
 * direction that looks like success.
 *
 * The three-confirmation clause is redundant for SHIPPED records (§5's validator
 * already enforces it), and is re-checked anyway: this predicate gates the live
 * demo and the headline scoreboard number, and must not silently depend on a
 * validator elsewhere having run.
 */
export function predictsStageAViolation(record: ClearedRecord): boolean {
  const modes = new Set(record.baseline_failures.map(f => f.mode));
  if (!modes.has("missed_obligation")) return false;
  const hr = record.human_review;
  return hr.obligation_applies_confirmed === true
    && hr.artifact_capable_of_violation_confirmed === true
    && hr.omission_materiality_confirmed === true;
}
