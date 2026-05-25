"""Overlay the Carver Agents pulsing badge + audio-reactive waveform onto the
sped-up demo video.

Reads:
  credio-policies/dist/demo-final-fast.mp4
  credio-policies/dist/_recording_assets/overlay/frame_NNNN.png

Writes:
  credio-policies/dist/demo-video.mp4

Run:
  scripts/make_overlay.py first to produce the badge frames.
  Then: ffmpeg path must be on $PATH (already verified).
"""
import subprocess
from pathlib import Path

VIDEO_IN = Path("credio-policies/dist/demo-final-fast.mp4")
VIDEO_OUT = Path("credio-policies/dist/demo-video.mp4")
OVERLAY_DIR = Path("credio-policies/dist/_recording_assets/overlay")
FRAMES = OVERLAY_DIR / "frame_%04d.png"

# Layout (1440x900 video):
#   ┌──────────────────────────────┐
#   │              [video]         │
#   │  ┌────┐                      │
#   │  │ CA │ ← 120px badge        │
#   │  │ rv │   in 180px canvas    │
#   │  └────┘                      │
#   │  ∿∿∿∿∿  ← 140x40 waveform    │
#   └──────────────────────────────┘
#
# Bottom margin: 24px. Gap between badge and wave: 8px. Wave height: 40px.
# Badge visible at x=30..150, centered horizontally with the 140px wave.

BADGE_CANVAS = 180          # PNG canvas size
BADGE_VISIBLE = 120         # visible circle diameter inside canvas
BADGE_LEFT_MARGIN = 30      # visible badge from left edge of video
BOTTOM_MARGIN = 36
GAP = 6
WAVE_W, WAVE_H = 200, 36

# Badge canvas position: place so visible badge top sits above the waveform
#   visible_badge_bottom = H - BOTTOM_MARGIN - WAVE_H - GAP
#   visible_badge_top    = visible_badge_bottom - BADGE_VISIBLE
#   canvas_top           = visible_badge_top - 30 (canvas padding)
CANVAS_Y_EXPR = f"H-{BOTTOM_MARGIN + WAVE_H + GAP + BADGE_VISIBLE + (BADGE_CANVAS - BADGE_VISIBLE) // 2}"
CANVAS_X = BADGE_LEFT_MARGIN - (BADGE_CANVAS - BADGE_VISIBLE) // 2   # 30 - 30 = 0

# Waveform position: align with badge horizontally; wider than badge for presence.
WAVE_X = BADGE_LEFT_MARGIN + (BADGE_VISIBLE - WAVE_W) // 2   # 30 + (120-200)/2 = -10 → clamp
if WAVE_X < 10:
    WAVE_X = 10
WAVE_Y_EXPR = f"H-{BOTTOM_MARGIN + WAVE_H}"


def main():
    filter_complex = (
        # Audio-reactive waveform — sqrt scale boosts low amplitudes so quiet
        # speech still registers visually. p2p mode draws connected lines for
        # a classic oscilloscope look.
        f"[0:a]aformat=channel_layouts=mono,"
        f"showwaves=s={WAVE_W}x{WAVE_H}:mode=p2p:rate=25:scale=sqrt:colors=#bae424,"
        f"format=rgba,colorkey=0x000000:0.15:0[wave];"
        # Overlay pulsing badge frames (looped via -stream_loop) onto base.
        f"[0:v][1:v]overlay=x={CANVAS_X}:y={CANVAS_Y_EXPR}:shortest=0[v_badge];"
        # Then overlay the waveform just below the badge.
        f"[v_badge][wave]overlay=x={WAVE_X}:y={WAVE_Y_EXPR}[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(VIDEO_IN),
        "-framerate", "25", "-stream_loop", "-1", "-i", str(FRAMES),
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(VIDEO_OUT),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\n✓ Branded video: {VIDEO_OUT} "
          f"({VIDEO_OUT.stat().st_size/1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
