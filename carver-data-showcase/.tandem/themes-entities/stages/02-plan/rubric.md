# Rubric — Stage 02 PLAN (Themes & Entities)

The checker judges every plan draft against these criteria. APPROVED only when all are satisfied
(or a gap is explicitly justified as out-of-scope). The plan must be executable top-to-bottom
without re-deciding any design — it implements the **approved** `stages/01-spec/artifact.md`.

1. **Faithful to the approved spec** — Every step traces to the spec and **cites** its
   section(s). No step invents, alters, or drops a design decision (taxonomy, artifact schemas,
   batch mechanics, alias merge, chart/slide content, aggregate-only behaviour). No contradictions
   with the spec or `goal.md`.

2. **Dependency-ordered & incremental** — Phases/steps are sequenced so each builds only on
   already-green prior steps (foundation/config → extract → classify → rollup → charts → load →
   gallery → deck → live run → verify). No forward dependencies.

3. **Test-driven, every code step** — Each code-creating/-changing step names the **test(s) to
   write FIRST** (file + specific cases) before the implementation. The TDD discipline is explicit,
   not implied.

4. **No live OpenAI in tests** — All tests for `classify_entities` (request-builder, parser,
   detect→retry→fallback, resume-or-submit sidecar, incremental cache, `--sample`) use a **stubbed
   client / no network**. The plan states this for each such test.

5. **Per-file change list is concrete** — Steps name exact paths created/edited matching spec §7 +
   Appendix A: 3 new tools, the 3 new test files, edits to `config.py`, `load.py`, `charts.py`,
   `deck.py`, `apps/gallery.py`, `requirements.txt`, and the extended `tests/test_charts.py` /
   `test_gallery_smoke.py` / `test_deck.py`.

6. **Each step is independently verifiable** — Every step states its **acceptance command(s)**
   (e.g. the exact `pytest` target) and what "green" looks like, so progress is checkable.

7. **Hard spec behaviours have build+test steps** — Concretely covered, each with a test:
   (a) **resume-or-submit** Batch sidecar + hash-mismatch resubmit (§4.4); (b) **detect→retry→
   fallback** with the `Other` fallback after `MAX_RETRIES` (§4.3); (c) **alias merge** +
   `_clean_canonical` AND the **breakdown-unchanged-by-merge** invariant (§4.5); (d) **per-occurrence
   `count`** (§3.1); (e) **deterministic chunking order** (§3.1 tie-break); (f) **graceful absence**
   (gallery hides tab / deck composes 8-slide list) (§5.3–5.4, §7); (g) the **two-chart** deck slide
   composition (§5.4); (h) **coverage tiles** (§5.2).

8. **The single live step is isolated & flagged** — The real enrichment run (extract → **Batch**
   classify, ~$1, key from `.env` → build stats) is called out as the ONLY network/cost step,
   sequenced AFTER all unit tests are green, with a `--sample` dry-run first. The plan never makes
   a green test depend on it.

9. **Constraints encoded** — The plan enforces: secrets only in `tools/classify_entities.py`
   (`carver_showcase/*` + `apps/*` never import `openai`); **Cockpit untouched**; categories stay
   internal; **nothing committed**; right-sized models for any subagent; **python-code-reviewer**
   run after code changes (a named final step).

10. **Final verification step exists** — A closing phase: full `pytest` green, python-code-reviewer
    clean, live gallery shows the tab, deck rebuilds to 9 slides, cockpit confirmed unchanged,
    nothing committed. Acceptance is concrete.

11. **Right-sized & self-contained** — Steps are small enough to implement+review in isolation
    (no mega-steps bundling unrelated files); large units (e.g. `classify_entities`) are split into
    sensibly-scoped sub-steps. No placeholders/TBDs in load-bearing steps.

12. **Internal consistency** — Self-consistent ordering, file lists, and acceptance commands; the
    test inventory matches the spec §8.2 test surface; no step references a file/symbol the spec or
    a prior step didn't establish.
