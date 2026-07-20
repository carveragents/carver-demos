/**
 * §10/§12 — the ONE place the "did the guardrail block this, or did the code crash?"
 * question is answered (goal #8's KNOWN RISK).
 *
 * WHY THIS MODULE EXISTS. A `catch` that conflates a correct block with a genuine
 * failure turns a *working* guardrail into a silent failure — this demo's claim,
 * exactly inverted. So the distinction is made once, here, and nowhere else: this
 * file holds the only `catch (err)` in the template. Callers (`guardedStep`, §10;
 * `deliveryStep`, §12) `await normalizeDelivery(...)` and MAP the returned
 * `TripwireOutcome` into their own schemas. They contain nothing themselves.
 *
 * WHAT IS SHARED, AND WHAT IS NOT. `guardedStep` returns `GuardedResult` (text,
 * blocked_draft, reason, processorId, a derived display record); `deliveryStep`
 * returns `DeliveryResult`. No single return type expresses both. What they share is
 * the *hard part* — the containment — so this returns the common core, not either
 * caller's shape.
 *
 * ── VERIFIED AGAINST @mastra/core 1.51.0 ITSELF (not against the docs, which the
 *    spec correctly notes are inconsistent across versions) ────────────────────────
 *
 * Driving a REAL Agent with a REAL output processor that calls `abort()`:
 *
 *   1. `abort(reason, options)` throws `new TripWire(reason, options, processor.id)`
 *      INSIDE the processor, and `runOutputProcessors` re-throws it — but Mastra's
 *      own stream machinery CATCHES it and converts it to state. So by the time
 *      `agent.generate()` returns to us it has **RETURNED NORMALLY**, carrying
 *      `result.tripwire = { reason, retry?, metadata?, processorId? }`, with
 *      `result.error === undefined` and `finishReason: "other"`. It does NOT throw.
 *      This confirms goal #8's "verified" note; the *thrown* form is the one that
 *      does not reach this caller on the `generate()` + `processOutputResult` path.
 *
 *   2. A GENUINE exception from a processor DOES escape `generate()` — as a
 *      `MastraError` wrapping the original. That is the case that must never be
 *      mistaken for a block, and it is why layer 2 re-throws rather than swallows.
 *
 * Layer 2 is therefore DEFENCE, not dead code: it costs nothing, and it is what makes
 * this helper correct if a future version (or a different call path — input
 * processors, a durable run) surfaces the tripwire in its thrown form instead. The
 * point of containing BOTH is that no caller ever has to know which happened.
 *
 * ── A REAL `TripWire`'s SHAPE — the spec's snippet gets this wrong ───────────────
 * The spec reads `err.reason` and `err.metadata`. On an actual `TripWire` instance
 * BOTH ARE `undefined` (verified by construction). The real shape is:
 *   • reason      → `err.message`            (TripWire extends Error; reason is the message)
 *   • metadata    → `err.options?.metadata`  (nested under `options`, not top-level)
 *   • processorId → `err.processorId`        (this one the spec has right)
 * Reading it the spec's way would classify every thrown tripwire as
 * `{reason: undefined, metadata: undefined}` — a block with no reason and no
 * obligation ids, which §10's soundness check would then reject as "unsound
 * metadata". Flagged, not silently accepted: see the report for this task.
 */
import { TripWire } from "@mastra/core/agent";

/**
 * The common core both callers map from — deliberately NOT either caller's shape.
 *
 * `{tripped: true}` carries no text on purpose: the blocked draft travels in the
 * tripwire's `metadata.blocked_draft` (§9c is the only place that sets it), which is
 * where §10's `buildBlockedResult` reads it from.
 */
export type TripwireOutcome =
  | { tripped: true; reason: string; processorId: string; metadata: unknown }
  | { tripped: false; text: string };

/**
 * Structural, not an imported Mastra type: it is the minimum this helper reads, so a
 * stub satisfies it as honestly as a real `generate()` result does. A real
 * `agent.generate()` return is assignable to it — `tripwireContainment.test.ts`
 * proves that by passing one.
 */
export type DeliveryCallResult = {
  text: string;
  tripwire?: {
    reason: string;
    retry?: boolean;
    metadata?: unknown;
    processorId?: string;
  };
};

/**
 * Mastra types `processorId` as OPTIONAL on both tripwire forms, while the spec's
 * `TripwireOutcome` (and both callers) require a `string`. Every abort path in
 * @mastra/core 1.51.0 passes `processor.id`, so this is unreachable in practice — but
 * it is typed reachable, and fabricating a plausible id would be worse than naming the
 * gap. Flagged rather than silently reshaped.
 */
const UNKNOWN_PROCESSOR_ID = "unknown";

/**
 * The ONE owner (§8's module table wrongly claims this for `carverGuardrail.ts` too —
 * flagged, see the report; `carverGuardrail.ts` does not import this module).
 *
 * `instanceof` ONLY — deliberately no structural/duck-typed fallback. The two failure
 * directions are NOT symmetric:
 *   • false NEGATIVE (a real block re-thrown as an error) fails LOUDLY — a red test,
 *     a failed step. Recoverable.
 *   • false POSITIVE (a genuine crash reported as "the guardrail blocked it") fails
 *     SILENTLY, and is precisely the inversion this module exists to prevent.
 * A looser check buys robustness in the safe direction at the price of risk in the
 * catastrophic one. Note `TripWire`'s `.name` is `"Error"`, so name-sniffing would be
 * wrong anyway.
 */
export function isTripWireError(err: unknown): err is TripWire {
  return err instanceof TripWire;
}

/**
 * Runs `call` and answers exactly one question: was this delivery TRIPPED (the
 * guardrail correctly blocked it) or DELIVERED — re-throwing anything that is neither.
 */
export async function normalizeDelivery(
  call: () => Promise<DeliveryCallResult>,
): Promise<TripwireOutcome> {
  try {
    const result = await call();

    // Layer 1 — the RETURNED form. Verified above: this is what actually happens on
    // the generate() + processOutputResult path in @mastra/core 1.51.0.
    if (result.tripwire) {
      return {
        tripped: true,
        reason: result.tripwire.reason,
        processorId: result.tripwire.processorId ?? UNKNOWN_PROCESSOR_ID,
        metadata: result.tripwire.metadata,
      };
    }
    return { tripped: false, text: result.text };
  } catch (err) {
    // Layer 2 — the THROWN form. Reading the REAL TripWire shape, not the spec's.
    if (isTripWireError(err)) {
      return {
        tripped: true,
        reason: err.message,
        processorId: err.processorId ?? UNKNOWN_PROCESSOR_ID,
        metadata: err.options?.metadata,
      };
    }
    // A genuine, unrelated failure. NEVER swallowed, never dressed up as a block —
    // re-thrown untouched, with its original stack.
    throw err;
  }
}
