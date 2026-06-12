# Stage 02 — PLAN: Themes & Entities phased implementation plan

## What to produce (this stage)

A **dependency-ordered, test-driven, phased implementation plan** that an implementer (or a
subagent-driven-development loop) can execute step-by-step to build exactly what the **approved
Stage 01 spec** decides — with **no design re-litigation**. This stage produces the *build
sequence and the per-file / per-test change list*; it does NOT re-open any design decision.

**Read first (carried forward):**
- `stages/01-spec/artifact.md` — the APPROVED spec (the single source of design truth). Every
  plan step must trace to it; cite spec sections (e.g. "§4.4", "§5.1").
- `goal.md` — the overall brief, locked decisions, and inherited project constraints.

The plan must be concrete enough that an implementer never has to decide *what* to build — only
to write the code/tests each step names.

## Required shape of the plan

Organize as **ordered phases**, each phase a small set of **steps**. Every step that creates or
changes code MUST be **test-driven and independently verifiable**:

- **TDD per step:** name the test(s) to write FIRST (file + the specific cases), then the
  implementation to make them pass. Tests for any OpenAI-touching code use a **stubbed client —
  NO live API call** (per spec §4.3, §8.2).
- **Files touched:** list exact paths created/edited (matching spec §7 + Appendix A).
- **Acceptance:** the command(s) that prove the step done (e.g. `.venv/bin/python -m pytest
  tests/test_extract_terms.py`), and what green looks like.
- **Traceability:** the spec section(s) the step implements.

Sequence so each phase builds only on already-green phases. A suggested spine (the maker may
refine ordering, but must cover all of it):

1. **Foundation** — `requirements.txt += openai` (+ install into `.venv`); `config.py` additions
   (paths, `ENTITY_TYPES`/`ENTITY_TYPE_DEFINITIONS`/`ENTITY_TYPE_COLORS`, model/chunk/top-N
   constants) per spec §7/§4.1. (Constants are logic-free; a light import test is enough.)
2. **`tools/extract_terms.py`** — TDD: counting over a tiny temp JSONL; per-occurrence `count`
   (§3.1/§2.1); whitespace-trim/empty-drop; missing/non-list fields skipped; deterministic output
   order (`count` desc, then term asc). (Spec §2.1, §3.1–3.2.)
3. **`tools/classify_entities.py`** — TDD with a STUBBED client: request-builder (deterministic
   ~50-chunking, `custom_id` format, body shape, taxonomy present); response-parser (`custom_id`→
   entities, schema validation); **detect→retry→fall back** (§4.3) incl. the `Other` fallback
   after `MAX_RETRIES`; **resume-or-submit** sidecar `entity_batch_state.json` logic (§4.4) incl.
   hash-mismatch resubmit + clear-on-terminal; incremental cache set-difference (§4.5); the
   `--sample N` sync path. (Spec §4.)
4. **`tools/build_term_stats.py`** — TDD: breakdown (sum mentions, count distinct once, all 6
   present zero-filled); **alias merge** by `_clean_canonical` (`U.S. ` strip, case/punct/
   whitespace) with the **breakdown-unchanged-by-merge** invariant; leaderboards top-50; meta JSON
   keys. (Spec §3.4–3.7, §4.5.)
5. **`carver_showcase/charts.py`** — TDD (extend `tests/test_charts.py`): the 3 builders
   (`fig_entity_type_breakdown`, `fig_entity_leaderboard`, `fig_tag_leaderboard`) incl. the
   defensive `_empty_fig` path; add to `__all__`. (Spec §5.1.)
6. **`carver_showcase/load.py`** — TDD: `load_term_stats()` returns the dict when artifacts exist
   and `None` when core artifacts absent (graceful). (Spec §7.)
7. **`apps/gallery.py`** — the conditional 9th "Themes & Entities" tab (tiles incl. coverage,
   3 charts, full-corpus caption, alias caveat); reads `df_full` not `view`. Smoke test: tab
   present+renders with artifacts; **gracefully absent** without them. (Spec §5.2–5.3, §6.)
8. **`carver_showcase/deck.py`** — `_slide_themes_entities` (the **two-chart** curated slide +
   tag KPI/callout per §5.4), `_build_context` extension, runtime active-slide-list compose;
   update `tests/test_deck.py` page-count to the active-slide count. (Spec §5.4.)
9. **Operational enrichment run (the ONE live step)** — run `extract_terms` → `classify_entities`
   (the real OpenAI **Batch** job, ~$1, `OPENAI_API_KEY` from `.env`) → `build_term_stats` to
   generate the real artifacts. Call this out explicitly as the only step that hits the network /
   spends money; everything testable above is already green without it. Include how to dry-run
   with `--sample` first.
10. **Final verification** — full `pytest` green; run **python-code-reviewer** on all new/changed
    Python and fix findings (per CLAUDE.md); live gallery (`:8501`) shows the tab; deck rebuilds
    to 9 slides; confirm cockpit (`:8502`) unchanged. Nothing committed.

## Hard constraints (the plan must encode, not just mention)

- **TDD everywhere**; **no live OpenAI call in any test** (stubbed client).
- **Secrets only in `tools/classify_entities.py`**; `carver_showcase/*` + `apps/*` never import
  `openai`.
- **Gallery + deck only — do NOT touch the Cockpit**; categories stay internal.
- **No commit** — all work stays uncommitted (flux merge is the user's).
- **Right-sized models** for any subagent dispatch; **python-code-reviewer** after code changes.
- Build **iteratively** — each step green before the next.

## Out of scope (this stage)

- Re-deciding any design (taxonomy, schemas, batch mechanics, chart/slide content) — all settled
  in the approved spec; cite it, don't change it.
- Writing the actual implementation code (that's execution, after this plan is approved).
- Re-pulling data; any Cockpit/category change.

The plan is APPROVED when an implementer could execute it top-to-bottom — writing each named test
then its implementation — and arrive at the spec's feature with full test coverage, without making
a single design decision the spec didn't already make.
