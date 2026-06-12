# Stress-test 002 — Stage 02 PLAN (Themes & Entities)

Orchestrator-driven grounded interrogation of `stages/02-plan/artifact.md`, sourced ONLY from the
plan + the approved spec + `goal.md`. In-scope-uncovered → GAP; deferred/out-of-scope → not a gap.

---

**Q1. Is every hard spec behaviour actually built AND tested, or just mentioned?**
A: Covered — the plan's traceability table (lines 413-423) maps each of (a) resume-or-submit
sidecar, (b) detect→retry→fallback, (c) alias merge + breakdown-invariant, (d) per-occurrence
count, (e) deterministic chunk order, (f) graceful absence, (g) two-chart deck slide, (h) coverage
tiles to a concrete build step AND a test step. Spot-checks confirm: GAP-1 → Step 2.4 (submit-fresh
/ resume / hash-mismatch / clear / cache), GAP-2 → Step 7.2 (two half-width charts + tag callout),
breakdown-invariant → Step 3.1. **Not a gap.**

**Q2. Does any green unit test depend on the live OpenAI run?**
A: No — every OpenAI-touching test (Phase 2) injects a stubbed client; the live run is isolated in
Phase 9, sequenced AFTER the Phase 8 whole-suite-green gate, and Phase 8/10 re-assert green
independently. `grep -rn "import openai" carver_showcase apps` → none is an explicit acceptance
(Steps 2.5, 8.1). **Not a gap.**

**Q3. Where does the spec's one deferred item — final prompt copy — get resolved?**
A: Step 9.2 (`--sample 100`) is the prompt-iteration loop ("iterate the prompt copy here until the
sample looks right") before the full Batch run in 9.3. So the only spec deferral lands in an
explicit plan step. **Not a gap.**

**Q4. Is the Cockpit/categories/no-commit boundary enforced, not just stated?**
A: Step 10.4 asserts `apps/cockpit.py` shows **no diff**, `git status` shows only intended files,
nothing committed; Step 6.2 keeps the "no Category filter" assertion. Concrete acceptance, not
prose. **Not a gap.**

**Q5. Async Batch could take up to the 24h window — does the plan handle a slow/interrupted job?**
A: Step 9.3 — "If interrupted, re-run the same command; it resumes the in-flight job (no duplicate
submit)." Backed by the Step 2.4 sidecar tests. Polling cadence is an impl detail, not a design
gap. **Not a gap.**

**Q6. Does `_build_context` blow up when term stats are absent (deck path)?**
A: Step 7.1's "without term stats → 8 slides, no exception" test enforces the guard; Step 7.2 loads
via `load_term_stats()` inside `build_deck` and composes the active slide list only when present.
**Not a gap.**

**Q7 (nits). Two cosmetic doc-inconsistencies in the plan.**
A: (i) Step 0.2 creates `tests/test_config_term_stats.py`, but the "Test inventory" table
(lines 30-39) omits it. (ii) `tests/test_load_term_stats.py` is in the plan's inventory though the
spec §8.2 folds load-graceful into §7 rather than listing it. **Both are cosmetic** — they don't
change a single executable step, file path, or acceptance command; the plan still executes
top-to-bottom correctly. **Recorded as accepted/non-blocking — NOT worth a refinement round**
(YAGNI; re-running the maker/checker loop to fix a table would be make-work).

---

## Verdict
**No actionable in-scope gaps.** The plan is faithful to the approved spec, fully executable, and
encodes every constraint with concrete acceptance. Two cosmetic table nits accepted as
non-blocking. No more stages to add (scope was spec → plan). **Decision: `--finish` the pipeline.**
