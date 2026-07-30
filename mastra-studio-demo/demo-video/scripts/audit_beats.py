"""Storyboard-driven pre-record audit.

Reads storyboard.yaml and replays every beat's action IN SEQUENCE, exactly as record_demo.py
would (state carries between beats — scroll_into_view/fill depend on the previous goto). For each
beat it checks:

  1. CAPTION BAND — crop y=705..812 of a screenshot and count pixels off the dominant background.
     Pixel truth, because bounding boxes can't see ancestor clipping.
  2. CLAIM VISIBILITY — the required text must be inside the visible viewport ABOVE the caption
     band. `innerText` is not enough: it happily returns text that is scrolled out of a clipped
     panel, which is exactly how beat 12 shipped narrating an off-screen applicant ID.

Run it against a live `mastra dev` (and the assets/ page server) BEFORE spending TTS on a re-record:

    uv run --with playwright --with pyyaml --with pillow python scripts/audit_beats.py \
        [--dir <video project dir>] [--out <screenshot dir>]

Exits non-zero if any beat fails, and leaves a screenshot per beat in the output dir.
"""
import sys, pathlib, argparse, tempfile
from collections import Counter
import yaml
from playwright.sync_api import sync_playwright
from PIL import Image

_HERE = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
# Defaults to this file's own project dir, so the audit travels with the storyboard it checks.
ap.add_argument("--dir", default=str(_HERE.parent),
                help="video project dir holding storyboard.yaml + branding.yaml")
ap.add_argument("--out", default=None, help="where to write per-beat screenshots")
_args = ap.parse_args()

W = pathlib.Path(_args.dir).expanduser().resolve()
OUT = str(pathlib.Path(_args.out).expanduser() if _args.out
          else pathlib.Path(tempfile.mkdtemp(prefix="beat-audit-")) / "beat")
pathlib.Path(OUT).parent.mkdir(parents=True, exist_ok=True)
BAND_TOP, BAND_BOTTOM = 705, 812
BASE = "http://localhost:4111"

# What must be VISIBLE in each beat's frame for its narration to be honest.
CLAIMS = {
    "01_agents": "Lending Status — Carver (grounded)",
    "02_code": "@carver/sdk",
    "04_type_baseline": "CO-1001",
    # The denial is the premise of the whole video — every answer beat that names it must show it.
    "05_baseline_answer": ["declined", "611", "640"],
    "05b_baseline_notice": "adverse action",   # baseline arm does NOT hyphenate
    "07_type_websearch": "CO-1001",
    "08_websearch_answer": ["Declined", "611", "640"],
    # 08b narrates all three federal items plus the heading — every one must be in frame.
    "08b_websearch_federal": ["What happens next", "adverse-action", "credit report", "30 days", "federal"],
    "10_type_carver": "CO-1001",
    "11_carver_answer": ["Artificial Intelligence Act", "declined", "611"],
    "12_trace_lookup": "applicantId",
    "13_trace_lookup_state": "Colorado",
    "14_trace_retrieval": "Colorado Artificial Intelligence Act",
    "16_type_ca": "CA-1001",
    "17_carver_ca": ["Fair Lending Notice", "611"],
    "19_type_ny": "NY-1001",
    "20_carver_ny": ["Regulation B", "declined"],
    "21_results_reliability": "8 / 8",
    "22_results_tokens": "18,417",
    "23_results_caveat": "Mastra",
}

VISIBLE_JS = """
([needle, bandTop]) => {
  // Range-based, not element-based: an inline <a> whose text wraps has a bounding box spanning
  // several lines, and its centre lands in the gap between them — which made this report false
  // negatives for links like "Colorado Artificial Intelligence Act". Measure the TEXT itself.
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const raw = n.nodeValue || '';
    const idx = raw.replace(/\u00a0/g, ' ').indexOf(needle);
    if (idx < 0) continue;
    const el = n.parentElement;
    if (!el) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const range = document.createRange();
    range.setStart(n, idx);
    range.setEnd(n, Math.min(raw.length, idx + needle.length));
    for (const r of range.getClientRects()) {
      if (r.width === 0 || r.height === 0) continue;
      if (r.top < 0 || r.bottom > bandTop) continue;
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      if (x < 0 || x > window.innerWidth || y < 0 || y > bandTop) continue;
      const hit = document.elementFromPoint(x, y);
      if (hit && (el.contains(hit) || hit.contains(el) || hit === el)) return true;
    }
  }
  return false;
}
"""


def band_pixels(path):
    im = Image.open(path).convert("RGB")
    band = im.crop((0, BAND_TOP, im.width, BAND_BOTTOM))
    px = list(band.getdata())
    bg, _ = Counter(px).most_common(1)[0]
    off = sum(1 for p in px if abs(p[0]-bg[0]) + abs(p[1]-bg[1]) + abs(p[2]-bg[2]) > 42)
    return 100.0 * off / len(px)


sb = yaml.safe_load((W / "storyboard.yaml").read_text())
css = yaml.safe_load((W / "branding.yaml").read_text())["recording_css"]

print(f"{'beat':<24} {'band':>7}  claim")
print("-" * 62)
problems = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    for beat in sb["beats"]:
        bid = beat["id"]
        a = beat["action"]
        t = a["type"]
        if t in ("goto", "goto_and_scroll"):
            page.goto(a["url"].replace("{{ base_url }}", BASE), wait_until="load", timeout=45000)
            page.wait_for_timeout(2300)
            page.add_style_tag(content=css)
            page.wait_for_timeout(700)
            if t == "goto_and_scroll":
                page.evaluate("(s)=>{const e=document.querySelector(s); if(e) e.scrollIntoView({block:'center'});}", a["selector"])
                page.wait_for_timeout(1100)
        elif t == "fill":
            page.fill(a["selector"], a["value"])
            page.wait_for_timeout(700)
        elif t == "scroll_into_view":
            page.evaluate("(s)=>{const e=document.querySelector(s); if(e) e.scrollIntoView({block:s.startsWith('#')?'start':'center'});}", a["selector"])
            page.wait_for_timeout(1100)

        # Mirror record_demo.py: highlight class lands after the action, cleared every beat.
        hl = beat.get("highlight")
        sels = [hl] if isinstance(hl, str) else list(hl or [])
        n = page.evaluate(
            "([sels, cls]) => { document.querySelectorAll('.'+cls).forEach(e=>e.classList.remove(cls));"
            " let n=0; for (const s of sels) for (const e of document.querySelectorAll(s)) { e.classList.add(cls); n++; }"
            " return n; }", [sels, "snt-highlight"])
        if sels and n == 0:
            problems.append(bid + " (highlight matched nothing)")
        page.wait_for_timeout(400)

        shot = f"{OUT}_{bid}.png"
        page.screenshot(path=shot)
        pct = band_pixels(shot)
        need = CLAIMS.get(bid)
        if not need:
            claim = "-"
        else:
            needles = [need] if isinstance(need, str) else need
            missing = []
            for need in needles:
                if t == "fill":
                # A textarea's typed text is a VALUE, not a DOM text node — TreeWalker is blind to
                # it. Check the value and that the field is visible above the caption band.
                    vis = page.evaluate(
                        "([sel, needle, bandTop]) => { const el = document.querySelector(sel);"
                        " if (!el || !el.value.includes(needle)) return false;"
                        " const r = el.getBoundingClientRect();"
                        " return r.height > 0 && r.top >= 0 && r.bottom <= bandTop; }",
                        [a["selector"], need, BAND_TOP])
                else:
                    vis = page.evaluate(VISIBLE_JS, [need, BAND_TOP])
                if not vis:
                    missing.append(need)
            claim = "OK" if not missing else "NOT VISIBLE: " + ", ".join(f'"{m}"' for m in missing)

        bad = pct >= 0.35 or (need and claim != "OK")
        if bad:
            problems.append(bid)
        print(f"{bid:<24} {pct:>6.2f}%  {claim}")
    browser.close()

print("-" * 62)
print("ALL BEATS PASS" if not problems else f"NEEDS WORK: {', '.join(problems)}")
sys.exit(1 if problems else 0)
