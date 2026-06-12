# Stress-test 001 — Stage 01 SPEC (Themes & Entities)

Orchestrator-driven grounded interrogation of `stages/01-spec/artifact.md`. Every answer is
sourced ONLY from the approved spec + `goal.md`, with section citations. In-scope-but-uncovered
→ **GAP**. Deferred-to-Stage-02 / out-of-scope → not a gap.

---

**Q1. Could `SEC` and `Securities and Exchange Commission` still render as two separate
leaderboard bars?**
A: Covered, by design. The leaderboard merges on `merge_key = _clean_canonical(canonical_name)`,
NOT on the raw entity string (§4.5). The model is instructed to return the "full, de-abbreviated,
conventionally-cased name" as `canonical_name` (§4.2), so both `SEC` and the full string should
yield `canonical_name = "Securities and Exchange Commission"` and merge — Appendix B shows exactly
this for `ECB`/`European Central Bank`. The spec states honestly this is "best-effort across
requests" (§4.5): the deterministic cleanup catches case/punct/`U.S. ` variants but not arbitrary
synonyms, and no second LLM pass is added (YAGNI). **Not a gap** — covered with a stated caveat.

**Q2. The full run is one async Batch job. If the tool process dies while polling (or the machine
sleeps) before the output is fetched, what happens on the next run?**
A: §4.4 submits a batch, polls until `completed`, then fetches+writes `entity_types.csv`.
Idempotency (§4.5) is defined ONLY on `entity_types.csv` — which is written *after* fetch. The
spec does **not** describe persisting the submitted `batch_id` or resuming an in-flight job, so a
re-run after an interrupted poll would fall back to the §4.5 set-difference, find the in-flight
entities still missing from the cache, and **submit a second, duplicate Batch job** (re-spending
and re-waiting). The async 24h window makes "process outlives the job" a realistic case. The task
puts the classify tool's batch mechanics in Stage-01 scope (task §1, §4 batch mechanics). **GAP-1
(substantive, in-scope).**

**Q3. The `custom_id → entity-list` map is "held in memory / re-derivable from the deterministic
chunking" (§4.4). After a fresh process fetches a previously-submitted batch, is the mapping
recoverable?**
A: Only if chunking is deterministic over a stable input order. §3.1 sorts `entity_mentions.csv`
by descending count, but does not pin a secondary sort, so **count-ties may reorder** between runs,
breaking the `chunk-{i}` → entity mapping on re-derivation. Tightly coupled to GAP-1 (both are
"survive a process boundary"). **Folded into GAP-1.**

**Q4. What does the new deck slide actually show, and does it fit?**
A: §5.4 says `_slide_themes_entities` is "built from the same three builders +
`_draw_kpis`/`_draw_chart`/`_draw_callout`," implying all three charts + tiles + a callout on one
fixed 960×540 16:9 slide. But the spec never **decides the slide's concrete composition/layout**,
and the task explicitly scopes "define … the deck slide" / what each surface shows to Stage 01
(task §4). Existing deck slides place ~2 half-width charts each (per the established deck pattern);
three charts + tiles + callout on one slide is unspecified and likely cramped. The gallery tab
(scrollable) can show all three; the fixed slide needs a decision (all three small, or a curated
subset with tags as a tile/callout). **GAP-2 (in-scope design decision).**

**Q5. Is field coverage (tags 88.5% / entities 92.5%) shown anywhere?**
A: Inconsistent. §3.8 and §8.3 say coverage % is "derived live in the apps" from the parquet
(`(n_entities>0).mean()`), but the tile inventory in §5.2 lists distinct counts, total mentions,
medians, and a tag-diversity line — **not** coverage %. So coverage is described as computed but
has no stated surface, OR §3.8's "coverage %" claim is vestigial. `goal.md` highlights the
88.5%/92.5% coverage as a headline fact. Either place it in a tile or drop the derived-live claim.
**GAP-3 (internal-consistency, rubric 14).**

**Q6. `count` in `entity_mentions.csv` is defined as "number of records that mention it" (§3.1),
but §2.1 accumulates a `collections.Counter` over each record's entity *list*. If one record's
list contains the same entity twice, is that one or two?**
A: The two sections disagree at the margin: §3.1 says per-record ("records that mention"); §2.1's
Counter-over-list-items counts per-occurrence. In practice intra-record duplicates are rare, so
the totals barely move — but the definition is load-bearing for "mentions" (it's the leaderboard
and breakdown weight). The spec should state precisely whether a within-record duplicate counts
once or per-occurrence, and make §2.1 and §3.1 agree. **GAP-4 (precision/consistency, rubric 3 &
14).**

**Q7. Does classifying all 281K distinct entities — incl. ~70% singletons — actually serve the
views, or is that waste?**
A: Covered. The 6-bucket breakdown counts distinct entities and sums mentions across ALL entities
(§3.4, §4.5), so every distinct entity must be typed for the breakdown to be complete and honest;
the leaderboard then needs only the head, but it's drawn from the same typed set. Cost is ~$1 for
the full set (§4.6). Matches `goal.md`'s "type the whole corpus." **Not a gap.**

**Q8. Batch job `failed`/`expired` — handled?**
A: Covered at the job level: §4.4 step 3 "(or `failed`/`expired` → surface + stop)." Per-chunk
errors inside a `completed` batch flow through detect→retry→fallback (§4.3). The only hole is
re-submission after an interrupted *successful-but-unfetched* job — that's GAP-1, not this.
**Not a gap (beyond GAP-1).**

**Q9. Person leaderboard externally — privacy?**
A: `goal.md` states entities are annotation content and fine to show externally; the examples are
public officials named in regulatory text. A product judgment, already endorsed by the locked
taxonomy including `Person`. **Not a gap.**

**Q10. Graceful degradation, cockpit isolation, secrets-in-tools, no-commit, categories-internal?**
A: All covered: §5.3/§5.4/§7 (hide tab / compose 8-slide list when artifacts absent), §8.1
(cockpit untouched; `OPENAI_API_KEY` only in `classify_entities.py`; categories never surfaced;
artifacts git-ignored; no commit). **Not gaps.**

---

## Verdict
Spec is strong and ~90% build-ready. **Four grounded gaps** to close before advancing — see
`001-gaps.md`. All four are Stage-01-scope (classify-tool design, deck-surface definition, two
internal-consistency tightenings); none are Stage-02 deferrals or out-of-scope.
