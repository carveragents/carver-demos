# Stress-test 001 — stage 01-spec (orchestrator-driven, grounded)

Self-driven grounded stress-test of the APPROVED spec (`stages/01-spec/artifact.md`).
Questions were formed using a real coverage/anomaly probe of the snapshot
(`_src/real-coverage-findings.md`); ANSWERS come only from the approved artifact + `goal.md`.
Deferred-to-stage-02 items are not gaps.

**Q1. Does the spec keep the data pull on the direct Artifacts API and apps off the live API?**
A: Covered. §2.2 (Artifacts API, offset-paginated, snapshot to JSONL; "apps never call the live
API on render"), §9.1. ✔

**Q2. Is the no-LLM constraint provably honored for every derived signal?**
A: Covered. §5 defines richness score, quality predicates, anomaly rules, curation as explicit
formulas/thresholds; each LLM-tempting spot is named and routed to §10. ✔

**Q3. Does the Gallery cover range AND quality AND richness; the Cockpit coverage/gaps/anomalies/triage?**
A: Covered. §6.2 tags each view RANGE/QUALITY/RICHNESS incl. the full single-record drill-down;
§7 covers coverage matrix, cleanup queue, anomaly panel, field-health, trend, migration tracker. ✔

**Q4. Does the design surface honest coverage and a sampling caveat?**
A: Covered. §8 (one metrics source, real %s, empty sections hidden) and §2.2 sampling banner. ✔

**Q5. (GROUNDED) The goal names "3 categories" as a primary RANGE axis, and the spec has a
"Category → topic structure" RANGE view (§6.2 v2) + category-sliced coverage (§7.1). Does the
snapshot the spec commits to actually CONTAIN the 3 categories?**
A: **NOT covered — GAP.** §2.2/§2.3 commit to a *60K contiguous offset slice (403/1,087 topics)*.
A real probe of that slice shows it is **~99% Finance, Data protection ≈ 2%, Medical Devices = 0
records**. So the category→topic view and category-sliced coverage would render with **one**
category — they cannot demonstrate range ACROSS the 3 categories, which is the #1 objective. The
spec's own §6.2-v2 / §7.1 promises are unmeetable on the committed snapshot.

**Q6. (GROUNDED) Where does `category` come from? §4.2/A3 says
`classification.category` → sidecar CSV → "Uncategorized".**
A: **Partially covered — GAP.** A probe confirms `category` is NOT in the annotation payload
(0/58,982) and the topics catalog's per-topic `category` field is null, so A3 collapses to
**100% "Uncategorized"** unless a sidecar is built. The spec names a sidecar but does not commit to
producing it, leaving category effectively empty. (Recovery exists: `/api/v1/feeds/categories/
{id}/topics` returns each category's topics — a direct GET sanctioned by `data-access.md` — so a
real topic→category map IS buildable. The spec doesn't adopt it.)

**Q7. Minor: §2.1 lists `reconciled_published_date { value, … }`. Real field?**
A: Minor inaccuracy — the real field is `date`, not `value` (§4.2 derives it correctly). Worth a
one-line fix during refinement.

## Verdict
Two confirmed, related in-scope GAPs (Q5 data composition; Q6 category sourcing) that block the
spec's own headline range claims, plus one minor field-name fix (Q7). Everything else: covered.
Route to a single refinement of stage 01-spec.
