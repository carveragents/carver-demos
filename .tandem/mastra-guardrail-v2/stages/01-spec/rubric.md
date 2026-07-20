# Rubric — Stage 01 Spec: Carver × Mastra Compliance Guardrail

The spec (`artifact.md`) is APPROVED only when ALL criteria hold. Otherwise
CHANGES_REQUESTED with specific, numbered, actionable issues.

## Completeness
1. All 15 required sections from the task are present and substantive.
2. Every module in the layout has its public functions/exports named, with signatures,
   return types, purpose, and dependencies — an engineer could implement it without guessing
   an interface.
3. The **cleared-record schema** (task §5) is pinned exactly — every field, type, provenance
   — including baseline-failure evidence, human-review sign-off, and citation URLs.
4. The full `config.yaml` key set and every env var is specified (key, type, default, effect).
5. Every prompt (probe question, LLM judge, guardrail verdict) has its exact template, every
   placeholder, and its structured-output schema.

## Fidelity to the goal (binding — a violation here is an automatic CHANGES_REQUESTED)
6. Honors every locked decision in `goal.md` verbatim. Spot-check especially:
   - Model is `openai/gpt-5.6-sol` via the router string, ONE shared pinned constant,
     **identical on both sides of the experiment**.
   - **No Anthropic API anywhere** — no key, no `anthropic/*` string, no SDK, no Claude call
     from either half, for any purpose.
   - `OPENAI_API_KEY` is the ONLY secret. No Carver key, no Mastra token/account.
   - Candidate filter is **2026-03-01+** (NOT 2026-02-01) and the spec states the
     2026-02-16-cutoff reason.
   - Severity mapping comes from Carver's `impact_label`, not a hand-invented rule.
   - No RAG / vector store / embeddings anywhere.
   - No custom frontend, no server, no SPA.
7. **The anti-padding asymmetry is specified, not just quoted**: the filter is a floor that is
   never relaxed; set size is a ceiling that may freely shrink. The spec makes padding
   *mechanically hard*, and names the forbidden shortcuts (loosening the cutoff, admitting
   medium/low impact, admitting noisy update_types, accepting unresolvable citations, waiving
   review, weakening the failure bar, synthesizing records).
8. `template/` is specified as genuinely self-contained: vendored data, zero references to
   `prep/` / `carver-showcase` / this repo, runs on `OPENAI_API_KEY` alone, extractable to
   its own repo.
9. `../carver-showcase` is treated as strictly read-only.

## The hard parts (this project fails here or nowhere)
10. **Question generation (task §3) is fully specified**, not hand-waved. It is unambiguous
    whether the probe tests knowledge, drafting behavior, or both-as-stages; the choice is
    justified against the goal's north star; exact prompt templates are given.
11. **Fair-test discipline is explicit**: the probe cannot leak the answer into the question.
    What the prompt may and may not contain is stated.
12. **Sampling + cost control is a first-class requirement**: a stratified, seeded sampling
    strategy over the 8,260 pool; an early-stop condition; a per-record and total call budget;
    a hard spend ceiling; a documented cost estimate. A spec that sweeps the whole pool, or
    leaves cost unbounded, is REJECTED.
13. **Scoring is deterministic wherever the check is deterministic.** Citation-fabrication and
    date-mismatch are string/HTTP checks with precisely defined semantics (including: a model
    naming a real regulation in prose without a URL vs inventing a URL — the spec says which
    counts and why). The LLM judge is confined to the irreducibly fuzzy check only.
14. **The failure bar is precise**: exactly what admits a record. Near-misses provably excluded.
15. **Tripwire containment (task §10) is specified with a verification** that proves the
    guarded branch's abort cannot end the run or kill the baseline branch.
16. **Human review is a hard gate**: an unreviewed record is *impossible* to ship by
    construction, not merely discouraged.
17. **The scenario decision rule (task §7) is mechanical**, decidable without a human, records
    its evidence, cannot stall, and applies the A tie-break.

## Robustness
18. Every stress scenario in task §14 has a specified behavior: empty narrowing result,
    tripwire in parallel, unresolvable URL, garbage/absent ground-truth date, malformed judge
    JSON, **zero probe survivors**, non-ASCII regulator names, duplicates, a citation that
    dies between clearing and demo.
19. Streaming over the 1.8 GB JSONL is specified (never loaded whole). Date rot (1442→2569)
    and `press release` noise are excluded **by construction**, not by hope.
20. Determinism is guaranteed and seeded: the same probe run replays to the same result;
    caching is specified.

## Quality
21. No placeholders, TBDs, internal contradictions, or requirements open to two readings.
22. Honors carver-adhoc conventions: project self-contained under `projects/`; **Python in an
    isolated project-local `prep/.venv`** (never system Python, never a sibling's venv, never
    importing `carver_showcase`); pinned deps; extracted prompts; results-vs-scratch split
    (`data/cleared/` tracked, `data/scratch/` gitignored); no secrets in code; TDD.
23. A project-local `.gitignore` is specified covering `node_modules/`, `.mastra/`,
    `data/scratch/`, `prep/.venv/`, `.env` — with `data/cleared/` tracked.

## Scope discipline
24. Specifies v1 only. Explicitly defers out-of-scope items (RAG, live Carver API, Mastra
    Platform, multi-agent orchestration, building both scenarios) rather than silently
    including or dropping them.
25. Any suspected defect in `goal.md` is raised as an explicit **"goal issue"** callout rather
    than silently worked around.

---

## Resumed-run criteria (this run only — these are ADDITIONAL to everything above)

This stage resumed from a round-5 artifact that STALEMATEd on the round cap, not on
disagreement. The maker's brief was to **revise** `_inputs/spec-seed.md`, not rewrite it.

### The 5 inherited open issues must be closed
26. **Trigger / guarded-eval failure-mode conflation** is resolved: the demo trigger is
    selected ONLY from records carrying human-confirmed `missed_obligation` evidence, and
    fails loudly if none exist; guarded catch-rate evaluation uses only records whose
    evidence predicts a Stage A violation, or defines evidence-specific expectations. A
    record admitted solely for `citation_fabricated`/`date_wrong` can NEVER become the
    trigger, and can never be asserted to trip the guardrail on a Stage A draft.
27. **`firmProfileForRecord()` narrow-match is guaranteed**: no eligible record can exist
    that the synthesized firm profile provably cannot match. The null-`country` +
    null-`bloc` case is handled by an explicit rule and covered by a test.
28. **Hard caps are enforced at the exact record boundary**, not per batch: `survivors`
    cannot exceed the cleared-set ceiling (200) and `probed` cannot exceed the sweep cap
    (400). Tests cover a batch crossing each cap by one.
29. **Judge confidence is constrained to `[0, 1]`** in BOTH the JSON schema and its Zod
    mirror, with consistent validation/fallback in `parse_and_validate_verdicts`.
30. **The hard-budget proof no longer overclaims**: reservation derives from the SDK-ready
    complete kwargs plus a defined conservative provider-overhead allowance (or a
    provider-enforced input cap). It does not claim byte-equality with the transmitted request.

### No regression
31. **The artifact is a revision of the seed, not a rewrite.** Every improvement the previous
    rounds credited still stands — specifically: non-recursive `judgeAgent`; broken judge
    dependency cycle; one-call Stage B/guarded eval paths; Stage B scoring constrained to
    provably-attributable claims; honest abstentions excluded from the failure bar; the
    snapshot-derived date upper bound; the exact snake_case seam; no-edit human review; the
    anti-padding table; immutable snapshot/failure-bar floors; price floors; the Scenario A
    jurisdiction rule and Scenario B financial∧promotional conjunction; winner-derived demo
    config; pinned-clock narrowing; the cross-language model drift test; discriminated
    blocked/pass schemas; the wired audit writer; the real `blocked_draft` + regulator field
    in the report; complete request-payload reservation with poisoned-ledger stop;
    deterministic ascending-id trigger selection.
    Any deliberate change to one of these must carry an explicit callout justifying it. A
    silent revert is an automatic CHANGES_REQUESTED.
32. **Do not re-open settled ground.** Issues resolved in earlier rounds and credited by the
    checker are closed. Raise them again only if the maker's new revision actually broke them.
