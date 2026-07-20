/**
 * Deterministic obligation narrowing (spec §9a).
 *
 * `narrowObligationsPure` filters the cleared regulatory set down to the ≤5
 * obligations relevant to a firm profile, and ranks what survives. It is
 * invoked directly by `processors/carverGuardrail.ts` as a plain function call
 * (`narrowObligations.execute({ firmProfile })`) — narrowing must be
 * unconditional and fast, never something an LLM can decline to call. No API
 * call, no randomness, sub-millisecond.
 *
 * **Required vs. ranking — not one blended score.** An earlier draft of this
 * spec used a single additive `matchScore >= 1` gate, under which a lone weak
 * signal (`scope === "supranational"` matching unconditionally) could admit an
 * obligation with no real connection to the firm, and top-5 truncation could
 * then discard an actually-relevant record in favour of that noise. The fix
 * separates REQUIRED relevance (must hold) from ranking (orders what already
 * passed): jurisdiction match AND (industry-or-sector overlap OR function
 * overlap) are both required; only records clearing both gates compete for the
 * five ranked slots.
 *
 * Kept in lockstep with `prep/mastra_prep/generate_template_config.py`'s
 * `narrow_obligations_pure` by `narrowing_golden.json` (duplicated byte-for-byte
 * in `prep/tests/fixtures/` and `template/tests/fixtures/`) — never by importing
 * across the language boundary (goal #1 forbids it). See
 * `narrowObligations.test.ts::narrowObligationsPure — golden parity` for the
 * proof this port agrees with Python's.
 *
 * **`impactedFunctions` (camelCase) is authoritative — orchestrator D18.** §9a's
 * own pseudocode reads `firm.impacted_functions`, which is WRONG: in
 * TypeScript that misspelling is not an error, it is `undefined`, so narrowing
 * would silently lose one of its two required predicates while still firing,
 * still blocking, and still looking correct. `FirmProfileSchema` (firmProfile.ts)
 * and this file agree on `impactedFunctions`; the pseudocode does not.
 *
 * **Three operators §9a names but never defines — orchestrator D24, RATIFIED,
 * copied here rather than re-derived** (`narrowing_golden.json` cannot lock a
 * semantic no case exercises):
 *   1. `overlapCount` iterates the RECORD's tags against a SET of the firm's.
 *      Direction is observable: `firmProfileForRecord` always duplicates
 *      `industry[0]` into `sector`, so iterating the firm's tags instead would
 *      double-count that duplicate and can flip top-5 membership.
 *   2. `daysBetween`'s delta is SIGNED (`complianceDate - SNAPSHOT_DATE`, via
 *      plain subtraction of millisecond timestamps). A compliance date already
 *      in the past is NEAR (weight 2), not far — `Math.abs` would rank an
 *      overdue obligation as if it were years away, the exact inversion of its
 *      real urgency. Past dates are routine here: the corpus cutoff bounds the
 *      PUBLICATION date, never the compliance date.
 *   3. An unparseable compliance date scores 1: `daysBetween` returns `NaN` for
 *      a value `new Date(...)` cannot parse, and `NaN <= 180` is `false`, so
 *      `urgencyWeight` falls to its `1` branch — never a throw, never a silent
 *      0. This is a normal input on this path, not an error: the corpus's date
 *      extraction has real rot, and `validate_cleared_record` type-checks
 *      `compliance_date` without parsing it, so a rotten value clears review.
 */
import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { ClearedRecordSchema, type ClearedRecord } from "../schema";
import { FirmProfileSchema, type FirmProfile } from "../firmProfile";
import { SNAPSHOT_DATE } from "../config";
import clearedSetJson from "../data/cleared-set.json";

/** §9a's `urgencyWeight` boundary: <= 180 days from SNAPSHOT_DATE scores 2. */
const URGENCY_NEAR_DAYS = 180;

/** `a.compliance_date ?? "9999-99-99"` — sorts nulls last. Not a real date,
 *  deliberately: a STRING comparison that sorts after every ISO date without
 *  pretending to be one. */
const NULL_DATE_SENTINEL = "9999-99-99";

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** The real, shipped `src/data/cleared-set.json` — validated once at module
 *  load, so a schema drift fails loudly here rather than surfacing as silently
 *  wrong narrowing at runtime. */
const vendoredClearedSet: ClearedRecord[] = ClearedRecordSchema.array().parse(clearedSetJson);

function jurisdictionMatches(record: ClearedRecord, firm: FirmProfile): boolean {
  if (record.jurisdiction.country && record.jurisdiction.country === firm.jurisdiction.country) return true;
  // A supranational/bloc-scoped record ONLY matches if its OWN bloc value
  // equals the firm's bloc — `scope === "supranational"` alone is never
  // sufficient; the bloc identities must actually agree.
  if (record.jurisdiction.bloc && record.jurisdiction.bloc === firm.jurisdiction.bloc) return true;
  return false;
}

/** `[...firm.industry, firm.sector]` — sector folded into the industry-overlap
 *  signal. */
function industryTags(firm: FirmProfile): string[] {
  return [...firm.industry, firm.sector];
}

/** Case-insensitive — tag capitalization is not guaranteed consistent across
 *  the corpus. */
function intersects(left: readonly string[], right: readonly string[]): boolean {
  const lowered = new Set(right.map(value => value.toLowerCase()));
  return left.some(value => lowered.has(value.toLowerCase()));
}

/** D24 #1 — iterates `recordTags` against a SET built from `firmTags`. Never
 *  the other direction: `firmTags` can carry a duplicate (industry[0] echoed
 *  into sector) that a firm-side iteration would double-count. */
function overlapCount(recordTags: readonly string[], firmTags: readonly string[]): number {
  const firmSet = new Set(firmTags.map(value => value.toLowerCase()));
  return recordTags.filter(value => firmSet.has(value.toLowerCase())).length;
}

/** D24 #2/#3 — signed day delta (`to - from`), `NaN` for either side an
 *  unparseable input, never `Math.abs`. */
function daysBetween(from: string, to: string): number {
  return (new Date(to).getTime() - new Date(from).getTime()) / MS_PER_DAY;
}

function urgencyWeight(complianceDate: string | null): number {
  if (!complianceDate) return 0;
  // SNAPSHOT_DATE ("2026-07-11", config.ts), NOT Date.now()/new Date() — the
  // corpus snapshot date is already this project's fixed reference point for
  // "now", so narrowing/ranking is deterministic on every run, on every
  // machine, forever.
  return daysBetween(SNAPSHOT_DATE, complianceDate) <= URGENCY_NEAR_DAYS ? 2 : 1;
}

/**
 * The Python port at `prep/mastra_prep/generate_template_config.py`'s
 * `narrow_obligations_pure` mirrors this function exactly — same required
 * predicates, same ranking, same SNAPSHOT_DATE-pinned urgency weight, same
 * top-5 slice, same tie-breaks.
 */
export function narrowObligationsPure(firmProfile: FirmProfile, clearedSet: ClearedRecord[]): string[] {
  const tags = industryTags(firmProfile);

  const relevant = clearedSet.filter(record =>
    jurisdictionMatches(record, firmProfile) &&                                                    // REQUIRED
    (intersects(record.impacted_business.industry, tags) ||
     intersects(record.impacted_functions, firmProfile.impactedFunctions))                          // REQUIRED (industry-or-sector OR function overlap)
  );

  const rankOf = (record: ClearedRecord): number =>
    overlapCount(record.impacted_business.industry, tags)
    + overlapCount(record.impacted_functions, firmProfile.impactedFunctions)
    + urgencyWeight(record.compliance_date);

  const ranked = [...relevant].sort((a, b) => {
    const diff = rankOf(b) - rankOf(a);
    if (diff !== 0) return diff;
    const dateA = a.compliance_date ?? NULL_DATE_SENTINEL;
    const dateB = b.compliance_date ?? NULL_DATE_SENTINEL;
    if (dateA !== dateB) return dateA < dateB ? -1 : 1;   // sooner deadline first, nulls last
    return a.id < b.id ? -1 : 1;                           // final deterministic tie-break
  });

  return ranked.slice(0, 5).map(record => record.id);
}

/**
 * Per goal #5(a), narrowing is explicitly "filter the cleared set BY FIRM
 * PROFILE (jurisdiction, sector, impacted_functions)" — draft text does not
 * participate. `narrowObligationsPure` takes `firmProfile` explicitly (not
 * implicitly read from `requestContext` inside `execute`) so it is directly
 * unit-testable with synthetic profiles, with no Mastra tool-execution harness
 * required — `execute` is a thin adapter over it, closing over the real
 * vendored cleared set.
 */
export const narrowObligations = createTool({
  id: "narrow-obligations",
  description: "Filter the cleared regulatory set to obligations relevant to this firm.",
  inputSchema: z.object({ firmProfile: FirmProfileSchema }),
  outputSchema: z.object({ candidateIds: z.array(z.string()).max(5) }),
  execute: async ({ firmProfile }) => ({
    candidateIds: narrowObligationsPure(firmProfile, vendoredClearedSet),
  }),
});
