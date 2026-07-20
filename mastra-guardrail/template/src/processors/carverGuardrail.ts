/**
 * `CarverGuardrail` — the mechanism this whole demo exists to show (spec §9).
 *
 * Three stages, in order, on the guarded arm's output ONLY:
 *
 *   (a) NARROW   — `narrowObligationsPure(firmProfile, clearedSet)` (§9a). Pure
 *                  array work, no LLM, sub-millisecond. Called directly, never
 *                  as an agent tool-call: narrowing must be unconditional, not
 *                  something the model can decline to do.
 *   (b) VERDICT  — ONE `runJudge` call for ALL candidates (§9b), through
 *                  `judge/callJudge.ts` — the only permitted `judgeAgent` path.
 *   (c) ENFORCE  — §9c's severity ladder: high -> audit + `abort()`,
 *                  medium -> audit + annotate, low -> audit + pass.
 *
 * IT NEVER BLOCKS BECAUSE SOMETHING WENT WRONG. Every degenerate path — no
 * candidates, a judge that cannot answer, a verdict that fails any one of §9c's
 * four conditions — returns the draft unchanged. The guardrail blocks only on
 * affirmative, in-range, applicable, material evidence. That direction is
 * deliberate and it is the same one §4's every fallback fails in.
 *
 * IT CONTAINS NOTHING ITSELF. `abort()` throws Mastra's `TripWire` and Mastra's
 * own machinery converts it into `result.tripwire` on the caller's side. The
 * block/error distinction is answered in exactly one place —
 * `processors/tripwireContainment.ts`'s `normalizeDelivery` — and this module
 * neither imports nor duplicates it. §8's module table claims `isTripWireError`
 * for this file too; that is the known F2 duplicate (orchestrator D26): one
 * owner, and it is not this one.
 *
 * ── WHERE THE METADATA GOES, AND WHY IT IS LOAD-BEARING ────────────────────
 * §10's `guardedStep` REJECTS a block whose metadata is unsound — no
 * `blocked_draft`, an empty/duplicated/out-of-rank-order `violated_obligation_ids`
 * — by throwing. So a correct block carrying wrong metadata does not degrade
 * gracefully; it becomes a LOUD CRASH (orchestrator D26 found exactly that
 * failure live, from reading the wrong TripWire properties). The `abort()` call
 * below is the ONLY place this metadata is ever set, and
 * `carverGuardrail.test.ts` drives a REAL Agent through the REAL `abort()` to
 * prove it arrives intact rather than asserting it against our own imagination.
 */
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { Processor, ProcessOutputResultArgs } from "@mastra/core/processors";
import { JUDGE_CONFIDENCE_FLOOR } from "../config";
import type { FirmProfile } from "../firmProfile";
import { runJudge } from "../judge/callJudge";
import { asJudgeObligation, type JudgeResult, type JudgeVerdict } from "../judge/contract";
import { ClearedRecordSchema, type ClearedRecord } from "../schema";
import { narrowObligationsPure } from "../tools/narrowObligations";
import clearedSetJson from "../data/cleared-set.json";

/** The messages `processOutputResult` receives and returns. Derived from the
 *  args type rather than imported from a second path, so it cannot drift from
 *  what Mastra actually hands us. */
type OutputMessages = ProcessOutputResultArgs["messages"];

export type Severity = "high" | "medium" | "low";
export type EnforcementAction = "aborted" | "annotated" | "logged";

export type AuditEntry = {
  timestamp: string;
  processorId: string;
  /** The DISPLAY record — `violatedObligationIds[0]`. A report shows one
   *  obligation; the array below is the complete, auditable finding. */
  obligationId: string;
  /** EVERY obligation judged violated on this call, in narrowing-rank order. */
  violatedObligationIds: string[];
  severity: Severity;
  action: EnforcementAction;
  rationale: string;
};

export interface AuditWriter {
  write(entry: AuditEntry): void;
}

/**
 * The default writer. Append-only JSONL — one line per enforcement event.
 *
 * OWNED by `CarverGuardrail`, never Mastra's optional `Processor.onViolation`
 * hook: `onViolation` is opt-in plumbing nothing in this project ever assigns,
 * so an earlier draft's `onViolation?.(...)` calls were silent no-ops and the
 * promised audit file was never written at all (§9). This one is constructed by
 * default and called unconditionally in every enforcement branch.
 */
export class FileAuditWriter implements AuditWriter {
  constructor(private readonly path: string = ".mastra/output/guardrail-audit.jsonl") {}

  write(entry: AuditEntry): void {
    mkdirSync(dirname(this.path), { recursive: true });
    appendFileSync(this.path, JSON.stringify(entry) + "\n");
  }
}

/** The real, shipped `src/data/cleared-set.json` — validated once at module
 *  load (the same discipline `narrowObligations.ts` applies to it), so a schema
 *  drift fails loudly here rather than as silently wrong enforcement. */
const vendoredClearedSet: ClearedRecord[] = ClearedRecordSchema.array().parse(clearedSetJson);

/** Highest first — §9c's ladder order, and the order `highestImpactLabel`
 *  scans in. */
const SEVERITY_LADDER: readonly Severity[] = ["high", "medium", "low"];

/**
 * §9c's display-severity lookup — a pure lookup of Carver's own
 * `impact_label`, never LLM-invented (goal #6).
 *
 * The return type is the WIDE union even though `ClearedRecord["impact_label"]`
 * is the literal `"high"` (goal #3's candidate filter admits nothing else, so
 * every vendored record is `"high"` BY CONSTRUCTION — the spec's Goal-issue
 * callout). Narrowing the type to `"high"` would make §9c's `medium`/`low`
 * branches un-writable rather than merely unreachable, and the ladder is
 * specified generically on purpose.
 */
function highestImpactLabel(records: ClearedRecord[]): Severity {
  return SEVERITY_LADDER.find(severity => records.some(record => record.impact_label === severity))!;
}

function buildAuditEntry(
  record: ClearedRecord,
  violatedObligationIds: string[],
  severity: Severity,
  action: EnforcementAction,
  rationale: string,
): AuditEntry {
  return {
    timestamp: new Date().toISOString(),
    processorId: CARVER_GUARDRAIL_ID,
    obligationId: record.id,
    violatedObligationIds,
    severity,
    action,
    rationale,
  };
}

/**
 * §9c's four-condition conjunction — the SAME one prep's
 * `score_missed_obligation` applies (§4). A bare `verdict === "violation"` is
 * never sufficient at runtime either:
 *
 *   • narrowing (§9a) established topical/jurisdictional relevance, but NOT that
 *     THIS draft's content genuinely triggers THIS obligation — `applies_to_draft`
 *     is what the judge must confirm;
 *   • nor that a flagged omission is material to a document of this type —
 *     `omission_material`;
 *   • nor that the judge is confident enough to act on — the floor.
 *
 * "uncertain" fails it, which is what makes a broken judge a pass-through.
 */
function isEnforceable(verdict: JudgeVerdict): boolean {
  return verdict.verdict === "violation"
    && verdict.confidence >= JUDGE_CONFIDENCE_FLOOR
    && verdict.applies_to_draft
    && verdict.omission_material;
}

/** §9c's `medium` branch — a visible, non-blocking warning prepended to the
 *  draft. Unreachable against real data (every vendored record is `"high"`);
 *  exercised only by `carverGuardrail.test.ts`'s synthetic fixtures. */
function annotateOutputWithWarning(messages: OutputMessages, record: ClearedRecord): OutputMessages {
  const warning =
    `[COMPLIANCE WARNING — Carver] This draft may not meet ${record.title} `
    + `(${record.regulator_name}, ${record.citation.name}). Review before sending.`;

  const lastAssistantIndex = messages.map(message => message.role).lastIndexOf("assistant");
  if (lastAssistantIndex === -1) return messages;   // nothing to annotate

  return messages.map((message, index) => {
    if (index !== lastAssistantIndex) return message;
    return {
      ...message,
      content: {
        ...message.content,
        parts: [{ type: "text" as const, text: warning }, ...message.content.parts],
        // `content` is MessageList's v4-compat mirror of the text parts. Kept in
        // step with `parts` — a consumer reading either must see the warning.
        ...(typeof message.content.content === "string"
          ? { content: `${warning}\n\n${message.content.content}` }
          : {}),
      },
    };
  });
}

const CARVER_GUARDRAIL_ID = "carver-guardrail";

export class CarverGuardrail implements Processor {
  readonly id = CARVER_GUARDRAIL_ID;

  /**
   * `auditWriter` is injected exactly as §9 specifies (a real default; tests
   * pass a stub instead of writing to disk).
   *
   * `clearedSet` is the same idea applied to the processor's OTHER external
   * dependency, and it is the seam §14's test list needs: it demands a
   * "synthetic verdict fixture drives each of high/medium/low through
   * enforcement", but `medium`/`low` are chosen from a matched record's
   * `impact_label`, and every record in the vendored set is `"high"` by
   * construction — so with the set read only at module scope those two branches
   * are not merely unreachable in production, they are untestable, and §14 asks
   * for something impossible. Production behaviour is unchanged:
   * `new CarverGuardrail()` reads the real vendored set, exactly as specified.
   */
  constructor(
    private readonly auditWriter: AuditWriter = new FileAuditWriter(),
    private readonly clearedSet: ClearedRecord[] = vendoredClearedSet,
  ) {}

  async processOutputResult({
    messages,
    abort,
    requestContext,
    result,
  }: ProcessOutputResultArgs): Promise<OutputMessages> {
    // ── (a) DETERMINISTIC NARROWING (§9a) ──────────────────────────────────
    const firmProfile = readFirmProfile(requestContext);
    const candidateIds = narrowObligationsPure(firmProfile, this.clearedSet);
    if (candidateIds.length === 0) {
      // Nothing to enforce. The draft passes through untouched, and NO audit
      // entry is written: the audit log's semantics are "a violation occurred",
      // and a narrowing miss is not one (§9a).
      return messages;
    }

    // ── (b) LLM VERDICT (§9b) ──────────────────────────────────────────────
    // `result.text` is Mastra's own resolved draft — the exact string
    // `agent.generate()` returns, and therefore the exact string `blocked_draft`
    // promises §10/§11. §9c writes `extractText(messages)`; re-deriving it from
    // the message parts would mean re-implementing role filtering and part
    // extraction, and getting that subtly wrong puts the USER'S PROMPT into the
    // judged draft. Flagged as a spec deviation rather than silently taken.
    const draftText = result.text;
    const judged = await this.runVerdict(draftText, candidateIds);

    // ── (c) ENFORCEMENT (§9c) ──────────────────────────────────────────────
    const violated = judged.verdicts.filter(isEnforceable);
    if (violated.length === 0) return messages;   // no write — nothing was violated

    // Safe by construction: `parseAndValidateVerdicts` (§4) guarantees every
    // returned obligation_id is one of `candidateIds`, and candidateIds ⊆
    // clearedSet. No existence check is needed, and none is faked.
    const matchedRecords = violated.map(verdict =>
      this.clearedSet.find(record => record.id === verdict.obligation_id)!);

    // EVERY violated obligation, not just the one we display. `violated`
    // inherits candidateIds order (§4 step 6 returns verdicts in requestedIds
    // order; candidateIds is narrowObligationsPure's rank order), so this array
    // is deterministic — same draft, same profile, same array, every run.
    //
    // Why it exists: one draft can legitimately violate several narrowed
    // obligations, but a tripwire can foreground only one record. Without the
    // array, §12's guarded scorer — "was the ground-truth obligation caught?" —
    // would score a MISS whenever the draft violated the expected obligation AND
    // a higher-ranked one: a correct block scored as a failure, purely because
    // the display slot was taken. The set is the finding; the record is the
    // headline.
    const violatedObligationIds = violated.map(verdict => verdict.obligation_id);

    const maxSeverity = highestImpactLabel(matchedRecords);
    // The DISPLAY record: highest-severity violated obligation and, among equals
    // (which is all of them), the first in narrowing-rank order.
    const highest = matchedRecords.find(record => record.impact_label === maxSeverity)!;
    // Exactly one match: obligation_id is unique per verdict (§4's guarantee).
    const highestVerdict = violated.find(verdict => verdict.obligation_id === highest.id)!;

    switch (maxSeverity) {
      case "high":
        // The write happens BEFORE abort(): abort() never returns, so anything
        // after it is unreachable — and the high branch is the ONLY one real
        // data can reach, so writing second would mean the audit trail is empty
        // in every real case, which defeats its entire purpose.
        this.auditWriter.write(
          buildAuditEntry(highest, violatedObligationIds, "high", "aborted", highestVerdict.rationale));
        // `return abort(...)`, not a bare call: abort() is typed `=> never` and
        // throws Mastra's TripWire, so the `break` §9c writes after it is dead
        // — and a bare call leaves this case FALLING THROUGH into "medium" for
        // any reader (and for any future version where abort() returns), which
        // would write a second audit entry and annotate a draft that was
        // blocked. The return makes the branch's end structural.
        return abort(highestVerdict.rationale, {
          metadata: {
            processorId: this.id,
            // A SIBLING of `record`, not nested in it: it describes the draft,
            // not the obligation. §10 rejects a block without it.
            blocked_draft: draftText,
            // Likewise a sibling: the CALL's complete finding (§12 scores
            // membership in this), while `record` is the one §11 displays.
            violated_obligation_ids: violatedObligationIds,
            record: {
              id: highest.id,
              regulator_name: highest.regulator_name,
              citation: highest.citation,
              compliance_date: highest.compliance_date,
              title: highest.title,
            },
          },
        });

      case "medium":
        this.auditWriter.write(
          buildAuditEntry(highest, violatedObligationIds, "medium", "annotated", highestVerdict.rationale));
        return annotateOutputWithWarning(messages, highest);

      case "low":
        this.auditWriter.write(
          buildAuditEntry(highest, violatedObligationIds, "low", "logged", highestVerdict.rationale));
        return messages;
    }
  }

  /**
   * §9b's verdict stage, entire: build the obligation inputs, delegate.
   *
   * Prompt rendering, the `judgeAgent` call, the retry, the all-uncertain
   * fallback and §4's six-step parse/validation all live in
   * `judge/callJudge.ts` — the SAME function §12's Stage A scorer calls, so
   * runtime enforcement and the eval cannot diverge. A method rather than §9b's
   * free function only because the cleared set it indexes is instance state.
   */
  private async runVerdict(draftText: string, candidateIds: string[]): Promise<JudgeResult> {
    const obligations = candidateIds.map(id =>
      asJudgeObligation(this.clearedSet.find(record => record.id === id)!));
    return runJudge(obligations, draftText);
  }
}

/**
 * The firm profile is per-run configuration the guarded arm cannot work without
 * (§8) — `requestContext` is where it lives, and `compareWorkflow`'s
 * `requestContextSchema` validates it at `run.start()` (§10), so by the time
 * this runs it is present or the run never started.
 *
 * A missing profile is therefore a WIRING BUG, and this throws a named error
 * rather than passing the draft through. Degrading silently here would make the
 * guarded arm indistinguishable from the baseline while every test still passed
 * — the guardrail switched off by an omission nobody sees. It cannot be
 * mistaken for a block either: `normalizeDelivery` re-throws anything that is
 * not a TripWire, untouched (§10). This is NOT the judge-failure path, which
 * genuinely has evidence saying "no violation found" and passes through (§9b);
 * here there is no evidence at all, because the guardrail never ran.
 */
function readFirmProfile(requestContext: ProcessOutputResultArgs["requestContext"]): FirmProfile {
  const firmProfile = requestContext?.get("firmProfile") as FirmProfile | undefined;
  if (!firmProfile) {
    throw new Error(
      "CarverGuardrail: no firmProfile in requestContext — the guarded arm cannot narrow without "
      + "it. Pass `requestContext: new RequestContext([[\"firmProfile\", DEMO_FIRM_PROFILE]])` on "
      + "the generate()/run.start() call (§8, §10).",
    );
  }
  return firmProfile;
}
