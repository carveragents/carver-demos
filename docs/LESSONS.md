# Project Lessons Learned

## SESSIONS

- 2026-05-25-1138-move-existing-demos
- 2026-05-25-1247-feat-trader-demos
- 2026-07-17-1529-feat-extend-mastra-demo

---

## LESSONS

### 1. Validate file purpose before organizing — don't assume artifacts are assets

**Problem:** When consolidating repositories, loose files in a project root often look like they should be organized (especially if they're grouped by naming pattern). Easy to assume they're assets that need a proper home.

**Mitigation:** Before reorganizing or consolidating files, check three things: (1) Is the file `.gitignored` in the original repo? (2) Does the file have zero code references (`grep -r` across docs/code/templates)? (3) Is the file used by the application or just a development artifact? If all three are "ignored, unreferenced, unused," it's probably scratch and should not be tracked.

**Lesson:** Development scratch and actual assets look similar at first glance. A quick `.gitignore` + grep check prevents unnecessary organization work and keeps the repo clean. If files were intentionally excluded, respect that intent unless you have a strong reason to track them now.

### 2. Preserve project-specific context when consolidating repos into a monorepo

**Problem:** When moving standalone repositories into a monorepo subdirectory, it's tempting to strip away project-specific config files (like `.claude/`, `.superpowers/`) to "clean up" the root. But these files often contain crucial guidance for AI agents and developers working on that specific project.

**Mitigation:** Always preserve project-local configuration that might be referenced later:
- `CLAUDE.md` or equivalent (agent system prompts, coding standards for that project)
- `.claude/settings.json` (project-specific Claude Code settings)
- `.superpowers/` (project-specific skill definitions)
- `docs/LESSONS.md` or project-local lesson files (contextual decisions)

**Lesson:** In a monorepo with heterogeneous projects, each demo/component is different. Keeping its local config prevents loss of context and avoids the need to recreate guidance later. The parent repo's `.claude/` and each subdirectory's `.claude/` serve different purposes and should coexist without conflict.

### 3. Motion-graphic overlays require programmatic measurement, not estimation

**Problem:** When aligning hyperframes overlays to page elements (e.g., thesis bar segment positions), manual CSS estimates or comment-based coordinates lead to misalignment that only becomes visible after rendering. Fixing after-the-fact costs rework.

**Mitigation:** Use programmatic bounding-box measurement from the actual rendered page (Playwright `locator.bounding_box()`) in preflight validation. Measure segment positions, store in anchors.json, and use the data to position overlays. Automate the preflight check: fail if measured positions deviate more than 5–10px from expected.

**Lesson:** Visual positioning is a data problem. Measure once during preflight, version the measurement data, and consume it in the composition. Avoid hardcoding positions based on assumptions or comments.

### 4. Storyboard-driven video requires explicit transition beats between major sections

**Problem:** Abrupt navigation jumps (e.g., closing Contract Details and jumping to Calendar) feel jarring to viewers. What seems like one logical step often needs two: exit-previous + enter-next.

**Mitigation:** When sketching beat flow, mark navigation transitions explicitly: identify which beats involve page changes, then add explicit transition beats. Example: beat 8 (scroll to end of contract page) → beat 08b (goto /trader/) → beat 9 (click calendar). Keep transition beat narration short (2–3 seconds); it's bridge copy, not substance.

**Lesson:** Smooth narrative pacing requires explicit transitions. Treat navigation like a scene change: close one scene, open the next. Don't skip the bridge.

### 5. Verify all on-screen narration claims during preflight, before TTS generation

**Problem:** Narration mentions numbers, dates, or UI labels that aren't actually visible at that beat's frame. Examples: mentioning a date when the timeline has scrolled past it, or citing event counts that don't match what's rendered. Catching these after recording wastes time on rework.

**Mitigation:** During preflight, screenshot each beat's frame. Automatically parse visible text (OCR or DOM text-content), compare against narration script. Flag any claim (number, date, label) that doesn't appear on-screen. Fix narration BEFORE TTS generation.

**Lesson:** Narration verification should be a preflight gate. Make it a checklist step: every factual claim must be verifiable from the page render, or the narration script is incomplete.

### 6. Benchmarking agent/model variants: measure per-case and hunt confounds before headlining a number

**Problem:** A comparative demo (grounded vs web-search agent) is easy to oversell — a favorable pooled median can hide a weak per-case cell, and an apparent "win" can be an artifact of a prompt asymmetry rather than the capability under test. (User caught both: "did you check all cases?" and "are the prompts different?")

**Mitigation:** Report per-case, not just pooled; neutralize prompt differences to what's structurally unavoidable (verbatim-shared instructions, only the tool differs) and re-test; run an ablation (drop the thing you claim is causing the win — here, curated records — and confirm the result collapses).

**Lesson:** For any A-vs-B claim, the headline number is only trustworthy after per-case breakdown + confound-neutralization + ablation. "Measure, don't assert" applies to the *comparison*, not just the result.

### 7. Reporting LLM agent token/cost: split cache-read vs fresh input, report cache-warm and cold, treat hosted-tool internal tokens as an unmeasurable floor

**Problem:** Gross token totals overstate real cost (cached input bills at ~1/10th), and provider-hosted tools (e.g. OpenAI web_search) consume server-side tokens that never appear in `usage` — so a naive token/cost comparison is both too high and incomplete.

**Mitigation:** Read `totalUsage` (it sums every model step; tool *results* land as *input* tokens on the next step), split fresh vs cache-read input, and report both cache-warm (steady-state) and cold (no-cache) cost as a range. State that hosted-tool internal tokens are a floor no API (or separate key) exposes.

**Lesson:** LLM cost claims need cache-adjusted, per-token-class accounting and an explicit floor caveat; a single gross-token dollar figure is neither accurate nor defensible.

### 8. When a demo value looks wrong, check whether it's coupled to a real constraint before cosmetically fixing it

**Problem:** A demo artifact had a decision date in the future, which reads as a bug on stage. The naive fix (move it to the present) silently broke the demo — the obligation being showcased only takes legal effect on that future date, so a present-day date made the key beat non-deterministic. (Surfaced by user: "the date is in the future — not explainable.")

**Mitigation:** Before changing a suspicious value, test whether it's coupled to a domain constraint; if it is, keep the value and make the framing explicit ("this scenario is set in early 2027, when the law takes effect") rather than hiding the coupling.

**Lesson:** A value that looks wrong may be load-bearing. Investigate the coupling first; an explicit, explained constraint beats a cosmetic change that quietly degrades the result.
