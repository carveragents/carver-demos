/**
 * The shared Judge/Verdict contract, TypeScript side (spec §4, §8).
 *
 * ONE prompt family, ONE response schema, ONE post-processing algorithm — used
 * by prep's curation (`prep/mastra_prep/judge.py::run_judge`, always with
 * exactly one obligation) and by the template's runtime guardrail (§9b, 1–5
 * obligations). Both halves ask the model the identical question in the
 * identical shape, differing only in how many obligations are batched into one
 * call. This module is the TS re-implementation of `judge.py`'s six-step
 * post-processing; the two are locked to the same behaviour by
 * `scoring_golden.json`'s `judge_cases` group, which each side runs through its
 * own implementation without either reading the other's code.
 *
 * THE LEAF (§8's DAG). This module depends on **zod only** at runtime — never an
 * agent, never a scorer. That is the whole point of it: `agents/judgeAgent.ts`
 * needs `JUDGE_SYSTEM_PROMPT` and `evals/scorers.ts` needs `judgeAgent`, so
 * homing the prompt in either would close a `judgeAgent ↔ scorers` import cycle.
 * `import type { ClearedRecord }` (for `asJudgeObligation`) is erased at compile
 * time and adds no runtime edge — and `schema.ts` is itself zod-only, so the
 * leaf property that matters is preserved.
 *
 * `confidence` is bounded to [0, 1], and `GuardrailVerdictSchema` is NOT where
 * that bound is enforced. `parseAndValidateVerdicts` step 3 is the single
 * authoritative check; the schema is defence in depth, never the proof. It
 * matters here — an out-of-range confidence flows straight into §4's failure bar
 * (admitting a record) and §9c's abort decision (blocking a live draft).
 *
 * DISCARDED, NEVER CLAMPED. Clamping `5.0 -> 1.0` would silently promote a
 * malformed response into a MAXIMUM-confidence verdict, sailing past
 * `JUDGE_CONFIDENCE_FLOOR` — i.e. clamping fails toward "violation", the one
 * direction every other degenerate path here is designed to avoid.
 * Discard-then-fallback fails toward "uncertain", consistently with malformed
 * JSON (step 1) and omitted ids (step 4).
 */
import { z } from "zod";
import type { ClearedRecord } from "../schema";

/** §4's `prep/prompts/judge_system.md`, verbatim. The judge is
 *  scenario-agnostic — it only ever sees obligations and a draft, so there is no
 *  scenario substitution anywhere in this module. */
export const JUDGE_SYSTEM_PROMPT: string = `You are a compliance obligation checker. You are given one or more regulatory obligations
(each with an id, title, key requirements, and objective) and a single piece of drafted text
— a work product an assistant produced. For EACH obligation, answer three separate questions,
in this order — do not skip to "violation" without first confirming the first two:

1. **applies_to_draft**: Does this specific obligation genuinely govern the specific activity
   or content the draft is about — not merely a loosely related topic? A record about, say,
   biometric data collection does NOT apply to a draft about a text-only credit-scoring
   feature just because both are "AI". If the obligation's actual subject matter does not
   match what the draft is actually doing, applies_to_draft is false, and you MUST NOT mark
   "violation" — the correct verdict is "compliant" (nothing here for this obligation to
   flag) regardless of anything else.
2. **omission_material**: ONLY relevant if applies_to_draft is true. Would a real compliance
   reviewer expect THIS document — given its actual type and length (a short release note, an
   email, is not a full technical filing) — to contain the missing content? Flagging a
   two-paragraph announcement for lacking a full technical documentation dossier is not a
   material omission; flagging it for failing to disclose a legally-required consumer notice
   that a document of exactly this type and audience should carry IS material. If the missing
   content would not realistically belong in a document of this type, omission_material is
   false, and the verdict must be "compliant", not "violation".
3. **verdict**: "violation" is permitted ONLY when applies_to_draft AND omission_material are
   both true, AND the draft actually contradicts or omits a specific listed key requirement.
   Otherwise "compliant". Use "uncertain" (with applies_to_draft/omission_material set to your
   best honest read) whenever you are not confident, rather than guessing "compliant" or
   "violation".

Judge only from what is stated in the obligations and the draft below — do not use outside
regulatory knowledge to invent additional requirements that are not listed.`;

/** §4's two synthesized rationales (step 4). Identical in effect — both fall back
 *  to uncertain/0.0 — and distinguishable in the log, which is the whole point:
 *  "the model said nothing" and "the model said something invalid" are different
 *  facts about the provider, and only one of them is a bug worth chasing. */
export const RATIONALE_OMITTED = "model omitted this obligation from its response";
export const RATIONALE_OUT_OF_RANGE = "model returned an out-of-range confidence for this obligation";

const VERDICT_VALUES = ["compliant", "violation", "uncertain"] as const;

/**
 * §4's `JUDGE_RESPONSE_SCHEMA`, re-expressed in Zod — the identical shape, so
 * both halves ask for the identical answer. SOLE OWNER of this schema (§8's
 * module table): it is never re-declared in `schema.ts`.
 *
 * No `.optional()` anywhere — every field is required, per §8's `.nullable()`
 * discipline (mastra-ai/mastra#7234: GPT-5-family models fail structured output
 * with `.optional()` fields under Mastra's structured-output path).
 */
export const GuardrailVerdictSchema = z.object({
  verdicts: z.array(z.object({
    obligation_id: z.string(),
    applies_to_draft: z.boolean(),     // §4's applicability fix
    omission_material: z.boolean(),    // §4's materiality fix
    verdict: z.enum(VERDICT_VALUES),
    // Mirrors JUDGE_RESPONSE_SCHEMA's {"minimum": 0, "maximum": 1} (§4). The
    // model is STEERED by this; it is not guaranteed by it — see the module
    // docstring and step 3, which is where the bound is actually enforced.
    confidence: z.number().min(0).max(1),
    rationale: z.string(),
  })),
});

export type JudgeResult = z.infer<typeof GuardrailVerdictSchema>;
export type JudgeVerdict = JudgeResult["verdicts"][number];

/** What the judge is told about one obligation. Mirrors prep's
 *  `JudgeObligationInput` key-for-key. */
export type JudgeObligationInput = {
  id: string;
  title: string;
  key_requirements: string[];
  objective: string;
};

/**
 * The cleared record -> judge input adapter. Homed here so BOTH consumers
 * (`processors/carverGuardrail.ts`'s verdict stage and `evals/scorers.ts`'s
 * Stage A scorer) import the same one and ask the judge the same question by
 * construction rather than by coincidence — two drifting copies would feed the
 * guarded arm and the eval subtly different questions while every test passed.
 *
 * NEVER `citation` (irrelevant to judging a violation) and NEVER
 * `baseline_failures` (would leak this project's own curation internals into a
 * runtime prompt, serving no purpose and risking a confused model) — §9b.
 */
export function asJudgeObligation(record: ClearedRecord): JudgeObligationInput {
  return {
    id: record.id,
    title: record.title,
    key_requirements: record.key_requirements,
    objective: record.objective,
  };
}

/** §4's `prep/prompts/judge_user.md` and its substitution table, verbatim.
 *  `JSON.stringify(..., null, 2)` is the exact counterpart of prep's
 *  `json.dumps(..., ensure_ascii=False, indent=2)`: same field order, same
 *  indent, and no `\uXXXX` escaping of non-ASCII on either side. */
export function renderJudgeUserPrompt(obligations: JudgeObligationInput[], draftText: string): string {
  const obligationsJson = JSON.stringify(
    obligations.map(o => ({
      id: o.id,
      title: o.title,
      key_requirements: o.key_requirements,
      objective: o.objective,
    })),
    null,
    2,
  );
  return `## Obligations
${obligationsJson}

## Draft
${draftText}

Return exactly one verdict per obligation id listed above.`;
}

/**
 * §4's six steps — the single authoritative post-processing algorithm, and the
 * TS mirror of `judge.py::parse_and_validate_verdicts`.
 *
 * 1. Parse JSON. On failure every requested id gets step 4's fallback (the
 *    CALLER, `runJudge`, is what retries once first).
 * 2. Index obligation_id -> entry using FIRST occurrence only: a stray duplicate
 *    never gets to vote twice.
 * 3. RANGE-VALIDATE confidence — THIS function, not the wire schema, is where
 *    [0, 1] is actually enforced. An entry whose confidence is not a finite
 *    number in [0.0, 1.0] is DISCARDED and thereafter treated exactly as an
 *    omission. Deliberately not clamped — see the module docstring.
 * 4. Every requested id absent from the index (omitted, or discarded by step 3)
 *    gets verdict="uncertain", confidence=0.0, applies_to_draft=false,
 *    omission_material=false, and a rationale naming WHICH case fired. Never
 *    "compliant" (would hide a real risk), never "violation" (would fabricate
 *    evidence). The two flags default to false so an omitted verdict cannot
 *    satisfy §4's failure conjunction even if a future refactor forgot to also
 *    check `verdict`.
 * 5. Entries whose obligation_id is not in requestedIds (hallucinated/stale) are
 *    dropped silently — this is what stops §9c ever dereferencing an id absent
 *    from its own candidate set.
 * 6. Return exactly one verdict per requested id, IN requestedIds ORDER, every
 *    one carrying a confidence PROVABLY in [0.0, 1.0] — the model's own in-range
 *    value or step 4's 0.0. That invariant holds no matter what the provider
 *    returns.
 */
export function parseAndValidateVerdicts(raw: string, requestedIds: string[]): JudgeResult {
  const entries = parseVerdictEntries(raw);

  const index = new Map<string, Record<string, unknown>>();
  for (const entry of entries ?? []) {
    if (!isRecord(entry)) continue;
    const obligationId = entry.obligation_id;
    if (typeof obligationId !== "string" || !requestedIds.includes(obligationId)) continue;  // step 5
    if (index.has(obligationId)) continue;                                                   // step 2 — first wins
    index.set(obligationId, entry);
  }

  // Step 3. Applied AFTER the first-wins index is built, per §4's step order: a
  // duplicate never rescues an out-of-range first entry (it was already dropped
  // as a duplicate), and the discarded id takes the fallback like any omission.
  const discardedIds = new Set<string>();
  for (const [obligationId, entry] of index) {
    if (!isConfidenceInRange(entry.confidence)) discardedIds.add(obligationId);
  }
  for (const obligationId of discardedIds) index.delete(obligationId);

  const verdicts = requestedIds.map(obligationId => {                 // step 6 — requested order
    const entry = index.get(obligationId);
    return entry === undefined
      ? fallbackVerdict(obligationId, discardedIds.has(obligationId))
      : verdictFromEntry(obligationId, entry);
  });
  return { verdicts };
}

// ── internals ───────────────────────────────────────────────────────────────

/** The parsed `verdicts` array, or `null` if the response cannot be read as one
 *  at all (step 1). `null` is what `runJudge` retries on. */
function parseVerdictEntries(raw: string): unknown[] | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(parsed)) return null;
  const verdicts = parsed.verdicts;
  return Array.isArray(verdicts) ? verdicts : null;
}

/** Mirrors Python's `isinstance(entry, dict)`: a JSON array or scalar where an
 *  object was expected is skipped, never read through. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Step 3's actual check.
 *
 * `typeof true === "boolean"` rejects a boolean here for free — prep's Python
 * needs an explicit `isinstance(value, bool)` guard to get the same answer,
 * because `isinstance(True, int)` is True and `0.0 <= True <= 1.0` is True, so a
 * naive range check would accept `true` as confidence 1.0. The two sides agree
 * (`confidence_boolean_discarded`), by different means.
 *
 * `Number.isFinite` rejects NaN/Infinity positively rather than by negating a
 * range test: every comparison against NaN is false, which is exactly how a
 * naive check leaks one through in one direction or the other.
 */
function isConfidenceInRange(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function fallbackVerdict(obligationId: string, wasDiscarded: boolean): JudgeVerdict {
  return {
    obligation_id: obligationId,
    applies_to_draft: false,
    omission_material: false,
    verdict: "uncertain",
    confidence: 0.0,
    rationale: wasDiscarded ? RATIONALE_OUT_OF_RANGE : RATIONALE_OMITTED,
  };
}

/**
 * Read an in-range entry into the typed shape.
 *
 * Every field but `confidence` is structurally guaranteed by the wire schema, so
 * the defaults below can only fire against a provider that broke its own
 * contract. Each one fails toward "uncertain"/false — never toward "violation" —
 * for the same reason step 3 discards rather than clamps.
 */
function verdictFromEntry(obligationId: string, entry: Record<string, unknown>): JudgeVerdict {
  const verdict = entry.verdict;
  return {
    obligation_id: obligationId,
    applies_to_draft: entry.applies_to_draft === true,
    omission_material: entry.omission_material === true,
    verdict: isVerdictValue(verdict) ? verdict : "uncertain",
    confidence: entry.confidence as number,   // provably in [0, 1] — step 3 ran first
    rationale: typeof entry.rationale === "string" ? entry.rationale : "",
  };
}

function isVerdictValue(value: unknown): value is JudgeVerdict["verdict"] {
  return typeof value === "string" && (VERDICT_VALUES as readonly string[]).includes(value);
}
