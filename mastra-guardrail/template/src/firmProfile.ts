/**
 * The firm profile — the guarded arm's static, per-run configuration (§8).
 *
 * It lives in `requestContext`, NOT working memory: working memory is Mastra's
 * mechanism for conversational state that evolves across turns, whereas this is
 * static per-run configuration the agent never discovers or updates. It is a
 * `RequestContext` INSTANCE at every programmatic boundary, never a plain object
 * (`new RequestContext({ firmProfile })`), and it is read by the guardrail's
 * narrowing stage AFTER generation — it must never reach either compared agent's
 * prompt, or the two arms would differ in their INPUT rather than only in whether
 * Carver data gates their OUTPUT (goal #9's fatal case). §8's structural test
 * asserts that.
 *
 * PARTLY GENERATED. `DEMO_FIRM_PROFILE` below is written by
 * `generate_template_config.py` (§7 step 8) via idempotent replacement of that
 * one declaration. Whether it describes Aldergrove Labs (Scenario A) or Solmark
 * Capital (Scenario B) depends entirely on which scenario won — never
 * hand-authored, never Scenario-A-specific by default. Add around it; never
 * re-author this file whole.
 */
import { z } from "zod";
import type { ClearedRecord } from "./schema";

export const FirmProfileSchema = z.object({
  jurisdiction: z.object({ country: z.string(), bloc: z.string().nullable() }),
  sector: z.string(),
  industry: z.array(z.string()),
  size: z.enum(["small", "medium", "large"]),
  impactedFunctions: z.array(z.string()),
});
export type FirmProfile = z.infer<typeof FirmProfileSchema>;

// ── GENERATED (§7 step 8) — do not hand-edit; re-run the generator ───────────
export const DEMO_FIRM_PROFILE: FirmProfile = {
  "jurisdiction": {
    "country": "DE",
    "bloc": "EU"
  },
  "sector": "Artificial Intelligence",
  "industry": [
    "Artificial Intelligence",
    "Data Protection"
  ],
  "size": "medium",
  "impactedFunctions": [
    "Compliance",
    "Engineering"
  ]
};
// ── end generated ───────────────────────────────────────────────────────────

/**
 * The SAME construction `generate_template_config.py`'s Python port
 * (`firm_profile_for_record`) uses to build `DEMO_FIRM_PROFILE` from the
 * mechanically-chosen trigger record (§7). Used directly by the eval harness
 * (§12) to synthesize a per-record profile for EVERY cleared-set record, not
 * only the one demo trigger — never by the demo, which has one profile and one
 * trigger.
 *
 * GUARANTEE (proved in §9a, made true by §7's two narrowability preconditions):
 * for every record in the cleared set, `record` satisfies BOTH of
 * `narrowObligationsPure`'s REQUIRED predicates against
 * `firmProfileForRecord(record)`.
 *
 *   1. Jurisdiction — eligibility guarantees a non-empty `country` OR a
 *      non-empty `bloc`, and this copies both across, so one of
 *      `jurisdictionMatches`' two branches always fires. The `country: null` AND
 *      `bloc: null` case is excluded at eligibility, before any spend.
 *   2. Topical overlap — eligibility guarantees a non-empty `industry` OR a
 *      non-empty `impacted_functions`, and this copies both across; a non-empty
 *      set always intersects a superset of itself.
 *
 * That is RELEVANCE (passing the required gates), NOT a top-5 slot: `R` can
 * legitimately rank sixth behind five same-tag records with nearer compliance
 * dates. That is goal #5(a)'s "handful of candidate obligations" working, not a
 * defect — §7's trigger generation and §12's `crowdedOut` partition both handle
 * it explicitly rather than assuming otherwise.
 *
 * `impactedFunctions` is camelCase, matching `FirmProfileSchema`, even though
 * `ClearedRecord` is snake_case throughout: prep serializes its dict straight
 * into this object literal via `json.dumps()`, with no key-transform step. §9a's
 * pseudocode reads `firm.impacted_functions` and is WRONG (orchestrator D18) —
 * in TypeScript that misspelling is not an error, it is `undefined`, so narrowing
 * would silently lose one of its two required predicates while still firing,
 * still blocking, and still looking correct.
 */
export function firmProfileForRecord(record: ClearedRecord): FirmProfile {
  return {
    // `?? ""` — null-coalescing, not truthiness; prep's port mirrors it exactly.
    jurisdiction: { country: record.jurisdiction.country ?? "", bloc: record.jurisdiction.bloc },
    sector: record.impacted_business.industry[0] ?? "",
    industry: record.impacted_business.industry,
    size: "medium",
    impactedFunctions: record.impacted_functions,
  };
}
