/**
 * §11 — the report generator, and the one invariant that makes "the report is never
 * hand-authored" true for EVERY caller, not just for the one that behaves.
 *
 * A demo report is only ever generated from a run that really blocked. §12 accepts a
 * live catch rate of `>= 0.9`, not 1.0, so the single trigger record can legitimately
 * fail to block on a given run — and the temptation at exactly that moment is to ship
 * the page anyway with a placeholder where the block should be. This function makes
 * that unrepresentable: it throws, and `renderReportHtml` cannot even be called with a
 * delivered run because its parameter type excludes one.
 *
 * The throw is the LAST-LINE invariant, not the UX. `scripts/demo.ts` diagnoses the
 * non-blocking case first and exits 2 with an explanation, so a developer never sees
 * this error for an expected outcome — it exists for the caller who skips that
 * diagnosis.
 */
import { renderReportHtml, type BlockedComparisonReport } from "./reportTemplate";
import type { ComparisonReport } from "../workflows/compareWorkflow";

export const NOT_BLOCKED_MESSAGE =
  "refusing to generate a demo report from a run whose guarded agent did not block: the report "
  + "exists to show a block, and one built from a delivered run would be a demo that did not "
  + "demonstrate anything. This is not necessarily a bug — the live catch rate bar is >= 0.9, not "
  + "1.0 — see scripts/demo.ts, which diagnoses this case and exits 2.";

/**
 * `report` is the `compareWorkflow` run's own output — §10's `ComparisonReportSchema`,
 * whose `outcome` field is cross-checked against `guarded.blocked` by the schema
 * itself, so the two can never disagree by the time it arrives here.
 */
export function generateHtmlReport(report: ComparisonReport): string {
  const { guarded } = report;
  if (!guarded.blocked) throw new Error(NOT_BLOCKED_MESSAGE);
  // Rebuilt rather than cast: `guarded` is NARROWED to the blocked arm by the check
  // above, so this object satisfies `BlockedComparisonReport` on the type checker's own
  // evidence. A cast would assert the same thing on ours.
  const blocked: BlockedComparisonReport = { ...report, guarded };
  return renderReportHtml(blocked);
}
