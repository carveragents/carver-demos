---
verdict: CHANGES_REQUESTED
round: 2
---

## Issues

1. **P6.0 is ordered before the synthetic fixture it consumes and adds an unapproved CLI contract.** The graph/task order is `P6.0 generate → P6.1 fixture`, while P6.0 explicitly reads “P6.1's synthetic cleared set”; reverse those steps. More importantly, `run_prep.py --emit-template-config --synthetic` is a new argv branch not present in the approved spec (P5.1 itself lists only the approved branches). Keep `run_prep.py` unchanged: create exact, committed synthetic generator-input fixtures (cleared records plus a fully specified `ScenarioDecision`, no “plausible” values) and invoke `emit_template_config(...)` directly with the project-local Python interpreter in the implementation step, or through an already-specified test/helper surface. Pin the exact command and inputs. P8.2 remains the approved `run_prep.py --emit-template-config` path over real reviewed data.

2. **The renumbered Phase-6 DAG left stale task dependencies and assignments.** Examples: P6.8 says it depends on “P6.3 (`runJudge`), P6.5 (`narrowObligationsPure`)”, but `runJudge` is now P6.5 and narrowing is P6.6; R7.0 names P6.14 as the phase gate, but the gate is P6.16; the stress table assigns empty narrowing/malformed judge to P6.7 although `CarverGuardrail` is P6.8, `crowdedOut` to P6.9 although evals are P6.11, and the citation/medium-low README statements to P6.13 although README is P6.15. Sweep every dependency, phase-gate, stress-scenario, risk, and carried-forward reference after the renumbering. This plan exists to prevent exactly the “authoritative site fixed, restatements stale” defect.

3. **The Phase-1 heading still makes the false parallelism claim the body corrected.** It says “Parallelizable: all ten modules,” while the revised parallelism section correctly makes P1.4 → P1.1 and P1.9 → P1.10 ordered joins. Replace the heading with the actual independent subset or point to the explicit table; do not leave a contradictory summary at the phase boundary.

4. **P5.1 omits the `--review` argv branch used by the real-run procedure.** The task says it creates `main()` plus `--replay`, `--emit-template-config`, and `--verify-cleared`, but R7.4 invokes `run_prep.py --review`, which the approved spec also names. Add the review branch and its tests/dispatch contract to P5.1 so the human checkpoint command is implemented before Phase 7.

## Notes

The billed-call sequencing, real TypeScript DAG, generated-only source rule, command cwd, per-change Python review cadence, clearing-time citation proof, and branch-first workflow are otherwise corrected well.
