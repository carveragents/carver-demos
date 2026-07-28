# Session: Move Existing Demos
**Started:** 2026-05-25 11:38

**Worktree:** /Users/achintthomas/work/scribble/code/repos/carver/carver-demos/.claude/worktrees/move-existing-demos

---

## Goals

- Move existing demos from outside this repository into the carver-demos monorepo
- Organize demos following the existing structure (each in its own subdirectory with README)
- Update the root README to document all imported demos

---

## Progress

_Session completed — see summary below_

---

## Session Summary

**Duration:** 2026-05-25 11:38 → 12:13 (35 minutes)

### Git Changes

**Files modified:**
- `README.md` — updated Demos table to include policy-diffs and pred-oracle entries

**Files added (untracked, ready to stage):**
- `policy-diffs/` — 114M, complete POC for Mastercard rulebook → Credio policy diff automation
- `pred-oracle/` — 24M, vertical compliance-intelligence platform for prediction-market operators
- `.claude/` — session tracking directory

**Total changed:** 3 items (1 modified, 2 new directories + session tracking)

### Accomplishments

✅ **Successfully moved 2 external repos into carver-demos monorepo:**
- Copied `../policy-diffs/` → `policy-diffs/` (excluded `.git`, `.venv`, `.pytest_cache`, `.env`)
- Copied `../pred-oracle/` → `pred-oracle/` (same exclusions)
- All source code, docs, CLAUDE.md (pred-oracle), .superpowers (policy-diffs), and .claude configs preserved

✅ **Organized structure following monorepo pattern:**
- Each demo is now a standalone subdirectory with its own README, dependencies, and docs
- `.git` / `.venv` / build artifacts excluded (not duplicated)

✅ **Updated root README:**
- Added policy-diffs entry: "POC that converts Mastercard B2B artifact deltas into Credio policy update proposals"
- Added pred-oracle entry: "A vertical compliance-intelligence platform for prediction-market operators (Kalshi, Polymarket, CFTC-licensed DCMs)"

✅ **Cleaned up development artifacts:**
- Identified 24 loose PNG files at `pred-oracle/` root (Playwright MCP exploration screenshots)
- Confirmed they were `.gitignored` in original repo (never tracked; development scratch)
- Verified not referenced in code or demos
- Decided NOT to track them (reverted unnecessary organization attempt)

✅ **Enhanced policy-diffs README:**
- Expanded from 4-line stub to 142-line comprehensive guide
- Added: problem statement (Credio's compliance exposure), 6-stage pipeline diagram, 3-layer demo presentation architecture, setup/run commands with cost/time expectations, annotated project layout, tech stack, status, and links to design doc/plan/runbook

### Key Decisions & Rationale

1. **Left originals in place** (not deleted)
   - `policy-diffs`: safe to delete later (pushed to GitHub)
   - `pred-oracle`: dangerous to delete (no remote; 132 local commits)
   - User chose "leave for now" option — safer approach

2. **Did not track loose PNGs**
   - Originally `.gitignored` in pred-oracle (intentional exclusion)
   - Zero code references; purely development exploration artifacts
   - Kept original `.gitignore` rule intact (*.png)

3. **Preserved CLAUDE.md and all docs**
   - policy-diffs: `.claude/settings.json` and `.superpowers/` moved
   - pred-oracle: CLAUDE.md preserved at root, full `docs/` tree intact

### Files Ready to Commit

- `README.md` (root) — updated Demos table
- `policy-diffs/` — complete POC implementation (114M)
  - `pipeline/`, `prompts/`, `presentation/` — core stages
  - `credio-policies/` — synthetic baseline + rendered dist/
  - `docs/superpowers/specs/` — comprehensive design doc (design-first POC)
  - `README.md` — thoroughly documented (~142 lines)
- `pred-oracle/` — compliance-intelligence platform (24M)
  - `build/`, `data/`, `scripts/`, `tests/`
  - `.github/workflows/` — CI configuration
  - `CLAUDE.md` — agent guidance
  - `docs/` — product strategy, development guide, lessons learned, specs

### What Wasn't Completed

- Not committed yet (per user request: commit after this session end)
- Not merged back to main (per user: git:merge-cleanup will handle)
- Originals (`../policy-diffs`, `../pred-oracle`) left untouched (user chose preservation option)

### Lessons Learned

- **Gotcha: .gitignore scope in monorepos** — Each subdirectory's .gitignore still applies to that path in the parent repo. Tried to whitelist pred-oracle PNGs with `!docs/screenshots/*.png`, but realized they were dev scratch not worth tracking; reverted.
- **Validation before organizing** — Always check if files are referenced, tracked, or used before "organizing" them. The PNGs looked like assets but were actually untracked scratch; a grep pass upstream saved unnecessary work.
- **Preserve context when consolidating repos** — Keeping CLAUDE.md, .superpowers/, docs/, and .claude/ configs for each demo prevents losing project-specific guidance and AI context. Critical for non-homogeneous codebases in a monorepo.

### Tips for Future Developers

- Run `git ls-files --others --exclude-standard <path>` to verify files are actually tracked vs. ignored
- When copying repos, use rsync with explicit exclusion lists rather than cherry-picking to avoid leaving artifacts behind
- The root README's Demos table should stay in sync with subdirectories — consider a pre-commit hook or CI check if more demos are added
- Each demo's README should be comprehensive (not a stub); it's the first thing a developer lands on
