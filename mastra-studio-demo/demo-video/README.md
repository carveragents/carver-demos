# State-lending demo video

`carver-state-lending.mp4` — 3:42, 25 beats. The narrated walkthrough of the state-lending
scenario documented in [`../docs/DEMO.md`](../docs/DEMO.md), built for an external audience and
co-branded Carver × Mastra for the design-partner pitch.

The argument it makes, in order: an applicant asks about his loan → it was declined by an
automated model → the federal-only answer is incomplete → live web search doesn't close the gap →
the Carver-grounded agent names the state obligation → the trace proves the state came from the
lender's own record and not from anything the applicant typed → California confirms it generalises
→ New York controls → 8/8 vs 0/8, measured.

## What's here

| Path | |
|---|---|
| `carver-state-lending.mp4` | the deliverable |
| `storyboard.yaml` | 25 beats — actions, highlights, narration. Heavily commented; read it before changing anything |
| `branding.yaml` | colours, voice, caption geometry, `recording_css`, music bed |
| `demo_config.yaml` | base URL, viewport, speed, feature flags |
| `assets/code.html`, `assets/results.html` | the two card beats, served on `:8099` at record time |
| `assets/carver_wordmark.png` | the corner badge (Carver only — a lockup is unreadable at that size) |
| `assets/carver-mastra-lockup.png` | the intro/outro slides |
| `scripts/audit_beats.py` | pre-record audit — replays every beat and checks its claims are on screen |
| `scripts/build_music_bed.sh` | rebuilds the music bed for a given runtime |

Not committed, because all of it regenerates: `_voiceover/` (TTS, ~$0.10 a run),
`_intermediate/` (mux/speed/brand stages), `reference.webm`, and `assets/bg_music_tech.mp3`
(run `scripts/build_music_bed.sh`).

## Rebuilding

Produced with the `show-n-tell` skill, which lives outside this repo in
`~/.claude/skills/show-n-tell/`. The video project is expected at
`~/demo-videos/carver-state-lending/` — copy this directory there, keeping `assets/` as
`_assets/` and `assets/{code,results}.html` as `_assets/pages/`.

Two servers must be up first:

```bash
cd mastra-studio-demo && npm run dev            # Mastra Studio on :4111
cd demo-video/assets && python3 -m http.server 8099   # the card beats
```

Then, from the skill directory:

```bash
W=~/demo-videos/carver-state-lending
uv run scripts/render_voiceover.py --working-dir $W     # diff-aware; only changed beats re-bill
uv run scripts/record_demo.py     --working-dir $W
uv run scripts/mux_demo.py        --working-dir $W
uv run scripts/speed_video.py  --input $W/_intermediate/muxed.mp4 --output $W/_intermediate/speed.mp4 --multiplier 1.2
uv run scripts/brand_video.py  --working-dir $W --input $W/_intermediate/speed.mp4 --output $W/_intermediate/branded.mp4
uv run scripts/make_intro_outro.py --working-dir $W
uv run scripts/make_captions.py    --working-dir $W
./demo-video/scripts/build_music_bed.sh --from-branded $W/_intermediate/branded.mp4
uv run scripts/finalize_video.py --working-dir $W --input $W/_intermediate/branded.mp4 --output $W/carver-state-lending.mp4
```

**Audit before you spend TTS**, against the same live servers:

```bash
uv run --with playwright --with pyyaml --with pillow python scripts/audit_beats.py
```

It replays every beat's action in sequence and fails if a narrated claim isn't visible in that
beat's frame, or if anything intrudes into the caption band. It has caught two defects that had
already shipped.

## Things that will bite you

**The answers on screen are replayed, not generated live.** Each agent takes 18–31s per answer,
which would be dead air. `scripts/capture-demo-threads.mjs` records nine real conversations into
memory under deterministic thread ids (`demo-<arm>-<applicant>`), and the storyboard navigates to
those saved threads. The ask/type beats fill the composer with the same message verbatim and send
nothing.

**Re-capturing threads invalidates the trace ids** hardcoded at beats 12 and 14, and re-rolls every
claim the storyboard pins — the Colorado bullet, the DFPI link, New York's silence. Re-run the
audit after any re-capture.

**The fixture's `decisionDate` is 2027-01-14, and that is deliberate.** The Colorado obligation
being showcased only takes legal effect then. Moving it to the present has been tried and it broke
the key beat — see `docs/LESSONS.md` #8. One consequence: the web-search agent, which knows today's
date from its search grounding, flags the record as an error. That paragraph was removed from the
stored `demo-websearch-co-1001` message. Nothing else in any answer was edited.

**Captions are burned in and wrap by width.** Keep any single beat's narration under ~255
characters. Longer, and the three-line block widens into the corner badge; longer still and it goes
to four lines, which grows *upward* out of the 190px reserve and back over the page content.

**The music bed is pinned to the runtime.** Change the beats and you change the length; rerun
`scripts/build_music_bed.sh --from-branded ...` or the bed hits its loop restart before the end.

## Credits

Music: **"This Or That" by Luigi Talluto** via [Jamendo](https://www.jamendo.com/track/1114380),
CC-BY-SA 3.0. Attribution is required wherever this video is published — it is *not* burned into
the video.
