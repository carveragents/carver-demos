# Stage 01 — Spec: Carver × Mastra Compliance Guardrail (RESUMED RUN)

## Read this first — this is a RESUMED run, not a fresh start

A previous run of this exact stage produced a **substantially complete, heavily hardened
spec over 5 maker/checker rounds**, then hit its round cap (5) before the last issues
could be closed. It STALEMATEd on the **cap**, not on disagreement — the checker's closing
note states the remaining issues "require another revision beyond the configured five-round
cap." The issue count fell **10 → 7 → 6 → 5 → 5** across those rounds: it was converging.

**Your round-1 draft is a REVISION of that spec, not a rewrite.**

1. Take `_inputs/spec-seed.md` (2,980 lines / 24,276 words — the round-5 artifact) as your
   **baseline**. Start from it verbatim.
2. Revise it to close the **5 open issues** in `_inputs/spec-open-issues.md`.
3. Write the result to `artifact.md` (and `rounds/001-draft.md` per protocol).

**Do NOT rewrite from scratch. Do NOT reorganize for taste.** Five rounds of adversarial
review are embedded in that document; a rewrite would silently drop them and restart the
convergence you are inheriting. Change what the open issues require, and what those changes
force. Nothing else.

## Do not regress what the checker already credited

Each round's feedback explicitly credited improvements. **These are now load-bearing and
must survive your revision.** Non-exhaustive, compiled from rounds 2–5:

- The **non-recursive `judgeAgent`** — the guarded agent must never be the internal verdict
  caller (round 2 caught real infinite recursion here).
- The **broken judge dependency cycle** (neutral judge-contract module imported by both).
- **One-call** Stage B / guarded eval paths (no double invocation).
- Stage B scoring **constrained to provably-attributable claims**; **honest abstentions
  excluded** from the failure bar (`citation_missing`/`date_missing` are NOT failures).
- The **date upper bound** from the pinned snapshot date (kills the 2569-style rot).
- The **exact snake_case cleared-record seam**; **no-edit** human review; the **anti-padding
  table**; **immutable snapshot / failure-bar floors**; **price floors**.
- Complete **Scenario A jurisdiction rule** and **Scenario B financial∧promotional
  conjunction** rules.
- **Winner-derived** demo/template config generation (no hand-picked or A-specific defaults).
- **Pinned-clock** narrowing (no moving `now`); cross-language **model drift test**.
- **Discriminated blocked/pass** schemas; the concrete **audit writer** wired to
  `onViolation`; the real **`blocked_draft`** + regulator field carried to the report.
- **Complete request-payload reservation**; poisoned-ledger stop behavior.
- **Deterministic ascending-id** trigger selection.

If closing an open issue genuinely requires changing one of the above, say so explicitly in
a callout and explain why — do not silently revert it.

## The 5 open issues to close (full text in `_inputs/spec-open-issues.md`)

1. **Trigger / guarded-eval conflate different failure modes (the substantive one).** A
   record admitted solely for `citation_fabricated` or `date_wrong` proves a **Stage B
   knowledge** failure — NOT that its Stage A draft violates an obligation. Yet
   `emit_template_config` may pick such a record as the demo trigger, and `runGuardedEval`
   expects the guardrail to block Stage A for **every** cleared record. Top-5 narrowing
   validation cannot prove the verdict will trip. **As written, the live demo and the ≥0.9
   guarded score can fail while the system behaves exactly per its own curated evidence.**
   The trigger must come from records with **human-confirmed `missed_obligation` evidence**
   (and fail loudly if none exist); guarded catch-rate must use only records whose evidence
   predicts a Stage A violation, or define evidence-specific expectations.
2. **`firmProfileForRecord()` cannot narrow-match every record.** Scenario B eligibility has
   no jurisdiction predicate, so a valid record may have `jurisdiction.country` AND `.bloc`
   both null; the synthesized profile uses `country: ""` while `jurisdictionMatches()`
   requires a non-null country or bloc — such a record can never pass narrowing. Add a
   deterministic usable-jurisdiction eligibility requirement or a sound scope-aware
   narrowing/profile rule. Test the null-country/null-bloc case.
3. **The batching loop violates its own hard caps.** `target_set_size` / `probe_max_records`
   are checked only after a full 40-record batch, so `survivors` can exceed the 200 ceiling
   (goal #11) and `probed` can exceed the 400 sweep cap (rubric 12). Stop/slice at the exact
   per-record boundary (budget may still stop mid-record). Test batches crossing each cap by one.
4. **Judge confidence is unbounded.** `JUDGE_RESPONSE_SCHEMA` and its Zod mirror accept any
   JSON number; values <0 or >1 pass validation and distort failure strength and enforcement.
   Constrain to `[0, 1]` in both; validate/fallback consistently in `parse_and_validate_verdicts`.
5. **The hard-budget proof overclaims.** `json.dumps(payload)` is not the exact wire request
   (the SDK serializes and may add framing). Reserve from the SDK-ready complete kwargs plus a
   defined conservative provider-overhead allowance, or a provider-enforced input cap — rather
   than claiming equality with the transmitted request. (Checker rates this secondary to 1–3.)

## Authoritative inputs

- **The goal** (binding; every locked decision in it): `goal.md`
- **The baseline to revise**: `_inputs/spec-seed.md`
- **The issues to close**: `_inputs/spec-open-issues.md`
- **The original full task** (all 15 required sections — still binding): `_inputs/spec-task-original.md`
- Corpus / schema / conventions: as listed in `_inputs/spec-task-original.md`

## Still binding, unchanged

The **entire original task** (`_inputs/spec-task-original.md`) and the **entire rubric**
(`rubric.md`) remain in force. All 15 sections must still be present and substantive; every
locked decision in `goal.md` still governs; no placeholders, no TBDs, no contradictions. The
seed already satisfies most of this — your job is to close the gap, not to re-establish it.

If you believe a goal decision is wrong, raise it as an explicit **"goal issue"** callout.
