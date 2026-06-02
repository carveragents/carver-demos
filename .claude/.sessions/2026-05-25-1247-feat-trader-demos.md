# 2026-05-25 1247 — feat-trader-demos

## Session Overview

- **Start time:** 2026-05-25 12:47
- **Worktree:** /Users/achintthomas/work/scribble/code/repos/carver/carver-demos/.claude/worktrees/feat-trader-demos
- **Goal:** Create new trader-focused demos
- **Status:** Initialized

## Goals

Create new trader-focused demos for the Pred-Oracle project, expanding the demo specs to include trader-centric use cases and walkthrough scenarios.

## Progress

### Session Summary

**Duration:** 4 days (2026-05-25 12:47 → 2026-05-29)

**Git Summary:**
- Branch: worktree-feat-trader-demos
- Commits: 57 total (from main branch point)
- Files changed: 33 modified, 3 deleted, 25+ added
- Major additions: hyperframes overlays, TTS wave files, video assets, demo config files
- Untracked: exploration screenshots, browser cache, build artifacts

**Key Accomplishments:**

1. **Carver Trader demo video completed** (27.9 MB, 3:22 post-1.2x speedup, 4m43s recording)
   - 17-beat storyboard with smooth transitions and explicit narration verification
   - Intro sequence (Concept A + cross-dissolve) with kinetic typography
   - All hyperframes overlays aligned and composited (How it Works, Thesis Tracker, Outro Card)
   - Full post-processing pipeline: record → mux → speed → brand → overlay → finalize
   - 28 hero frames extracted and verified against on-screen claims

2. **Storyboard design refined through 8 user-requested iterations**
   - Beat 3: Added demo-sample clarification to portfolio narration
   - Beat 7: Fixed thesis tracker hyperframes vertical alignment (+3 recalculation attempts)
   - Beats 08b, 09b: Added smooth transition beats (back to /trader/ before opening Calendar and Case Studies)
   - Beat 10: New landing beat on retrospectives list
   - Beats 11–13: Added year (2025) to all dates, constrained narration to on-screen visible content
   - Beat 15: Updated CTA to "Get in touch and find out what Carver's data can do for you"

3. **Infrastructure improvements for demo automation**
   - preflight.py: Updated click-action pathfinding to correctly derive page URL (walks backward from beat N for click actions)
   - Template anchors: Added `id` attributes and `scroll-margin-top: 80px` to all major sections for precise recording positioning
   - Data attributes: Added `data-thesis-bar="true"` and `data-segment="direct-bullish|bg-bullish|direct-bearish"` for bounding-box measurement
   - ECharts tooltip dispatch: Implemented `?demo_show_event=YYYY-MM-DD` URL param to programmatically show chart event annotations

4. **Visual design and hyperframes composition**
   - Intro sequence: Full-screen dark card (radial gradient) with three staggered text lines entering at 0.6s, 2.9s, 4.6s (cross-dissolve exit at 8.3–8.9s)
   - Beat 2 (How it Works): Three step chips entering via fromTo (y+opacity), RHS positioned, fade out at transition
   - Beat 7 (Thesis Tracker): Three segment callouts (direct-bullish, bg-bullish, direct-bearish) with vertical alignment to bar centerline after scroll-into-view
   - Beat 15 (Outro Card): Full-screen branded card with headline, tagline, CTA pill + lime pulse dot
   - All compositions use GSAP timelines with paused-true contract, 0.1–0.3s entrance offset, varied eases (power3.out, expo.out, sine.inOut)

**Problems Encountered & Solutions:**

1. **Intro concept selection (rejected iteration)**
   - Problem: User requested intro concept options; Concept B (pull-back reveal) + T2 (transition) was selected but rendered visually awkward
   - Solution: Pivoted to Concept A (kinetic typography) + T1 (cross-dissolve) per user feedback
   - Lesson: First implementation isn't guaranteed correct; user visual review is essential gate

2. **Thesis tracker vertical misalignment (3 recalculation cycles)**
   - Problem: Beat 7 overlay dots were not landing on thesis bar segments; CSS positioning used estimated y-coordinates from comments
   - Root cause: scroll-into-view behavior placed bar at viewport y≈138, not y≈210 as assumed
   - Solution: Recalculated segment centers (x≈305, 508, 712) and connector heights (60px) to land dots precisely at bar centerline
   - Verification: Measured via preflight.py bounding-box data from actual page rendering
   - Lesson: Visual positioning cannot rely on assumptions; measure from rendered DOM

3. **Text wrapping in intro card**
   - Problem: "Prediction markets price tomorrow's news." wrapped to two lines at 56px font
   - Solution: Reduced to 48px, tightened padding to 140px H, added `white-space: nowrap` to lock single-line render
   - Lesson: Font size + padding + content length form a coupled system; adjust all three if any one fails

4. **Storyboard beat count expansion**
   - Problem: 14-beat storyboard → user feedback identified two abrupt navigation transitions (beat 8→9 and beat 9→10)
   - Solution: Decomposed into 17 beats: added 08b (back to /trader/), 09b (back to /trader/), 10 (retrospectives landing)
   - Lesson: Smooth UX requires explicit transition beats; what feels like one action often needs two (exit prev, enter next)

5. **Preflight click-action pathfinding**
   - Problem: Beat 5 (click CLARITY contract) failed selector verification because preflight tried to verify on `/trader/` instead of `/trader/portfolio/`
   - Solution: Updated `derive_page_url()` to walk backward from beat N: if beat N is a click, verify against result of beat N-1 (not N itself)
   - Lesson: Click actions resolve on the page they originate from, not the page they navigate to; pathfinding must account for action type

6. **Narration mismatch with on-screen content**
   - Problem: Beats 12–13 mentioned dates and numbers not visible at time of narration (e.g., citing "2025-08-04" when timeline scrolled past that date)
   - Solution: Constrained all narration to only claim what is on-screen at that beat's frame; rewrote affected beats
   - Lesson: Narration verification should be a preflight step: screenshot each beat, compare against script

**Features Implemented:**

- Storyboard-driven video recorder with 17 explicit beats
- Hyperframes motion-graphic overlay system (GSAP + cross-composition coordination)
- Preflight validation: selector resolution, bounding-box measurement, URL derivation
- TTS narration generation with per-beat caching and diff-aware re-render
- Video mux, speed, brand overlay, and hyperframes composition pipeline
- Hero frame extraction and visual verification

**Dependencies Added/Modified:**

- No new npm/Python dependencies added (used existing Playwright, GSAP, ECharts, OpenAI TTS)
- Modified: pred-oracle build templates, helper scripts (preflight.py), hyperframes index.html

**Configuration Changes:**

- storyboard.yaml: 14 beats → 17 beats with verified on-screen claims
- branding.yaml: Updated CTA and voice settings
- demo_config.yaml: Final speedup 1.2x, features (captions, brand_overlay) enabled
- helpers/preflight.py: Enhanced click-action pathfinding and bounding-box measurement
- build templates: Added anchors (id + scroll-margin-top), data attributes for measurement

**Deployment/Output:**

- Final video: `~/demo-videos/pred-oracle-trader/carver-trader-demo.mp4` (27.9 MB, 3:22 post-speedup)
- Hero frames: `~/demo-videos/pred-oracle-trader/_assets/hero_frames/` (28 PNG, 1 per beat × 2)
- TTS waves: `~/demo-videos/pred-oracle-trader/_assets/voiceover/` (17 WAV, one per beat)
- Metadata: anchors.json (measurement data for overlay composition), storyboard.yaml (source of truth)

**Lessons Learned (Cross-Project Applicable):**

1. **Hyperframes positioning requires bounding-box measurement, not estimation**
   - When aligning motion-graphic overlays to page elements, use programmatic measurement (Playwright locator.bounding_box()) rather than manual CSS estimates or comments
   - Validation should be automated in preflight: measure actual rendered positions, compare against expected, flag misalignment before recording

2. **Storyboard-driven video requires explicit transition beats**
   - Smooth navigation between features feels intentional; abrupt jumps feel jarring to viewers
   - Decompose high-level navigation intent into atomic beats: exit-previous (back to home), then enter-next (click into new feature)
   - Call out transitions explicitly in storyboard with short narration that bridges sections

3. **Verify all on-screen claims during preflight, before recording**
   - Every narration claim (number, date, UI label) should be verifiable against the actual page render at that beat's frame
   - Automate: screenshot each beat, parse visible text, compare against narration claims
   - Catch mismatches before TTS generation and recording (saves hours of rework)

**What Wasn't Completed:**

- None. Demo is complete and delivered.

**Tips for Future Developers:**

- **Hyperframes timing:** Beat duration in storyboard drives clip duration; GSAP timeline length is derived from data-duration, not vice versa. Always specify data-duration on clips.
- **Selector stability:** Prefer data-* attributes over semantic HTML selectors when building a site meant to be recorded; selectors are how the recorder finds elements, so they should be stable and unique.
- **Narration pacing:** ~16 characters per second (140 wpm) is the TTS speed. Count chars in narration to estimate beat duration; compare against intended sped-up window. If mismatch, rewrite or extend beat.
- **Preflight as integration test:** Run preflight before every recording cycle. It validates selectors, measures positions, and catches content mismatches. Missing a preflight step = lost time on rework.
- **Hyperframes anchor measurement:** Store all anchor bboxes and segment positions in anchors.json during preflight; use this data in the hyperframes HTML to position overlays. This creates a tight feedback loop: page changes → preflight remeasures → overlays reposition automatically.

---

**Session completed:** 2026-05-29
