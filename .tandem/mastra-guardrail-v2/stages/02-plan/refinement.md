# Refinement 2 — 02-plan (ONE bug in P8.0. Nothing else.)

Refinement 1 landed well. G1–G9 are closed, and two fixes exceed what was asked: the `unit:`
allowlist selector genuinely runs the deterministic cases from both file-level-excluded suites at
zero cost, and P8.0's gate is bound to a **digest of the cleared set**, so a re-curated set voids
an old acknowledgment automatically. The round-6/7 checker rounds were excellent — catching that
round 5's first gate *"delivered a paragraph with a `sys.exit` in it"*, and that a proposed Verify
command *"names a real other file that passes and proves nothing"*.

**This cycle fixes one bug and one sentence. Change nothing else.** No restructuring, no
renumbering (§0's own note: renumbering Phase 6 has already caused two defect rounds here).

---

## BLOCKING — one bug, found by executing the gate

**Y1. `user_instruction: ""` passes the gate. It must not.**

The orchestrator extracted P8.0's command verbatim and ran it against fixtures. **The six cases the
plan claims were tested all pass** — including the digest binding (a *different* 14 records
correctly exits 3). But an untested case fails:

| case | expected | actual |
|---|---|---|
| `user_instruction: ""` (empty, all other fields correct) | **3** | **0** ❌ |

**Why.** `field()`'s regex `^user_instruction:[ \t]*(.+?)[ \t]*$` captures the two literal quote
characters, so `field('user_instruction')` returns the 2-character string `""` — which is
**truthy**. `if not (field('user_instruction') or '')` therefore never fires, no problem is
appended, and the gate exits 0.

**Why it matters.** `survivor_count` and `set_digest` can both be *computed* by whatever is running
the plan. `user_instruction` is the **only** field in the artifact that can only come from a human
having actually answered — the plan's own words: *"must quote the user verbatim"*, and *"The only
unlock is an artifact recording a real human answer about a real dataset."* As written, the field
that carries the human is the one field not enforced.

**Fix:** strip surrounding quotes/whitespace before the emptiness check (e.g.
`(field('user_instruction') or '').strip('"\'' ).strip()`), so an empty or quote-only value is a
problem. Then **actually execute** it against at least: `""`, `''`, a whitespace-only value, a
quote-only value, and a real instruction. Also confirm the passing cases still pass — the digest
and count bindings are correct and must not regress.

**And correct the claim.** P8.0 states *"This command was executed against fixtures before being
written down, not reasoned about."* For six cases that is true and verified. For this one it was
not. Either extend the fixture list to cover it and keep the claim, or soften the claim — but do
not leave a claim of empirical testing standing over an untested branch, in the one task whose
whole argument is *mechanism over assertion*.

## MINOR — one sentence

**Y2.** P8.0's quoting-bug note says a `\$` mis-escape *"would silently make every field read
`None` and turn the gate into a **rubber stamp** that always exits 3."* A gate that always exits 3
blocks **everything** — that is a false alarm, fail-closed, the opposite of a rubber stamp. The
mechanism is right and fail-closed is the correct direction; only the label is wrong. Fix the word.

## Standing

`goal.md` is the authority. `01-spec` is APPROVED and **refine-capped** — the plan may not edit it;
any spec defect is a **"spec issue" callout**. Everything refinement 1 closed stays closed: the
`unit:` selector, the digest binding, the generated/hand-authored preservation contract, the
P6.12a/b split, the Verify defaults and their deviation table, the re-export/`conftest.py`/golden
groups/Phase-3-4 gate owners. Do not reopen them.
