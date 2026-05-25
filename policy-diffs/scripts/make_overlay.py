"""Generate the Carver Agents badge overlay frames for the demo video.

Produces a sequence of 50 PNG frames (2-second loop at 25fps) where each frame
contains the static gradient badge plus a pulsing lime ring extending outward.
The frames are designed to be looped indefinitely by ffmpeg via -stream_loop.

Output:
  credio-policies/dist/_recording_assets/overlay/frame_NNNN.png
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_DIR = Path("credio-policies/dist/_recording_assets/overlay")
OUT_DIR.mkdir(parents=True, exist_ok=True)
WORDMARK = Path("credio-policies/dist/_recording_assets/carver_wordmark.png")

BADGE_SIZE = 120        # final visible diameter
CANVAS = 180            # canvas size (badge centered, 30px padding for pulse ring)
SS = 4                  # supersample factor
FRAMES = 50             # 2 seconds at 25fps
LOGO_WIDTH_RATIO = 0.62 # logo width as fraction of badge diameter

# Carver design palette
INK = (0x10, 0x18, 0x28)
INK_DEEP = (0x06, 0x0a, 0x14)
LIME = (0xba, 0xe4, 0x24)
CREAM = (0xfb, 0xf7, 0xf3)


def load_wordmark_recolored() -> Image.Image:
    """Load the Carver Agents wordmark and recolor it to cream.

    The source PNG is solid black on transparent. We swap the fill color
    while preserving the alpha shape so the logo reads cleanly on the
    dark badge background.
    """
    src = Image.open(WORDMARK).convert("RGBA")
    cream_fill = Image.new("RGBA", src.size, (*CREAM, 0))
    cream_fill.putalpha(src.getchannel("A"))
    return cream_fill


def draw_static_badge() -> Image.Image:
    """Render the un-animated badge (gradient + ring + text) at supersample."""
    cs = CANVAS * SS
    img = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = cs // 2
    r_outer = BADGE_SIZE * SS // 2  # 240

    # Soft outer halo glow (always-on, gentle)
    halo = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse(
        [cx - r_outer - 8 * SS, cy - r_outer - 8 * SS,
         cx + r_outer + 8 * SS, cy + r_outer + 8 * SS],
        fill=(*LIME, 60),
    )
    halo = halo.filter(ImageFilter.GaussianBlur(7 * SS))
    img = Image.alpha_composite(img, halo)
    draw = ImageDraw.Draw(img)

    # Filled circle with simulated radial gradient
    for i in range(r_outer, 0, -1):
        t = 1 - (i / r_outer)  # 0 at edge, 1 at center
        r = int(INK[0] * (1 - t) + INK_DEEP[0] * t)
        g = int(INK[1] * (1 - t) + INK_DEEP[1] * t)
        b = int(INK[2] * (1 - t) + INK_DEEP[2] * t)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(r, g, b, 255))

    # Lime ring border
    ring_w = 2 * SS
    draw.ellipse(
        [cx - r_outer + ring_w // 2, cy - r_outer + ring_w // 2,
         cx + r_outer - ring_w // 2, cy + r_outer - ring_w // 2],
        outline=(*LIME, 255), width=ring_w,
    )

    # Paste the actual Carver Agents wordmark (recolored to cream).
    logo = load_wordmark_recolored()
    target_w = int(BADGE_SIZE * SS * LOGO_WIDTH_RATIO)
    scale = target_w / logo.size[0]
    logo = logo.resize(
        (int(logo.size[0] * scale), int(logo.size[1] * scale)),
        Image.LANCZOS,
    )
    lx = cx - logo.size[0] // 2
    ly = cy - logo.size[1] // 2
    img.paste(logo, (lx, ly), logo)

    return img


def draw_pulse_ring(img: Image.Image, phase: float) -> Image.Image:
    """Overlay an expanding lime ring on the badge at this phase (0..1)."""
    cs = img.size[0]
    overlay = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx = cy = cs // 2
    r_base = BADGE_SIZE * SS // 2

    # Pulse expands from just outside the ring, fades as it grows
    expansion = phase * 22 * SS
    r = r_base + 4 * SS + expansion
    # Smooth fade-out, slight ease-in at start for natural feel
    alpha = int(160 * (1 - phase) ** 1.5)

    if alpha > 4:
        # Soft blurred ring
        ring_img = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
        ImageDraw.Draw(ring_img).ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(*LIME, alpha), width=int(3 * SS),
        )
        ring_img = ring_img.filter(ImageFilter.GaussianBlur(1.5 * SS))
        overlay = Image.alpha_composite(overlay, ring_img)

    return Image.alpha_composite(img, overlay)


def main():
    print(f"Rendering {FRAMES} frames at {CANVAS}x{CANVAS}…")
    static = draw_static_badge()
    for f in range(FRAMES):
        # Two pulse rings overlapping out of phase = continuous activity feel
        phase_a = (f / FRAMES + 0.0) % 1.0
        phase_b = (f / FRAMES + 0.5) % 1.0
        frame = static.copy()
        frame = draw_pulse_ring(frame, phase_a)
        frame = draw_pulse_ring(frame, phase_b)
        final = frame.resize((CANVAS, CANVAS), Image.LANCZOS)
        final.save(OUT_DIR / f"frame_{f:04d}.png")
    print(f"✓ Wrote {FRAMES} frames to {OUT_DIR}/")


if __name__ == "__main__":
    main()
