"""Record the demo webm, beat-by-beat, with hold times matched to TTS durations.

Reads beats from scripts/demo_script.py and per-beat audio durations from
the voiceover manifest. Writes a `timings.json` so the muxer can build a
perfectly-synced audio track.

Prereqs:
  1. Static site server running:    (cd credio-policies/dist && python3 -m http.server 8080)
  2. Voiceover already generated:    uv run --with openai --with python-dotenv python scripts/render_voiceover.py

Run:
  unset NODE_OPTIONS && uv run --with playwright python scripts/record_demo.py
"""
import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from demo_script import BEATS, PRE_NARRATION_MS, POST_NARRATION_MS


VIEWPORT = {"width": 1440, "height": 900}
OUT_DIR = Path("credio-policies/dist")
VIDEO_OUT = OUT_DIR / "demo-reference.webm"
TIMINGS_OUT = OUT_DIR / "_voiceover" / "timings.json"
VOICEOVER_MANIFEST = OUT_DIR / "_voiceover" / "manifest.json"

# CSS injected at every page load. Pins the change-page header to the top so
# the section title stays visible while scrolling into the diff panels.
# Production site is NOT affected — this only lives inside the recording
# browser context.
RECORDING_CSS = """
.change-header {
  position: sticky;
  top: 0;
  background: var(--surface, #fff);
  z-index: 40;
  padding-top: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
/* Push scroll targets below the sticky header */
section.tab-panel,
section.tab-panel .file-panel,
section.tab-panel .col,
section.tab-panel .prose,
section.tab-panel pre,
.extraction-warning,
.callout {
  scroll-margin-top: 130px;
}
/* Keep section eyebrow + H2 visible when scrolling into overview sections */
.overview-section {
  scroll-margin-top: 24px;
}
"""


def smooth_scroll_to_y(page, y, duration_ms=900):
    page.evaluate(
        """async ({y, duration}) => {
            const steps = Math.max(10, Math.round(duration / 16));
            const start = window.scrollY;
            const delta = y - start;
            const stepDelay = duration / steps;
            for (let i = 1; i <= steps; i++) {
                const t = i / steps;
                const ease = t < 0.5 ? 2*t*t : -1 + (4 - 2*t)*t;
                window.scrollTo(0, start + delta * ease);
                await new Promise(r => setTimeout(r, stepDelay));
            }
        }""",
        {"y": y, "duration": duration_ms},
    )


def smooth_scroll_to_element(page, selector):
    """Smooth-scroll so the element lands at the top of viewport, respecting
    scroll-margin-top (so sticky headers don't cover it)."""
    page.evaluate(
        """async (selector) => {
            const el = document.querySelector(selector);
            if (!el) return;
            // Pre-measure so we can do our own smooth animation
            const cs = window.getComputedStyle(el);
            const margin = parseInt(cs.scrollMarginTop || '0', 10);
            const targetY = el.getBoundingClientRect().top + window.scrollY - margin;
            const duration = 900;
            const steps = 60;
            const start = window.scrollY;
            const delta = targetY - start;
            const stepDelay = duration / steps;
            for (let i = 1; i <= steps; i++) {
                const t = i / steps;
                const ease = t < 0.5 ? 2*t*t : -1 + (4 - 2*t)*t;
                window.scrollTo(0, start + delta * ease);
                await new Promise(r => setTimeout(r, stepDelay));
            }
        }""",
        selector,
    )


def execute_action(page, action):
    """Run one beat's camera action. Returns nothing — duration is measured by caller."""
    t = action["type"]
    if t == "goto":
        page.goto(action["url"], wait_until="networkidle")
        page.add_style_tag(content=RECORDING_CSS)
        page.wait_for_timeout(300)  # settle layout
    elif t == "goto_and_scroll":
        page.goto(action["url"], wait_until="networkidle")
        page.add_style_tag(content=RECORDING_CSS)
        page.wait_for_timeout(300)
        smooth_scroll_to_element(page, action["selector"])
    elif t == "scroll_y":
        smooth_scroll_to_y(page, action["y"])
    elif t == "scroll_into_view":
        smooth_scroll_to_element(page, action["selector"])
    elif t == "hover":
        page.locator(action["selector"]).first.hover()
    elif t == "click":
        page.locator(action["selector"]).first.click()
        page.wait_for_timeout(200)
        if action.get("then_scroll"):
            smooth_scroll_to_element(page, action["then_scroll"])
    else:
        raise ValueError(f"Unknown action type: {t}")


def main():
    if not VOICEOVER_MANIFEST.exists():
        sys.exit(f"Voiceover manifest not found at {VOICEOVER_MANIFEST}. "
                 "Run scripts/render_voiceover.py first.")
    manifest = json.loads(VOICEOVER_MANIFEST.read_text())
    durations = {b["id"]: b["duration_seconds"] for b in manifest["beats"]}

    missing = [b["id"] for b in BEATS if b["id"] not in durations]
    if missing:
        sys.exit(f"Missing voiceover for beats: {missing}. "
                 "Re-run scripts/render_voiceover.py to regenerate.")

    timings = []
    print(f"Recording {len(BEATS)} beats…\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(OUT_DIR / "_video_tmp"),
            record_video_size=VIEWPORT,
        )
        # Inject CSS on every page navigation
        ctx.add_init_script(f"""
            (() => {{
                const style = document.createElement('style');
                style.textContent = `{RECORDING_CSS}`;
                document.head.appendChild(style);
            }})();
        """)

        page = ctx.new_page()

        beat_start = time.monotonic()
        for beat in BEATS:
            t0 = time.monotonic()
            execute_action(page, beat["action"])
            action_ms = int((time.monotonic() - t0) * 1000)

            tts_ms = int(durations[beat["id"]] * 1000)
            page.wait_for_timeout(PRE_NARRATION_MS + tts_ms + POST_NARRATION_MS)

            total_ms = int((time.monotonic() - t0) * 1000)
            timings.append({
                "id": beat["id"],
                "action_ms": action_ms,
                "tts_ms": tts_ms,
                "pre_ms": PRE_NARRATION_MS,
                "post_ms": POST_NARRATION_MS,
                "total_ms": total_ms,
            })
            print(f"  {beat['id']:32}  action {action_ms:5}ms · tts {tts_ms:5}ms · total {total_ms:5}ms")

        total_video_ms = int((time.monotonic() - beat_start) * 1000)
        print(f"\nVideo body wall-time: {total_video_ms/1000:.1f}s")

        video_path = page.video.path()
        ctx.close()
        browser.close()

    # Move the recorded video out of the tmp dir
    if video_path and Path(video_path).exists():
        shutil.move(video_path, VIDEO_OUT)
    tmp = OUT_DIR / "_video_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)

    TIMINGS_OUT.write_text(json.dumps({
        "viewport": VIEWPORT,
        "pre_narration_ms": PRE_NARRATION_MS,
        "post_narration_ms": POST_NARRATION_MS,
        "beats": timings,
    }, indent=2))

    print(f"\n✓ Video: {VIDEO_OUT}  ({VIDEO_OUT.stat().st_size/1_048_576:.1f} MB)")
    print(f"✓ Timings: {TIMINGS_OUT}")


if __name__ == "__main__":
    main()
