/**
 * §10 — the demo. Baseline vs guarded, side by side: the SAME model, the SAME
 * instructions, the SAME generation settings, differing ONLY in whether Carver's
 * cleared set gates the output.
 *
 * ── WHY THE RESULT SHAPE LOOKS THE WAY IT DOES (orchestrator D28.5) ─────────────
 * Mastra wraps output processors in a workflow, so a CORRECT `abort()` — the
 * guardrail doing exactly its job — emits `[WORKFLOW] Error executing step …`
 * plus a stack trace to stderr. **The guardrail working correctly looks like a
 * crash.** Nobody watching a demo reads the source to discover the red text was
 * the success path.
 *
 * This workflow cannot silence Mastra's stderr, and does not try. What it CAN do
 * — and does — is make sure the thing a viewer reads as "the answer" says BLOCK:
 *
 *   1. `run.start()` resolves `status: "success"`, never `"tripwire"`: the
 *      tripwire is contained inside `guardedStep` (via `normalizeDelivery`) and
 *      never propagates out of a step, so Mastra's workflow-level tripwire status
 *      is unreachable for this run shape.
 *   2. `ComparisonReportSchema.outcome` is a top-level `"BLOCKED" | "DELIVERED"`
 *      enum — the FIRST key of the workflow's output, and the first thing Studio's
 *      result panel renders. It is DERIVED from `guarded.blocked` and cross-checked
 *      by a refinement, so it can never disagree with the union it summarises. It
 *      is redundant by design: `guarded.blocked` already carries the fact, six
 *      keys deep inside a nested discriminated union. Redundancy is the point —
 *      the headline has to be legible without a schema in hand.
 *      (§10 pins `ComparisonReportSchema` as `{baseline, guarded}`. The extra key
 *      is ADDITIVE — every consumer §10 names still reads exactly what it read —
 *      and it exists because D28 makes the block's presentation this task's job.
 *      Flagged as a deviation, not silently taken.)
 *
 * ── THE OTHER THINGS THE SPEC GETS WRONG HERE, FLAGGED NOT FIXED ────────────────
 * §10's `new RequestContext({ firmProfile })` does NOT compile (TS2353 — the
 * constructor takes an entry-tuple iterable). See the call sites in
 * `comparisonWorkflow.test.ts`. §10's snippet also has `guardedStep` read
 * `err.reason`/`err.metadata` off a thrown TripWire; that is `tripwireContainment`'s
 * problem, and it is already corrected there — this step contains NOTHING itself
 * (D26), it awaits `normalizeDelivery` and maps.
 */
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";
import { FirmProfileSchema, type FirmProfile } from "../firmProfile";
import { normalizeDelivery } from "../processors/tripwireContainment";
import { ClearedRecordSchema, type ClearedRecord } from "../schema";
import { narrowObligationsPure } from "../tools/narrowObligations";
import clearedSetJson from "../data/cleared-set.json";

/** Parsed here rather than imported from a module that exports it: no module does
 *  (§8) — every consumer reads the JSON and parses it with the schema, so a drifted
 *  file fails loudly at import in each of them. */
const vendoredClearedSet: ClearedRecord[] = ClearedRecordSchema.array().parse(clearedSetJson);

const PromptInputSchema = z.object({ prompt: z.string() });
const DraftOutputSchema = z.object({ text: z.string() });

const draftStep = createStep({
  id: "baseline-draft",
  description: "The naked agent: no Carver data, no guardrail. Whatever it drafts is delivered.",
  inputSchema: PromptInputSchema,
  outputSchema: DraftOutputSchema,
  execute: async ({ inputData, mastra }) => {
    const agent = mastra.getAgent("baselineAgent");
    const result = await agent.generate(inputData.prompt);
    return { text: result.text };
  },
});

/** §5's seam fields §11's report displays, snake_case on both sides. */
const ClearedRecordSummarySchema = z.object({
  id: z.string(),
  regulator_name: z.string(),
  citation: z.object({ name: z.string(), url: z.string() }),
  compliance_date: z.string().nullable(),
  title: z.string(),
});

/**
 * A discriminated union on `blocked`, not one object with every field independently
 * nullable: a flat shape would PERMIT `blocked: true` with `blocked_draft: null`,
 * which §11's report cannot render. The union makes that unrepresentable.
 */
const BlockedGuardedResultSchema = z.object({
  blocked: z.literal(true),
  text: z.null(),
  blocked_draft: z.string(),
  reason: z.string(),
  processorId: z.string(),
  record: ClearedRecordSummarySchema,
  violated_obligation_ids: z.array(z.string()).min(1),
});

const PassGuardedResultSchema = z.object({
  blocked: z.literal(false),
  text: z.string(),
  blocked_draft: z.null(),
  reason: z.null(),
  processorId: z.null(),
  record: z.null(),
  violated_obligation_ids: z.array(z.string()).length(0),
});

/**
 * The refinements live on the UNION, not on `BlockedGuardedResultSchema`:
 * `z.discriminatedUnion` requires plain `ZodObject` members, and wrapping a member
 * in `.superRefine()` makes it a `ZodEffects` the discriminator cannot see through.
 */
export const GuardedResultSchema = z
  .discriminatedUnion("blocked", [BlockedGuardedResultSchema, PassGuardedResultSchema])
  .superRefine((v, ctx) => {
    if (!v.blocked) return;
    // The display record IS the highest-ranked violated obligation. `guardedStep`
    // satisfies this by construction (it derives `record` FROM
    // violated_obligation_ids[0]), so for that caller this is a tautology — kept
    // because the schema, not one caller's discipline, is what any future
    // constructor of a blocked result is held to.
    if (v.violated_obligation_ids[0] !== v.record.id) {
      ctx.addIssue({
        code: "custom",
        path: ["record", "id"],
        message: `display record ${v.record.id} is not violated_obligation_ids[0] `
          + `(${v.violated_obligation_ids[0]}) — audit, scoring and report would disagree`,
      });
    }
    if (new Set(v.violated_obligation_ids).size !== v.violated_obligation_ids.length) {
      ctx.addIssue({
        code: "custom",
        path: ["violated_obligation_ids"],
        message: "duplicate obligation id — §4's parseAndValidateVerdicts guarantees one verdict "
          + "per id, so a duplicate here means the metadata did not come from it",
      });
    }
  });

export type GuardedResult = z.infer<typeof GuardedResultSchema>;

const guardedStep = createStep({
  id: "guarded-draft",
  description: "The same agent with Carver's cleared set gating its output. A block here is the "
    + "DESIGNED outcome, not an error.",
  inputSchema: PromptInputSchema,
  outputSchema: GuardedResultSchema,
  execute: async ({ inputData, mastra, requestContext }): Promise<GuardedResult> => {
    const agent = mastra.getAgent("guardedAgent");

    // The AUTHORITATIVE candidate set for THIS call, recomputed from the same firm
    // profile the processor narrowed with, over the same vendored set it reads.
    // Deliberately NOT read out of the tripwire metadata: metadata is the thing being
    // validated, so letting it vouch for its own legitimacy is circular. Pure array
    // work (§9a) — no API call, no duplicated logic.
    //
    // No defensive parse: compareWorkflow's requestContextSchema validated firmProfile
    // at run.start(), so by the time any step executes it is present and well-formed or
    // the run never started.
    const firmProfile = requestContext.get("firmProfile") as FirmProfile;
    const candidateIds = narrowObligationsPure(firmProfile, vendoredClearedSet);

    const buildBlockedResult = (reason: string, processorId: string, metadata: unknown): GuardedResult => {
      const meta = (metadata ?? {}) as Record<string, unknown>;
      const blockedDraft = meta.blocked_draft;
      const violatedIds = meta.violated_obligation_ids;

      // Mastra failed to propagate the metadata this project's whole contract depends
      // on (§9c's abort() is the only place that sets it), or propagated something that
      // cannot have come from it. Fail loudly rather than return a plausible-but-wrong
      // obligation to the report.
      const problems: string[] = [];
      if (typeof blockedDraft !== "string" || blockedDraft.length === 0) {
        problems.push(`blocked_draft is ${typeof blockedDraft}`);
      }
      if (!Array.isArray(violatedIds) || violatedIds.length === 0) {
        problems.push(`violated_obligation_ids is ${Array.isArray(violatedIds) ? "empty" : typeof violatedIds}`);
      } else {
        if (new Set(violatedIds).size !== violatedIds.length) problems.push("duplicate obligation ids");
        // MEMBERSHIP IN THIS CALL'S NARROWED CANDIDATES — not merely "is a real vendored
        // record", which is too weak: a stale or forged id naming a genuine record that
        // was never among this call's candidates would pass, and the report would cite an
        // obligation the guardrail never considered. candidateIds is the exact set the
        // judge was asked about (§9b).
        const notCandidates = violatedIds.filter(id => !candidateIds.includes(id));
        if (notCandidates.length) {
          problems.push(`ids not among this call's narrowed candidates: ${notCandidates.join(",")}`);
        } else {
          // ORDER: violated must be a subsequence of the RANKED candidateIds, because §9c
          // builds it by filtering verdicts that are themselves in candidateIds order. Any
          // other order means the metadata did not come from that code path — and this is
          // what makes "…[0] is the highest-ranked violated obligation" a CHECKED fact
          // rather than a comment.
          const rankOf = (id: string) => candidateIds.indexOf(id);
          if (!violatedIds.every((id, i) => i === 0 || rankOf(violatedIds[i - 1]) < rankOf(id))) {
            problems.push("violated_obligation_ids are not in narrowing-rank order");
          }
        }
      }
      if (problems.length) {
        throw new Error(`CarverGuardrail tripwire fired but its metadata is unsound `
          + `(${problems.join("; ")}) — refusing to build an invalid blocked result`);
      }

      const ids = violatedIds as string[];
      // DERIVE the display record from the vendored set — never copy metadata's own
      // record object. Validating those fields would only catch a forged title/citation
      // by comparing every one of them; deriving makes forgery unrepresentable. The
      // lookup cannot fail: ids ⊆ candidateIds ⊆ vendoredClearedSet, both established
      // above.
      const source = vendoredClearedSet.find(r => r.id === ids[0])!;
      // Parsed HERE, not only at the step boundary, so the union's refinements fail with
      // THIS error's context rather than as an opaque step-output validation failure.
      return GuardedResultSchema.parse({
        blocked: true,
        text: null,
        blocked_draft: blockedDraft,
        reason,
        processorId,
        record: {
          id: source.id,
          regulator_name: source.regulator_name,
          citation: source.citation,
          compliance_date: source.compliance_date,
          title: source.title,
        },
        violated_obligation_ids: ids,
      });
    };

    // The dual-layer containment lives in ONE place — processors/tripwireContainment.ts
    // — and this is one of its two callers (§12's deliveryStep is the other). This step
    // never sees the return-vs-throw difference and never lets a tripwire propagate out
    // of execute(), which is what keeps the run's status "success" rather than
    // "tripwire" (D28: a block is the designed outcome, not an error).
    const outcome = await normalizeDelivery(() => agent.generate(inputData.prompt, { requestContext }));
    if (!outcome.tripped) {
      return {
        blocked: false as const,
        text: outcome.text,
        blocked_draft: null,
        reason: null,
        processorId: null,
        record: null,
        violated_obligation_ids: [],
      };
    }
    return buildBlockedResult(outcome.reason, outcome.processorId, outcome.metadata);
    // (execute() still throws for a metadata-completeness failure inside
    // buildBlockedResult, or for a truly unrelated error normalizeDelivery re-throws —
    // never for a tripwire.)
  },
});

/**
 * `outcome` FIRST and TOP-LEVEL, deliberately (D28.5) — see this module's header.
 * A block prints a red `[WORKFLOW] Error executing step …` to stderr because that is
 * how Mastra reports its own internal `abort()`; the run itself succeeded, and this
 * field is what says so in the one place a viewer actually reads.
 */
export const ComparisonReportSchema = z
  .object({
    outcome: z.enum(["BLOCKED", "DELIVERED"]),
    baseline: z.object({ text: z.string() }),
    guarded: GuardedResultSchema,
  })
  .superRefine((v, ctx) => {
    // The headline is DERIVED from `guarded.blocked`, so this can only fire if someone
    // constructs a report by hand and gets it wrong. That is exactly when a demo would
    // most like to lie, so it is checked rather than trusted.
    const expected = v.guarded.blocked ? "BLOCKED" : "DELIVERED";
    if (v.outcome !== expected) {
      ctx.addIssue({
        code: "custom",
        path: ["outcome"],
        message: `outcome is "${v.outcome}" but guarded.blocked is ${v.guarded.blocked} — the `
          + `headline must never disagree with the result it summarises`,
      });
    }
  });

export type ComparisonReport = z.infer<typeof ComparisonReportSchema>;

const reportStep = createStep({
  id: "report",
  description: "Remaps the parallel steps' outputs into the {outcome, baseline, guarded} shape "
    + "the HTML report and Studio both read.",
  // Keyed by each parallel step's own id (§9's Mastra convention). The step's own
  // `outputSchema` property is a StandardSchema, not a ZodType — §10 writes
  // `draftStep.outputSchema` here, which types the whole object as `unknown` and makes
  // this step's body uncompilable. The Zod schemas the steps were BUILT from are the
  // same objects, and they carry their types. Flagged, not silently fixed.
  inputSchema: z.object({
    "baseline-draft": DraftOutputSchema,
    "guarded-draft": GuardedResultSchema,
  }),
  outputSchema: ComparisonReportSchema,
  execute: async ({ inputData }): Promise<ComparisonReport> => {
    // .parallel() keys inputData by each step's own id — reportStep's ONLY job is
    // remapping those step-id keys to the clean shape everything downstream consumes.
    const guarded = inputData["guarded-draft"];
    return {
      outcome: guarded.blocked ? "BLOCKED" : "DELIVERED",
      baseline: { text: inputData["baseline-draft"].text },
      guarded,
    };
  },
});

export const compareWorkflow = createWorkflow({
  id: "compareWorkflow",
  description: "THE DEMO — the naked agent and the Carver-guarded agent draft the same task, side "
    + "by side. `outcome: \"BLOCKED\"` is the guardrail working, not a failure.",
  inputSchema: z.object({ prompt: z.string() }),
  // The firm profile travels as REQUEST CONTEXT, not as workflow input: it is per-run
  // configuration, not part of the task being drafted, and it must reach the guarded
  // step's processor without ever entering either agent's prompt (§8's verified
  // invisibility property). Declaring the schema here does three jobs at once:
  //   1. Mastra VALIDATES it at the start of run.start(), so a run that forgot the
  //      profile fails immediately with a named error at the boundary rather than deep
  //      inside a step;
  //   2. it gives Studio a schema-driven form for the value (§11's Studio path);
  //   3. it documents, in the workflow's own type, that firmProfile is a first-class
  //      input to the RUN.
  requestContextSchema: z.object({ firmProfile: FirmProfileSchema }),
  outputSchema: ComparisonReportSchema,
})
  .parallel([draftStep, guardedStep])
  .then(reportStep)
  .commit();
