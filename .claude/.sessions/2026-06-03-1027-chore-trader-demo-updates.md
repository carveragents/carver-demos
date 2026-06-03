# chore-trader-demo-updates — 2026-06-03 10:27 AM

## Session Overview

- **Start time:** 2026-06-03 10:27 AM
- **Worktree:** `/Users/achintthomas/work/scribble/code/repos/carver/carver-demos/.claude/worktrees/chore-trader-demo-updates`
- **Branch:** `worktree-chore-trader-demo-updates`

## Goals

Make minor changes to the carver trader demo pages.

## Progress

### Copy changes (trader demo pages)
- **Thesis tracker → "Carver Thesis Tracker"** on the contract briefing template
  (`build/templates/trader/briefing.html`) + a subtitle line ("Bullish/bearish
  reads aggregated from Carver-annotated regulatory events"). Applies to all 9
  contract pages and all 4 retrospective pages (same template).
- **"Regulatory Calendar" → "Event Catalyst Calendar"** on the calendar page
  (`calendar.html`) + subtitle "N catalyst events that will impact your portfolio".
- **Trader overview** (`intro.html`): "Regulatory calendar" feature card →
  "Event Catalyst Calendar" + meta description; product landing (`landing.html`)
  prose updated to match.
- Built `site/` HTML updated to match (presentation-only string swap; no
  re-slice, so curated dates/numbers preserved).

### Build fix — retrospective fragility
- `build/generate.py` previously wiped all of `site/` (`shutil.rmtree`) and only
  re-rendered pages with a committed page_data slice — silently deleting the 3
  retrospectives (cardano / polymarket / stablecoin) whose slices were never
  committed (corpus is gitignored scratch; no API key to re-pull).
- Added `_preserve_sliceless_retrospectives()`: snapshots those committed pages
  before the wipe and restores them after. Self-disabling once slices exist.
  Reviewed (no correctness bugs).

### Demo video (lives in ~/demo-videos/pred-oracle-trader/, not this repo)
- Full re-record of the show-n-tell + HyperFrames demo as
  `carver-trader-demo-v2.mp4` (+ `.srt`); original `carver-trader-demo.mp4`
  preserved. Beat 07 narration → "Carver thesis tracker"; beat 09 → Event
  Catalyst Calendar; thesis callouts re-anchored +20px; overlay outro/base
  timings recomputed; overview card fixed. Verified frames.

### Known follow-ups (not done this session)
- `make build` is still destructive to other sliceless committed pages
  (`alpha/*`, `beta/*`, `gamma/*`, resolved `trader/contracts/*`). The preserve
  fix covers retrospectives only. Proper fix needs the slices regenerated, which
  requires re-pulling the corpus (CARVER_API_KEY not available here).
