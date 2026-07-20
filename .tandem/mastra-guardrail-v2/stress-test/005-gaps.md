---
mode: autonomous
stage: 02-plan
stress_test: 005 (orchestrator, by execution)
date: 2026-07-16
---

# Stress-test 005 — the yield gate, verified by running it

## Method

P8.0's command is the mechanical form of the one promise made to the user: stop below ~20
survivors. It was not read — it was **extracted verbatim and executed against fixtures**.

## Y1 — found: `user_instruction: ""` passed the gate (expected 3, got 0)

`field()`'s regex `^user_instruction:[ \t]*(.+?)[ \t]*$` captured the two literal **quote
characters**, so an empty `""` returned the truthy 2-character string `""`, the emptiness check
never fired, and the gate **exited 0** on an artifact carrying no human answer.

**Why it mattered more than its size.** `survivor_count` and `set_digest` can both be *computed* by
whatever executes the plan. `user_instruction` is the only field that can only come from a human
having actually answered. The two machine-checkable fields were enforced provably; the one carrying
the human was silently unenforced — the project's own mechanism-vs-assertion line failing at
exactly the point it mattered most.

**How it survived** a maker, a checker, two stress-test readers, and a plan claiming the command was
*"executed against fixtures… not reasoned about"*: every reader saw `if not (field(...) or '')` and
read the **intent**. Reading tells you what code means; running tells you what it does.

## Fix — verified by execution, APPROVED round 9 first pass

`field()` now strips surrounding quotes/whitespace via `\x22`/`\x27` hex escapes (so no quote
literal must survive the shell's own quoting — sidestepping the very bug class that caused this),
and the check is a plain `if not field('user_instruction')`. The fixture matrix went 6 → 15.

**Orchestrator re-verification — 16 cases, all correct:**

| | case | expect | got |
|---|---|---|---|
| bug | `user_instruction: ""` | 3 | 3 ✅ |
| bug | `user_instruction: ''` | 3 | 3 ✅ |
| bug | `user_instruction: "   "` | 3 | 3 ✅ |
| bug | `user_instruction:` (bare) | 3 | 3 ✅ |
| regression | 14 + no artifact | 3 | 3 ✅ |
| regression | stale `survivor_count: 99` | 3 | 3 ✅ |
| regression | correct artifact | 0 | 0 ✅ |
| regression | a **different** 14 (digest binding) | 3 | 3 ✅ |
| regression | 25 + no artifact | 0 | 0 ✅ |
| regression | boundary 20 | 0 | 0 ✅ |
| regression | boundary 19 | 3 | 3 ✅ |
| probe | unquoted real instruction | 0 | 0 ✅ |
| probe | `decision: proceed` (lowercase) | 3 | 3 ✅ |
| probe | empty artifact file | 3 | 3 ✅ |
| probe | `user_instruction` line absent | 3 | 3 ✅ |
| probe | `user_instruction: """"` (quotes only) | 3 | 3 ✅ |

## Y2 — minor, closed

P8.0 called a broken acknowledgment path a *"rubber stamp that always exits 3"*. Always exiting 3
blocks everything — a fail-closed false alarm, the opposite of a rubber stamp. The direction was
right; only the label was wrong. Corrected.

## Outcome

`02-plan` **APPROVED at round 9**, `refine_count=2`. The gate is a mechanism, and the mechanism is
verified by execution.
