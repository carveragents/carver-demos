# Refinement — Stage 01 SPEC (cycle 1)

A grounded stress-test (`stress-test/001-*`) of the APPROVED spec surfaced **four Stage-01-scope
gaps**. Revise the EXISTING `artifact.md` to close them — keep everything else intact (the spec is
otherwise approved). The checker will re-review against the original rubric **plus** "are these
four gaps closed." Do not relitigate settled decisions; just close the gaps below.

---

## GAP-1 (High) — Async-batch resumability + deterministic chunking  [§4.4, §4.5, §3.1]

**Problem.** The full run submits ONE async Batch job and polls until complete, but idempotency is
defined only on `entity_types.csv`, which is written *after* fetch. If the process dies (or the
machine sleeps) between **submit** and **fetch**, a re-run sees the in-flight entities still
missing from the cache and submits a **second, duplicate Batch job** — re-spending and re-waiting.
Separately, the `custom_id → entity-list` map is "re-derivable from deterministic chunking," but
`entity_mentions.csv` pins no tie-break, so equal-`count` rows can reorder between runs and break
the `chunk-{i}` → entity mapping after a fresh process.

**Close it by specifying:**
1. **Persist the in-flight batch.** When a Batch job is submitted, write a small sidecar state
   (e.g. `data/entity_batch_state.json` — name it) holding at least the `batch_id`, the input
   file path, the model, and a content hash / row-count of the exact distinct-entity input set.
   On startup, `classify_entities` checks for this sidecar **before** submitting: if a live
   `batch_id` exists, it **resumes** (polls/fetches that job) instead of submitting a new one; it
   clears the sidecar only after the output is successfully fetched and merged into
   `entity_types.csv`. A terminal `failed`/`expired` batch clears the sidecar and may resubmit.
2. **Deterministic total order.** State that `entity_mentions.csv` is written in a **fully
   deterministic order** (e.g. `count` desc, then `entity` ascending as a stable tie-break) and
   that chunking consumes that file in order, so `chunk-{i}` → entity list is reproducible across
   processes from the file alone (no reliance on in-memory state surviving).
3. Note this makes the classify step **safely re-runnable** — at most one live Batch job per
   distinct-entity input set.

Keep it a design decision (what state is persisted, when it's read/cleared, the ordering
guarantee); exact serialization is a Stage-02/impl detail.

## GAP-2 (Medium) — Decide the deck slide's concrete composition  [§5.4, task §4]

**Problem.** §5.4 lists the three builders + tiles + callout but never decides what the single
new 8→9 deck slide actually shows or how it's laid out on a fixed 960×540 16:9 page. Existing deck
slides fit roughly **two** half-width charts; three charts + tiles + callout is unspecified and
likely cramped. "Define the deck slide / what each surface shows" is Stage-01 scope.

**Close it by deciding** (and writing into §5.4) the slide's concrete content and a legible
layout — e.g. which charts appear at deck fidelity (a curated subset such as the **entity type
breakdown** + the **entity leaderboard**, with **tag** richness carried as a KPI tile / callout
line rather than a third full chart), versus the gallery tab which keeps all three. State the
arrangement at the same granularity the rest of §5 uses (half-width chart placement + tiles +
callout), and that the slide reuses the shared builders so it still can't drift from the gallery.
The gallery tab content (§5.3) is unchanged — this gap is only about the fixed deck slide.

## GAP-3 (Low) — Resolve coverage-% surfacing  [§3.8, §5.2, §8.3]

**Problem.** §3.8 and §8.3 say field coverage % (tags 88.5% / entities 92.5%) is "derived live in
the apps," but the §5.2 tile inventory omits it — so it's computed but never shown (or the §3.8
claim is vestigial). `goal.md` flags coverage as a headline fact.

**Close it by** making the spec self-consistent: either (preferred) add coverage % to the §5.2
headline tiles / diversity line (and keep the §3.8 derived-live description), or remove the
"coverage %" from the derived-live list in §3.8/§8.3. Pick one and make §3.8, §5.2, §8.3 agree.

## GAP-4 (Low) — Pin the "mentions" definition  [§3.1, §2.1]

**Problem.** §3.1 defines `count` as "number of records that mention it" while §2.1 accumulates a
`Counter` over each record's entity/tag list (per-occurrence). These disagree on within-record
duplicates.

**Close it by** stating one precise definition and making §2.1 and §3.1 agree — e.g. "`count` =
total occurrences across the corpus (a `Counter` over list items); within-record duplicates are
rare and counted per-occurrence," OR "deduplicate each record's list first → `count` = records
mentioning the term." Either is fine; just make it explicit and consistent (it's the
leaderboard/breakdown weight).

---

**Out of scope for this refinement:** everything not listed above is already approved — don't
rewrite it. No new features, no taxonomy changes, no scope expansion.
