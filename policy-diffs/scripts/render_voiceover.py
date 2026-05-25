"""Generate TTS for each demo beat using OpenAI's gpt-4o-mini-tts.

Reads BEATS from scripts/demo_script.py, generates one wav per beat, and
writes a manifest with measured durations so the recorder + muxer can sync
to actual audio length.

Output:
  credio-policies/dist/_voiceover/<beat_id>.wav
  credio-policies/dist/_voiceover/manifest.json

Usage:
  # Make sure OPENAI_API_KEY is set in env or .env
  uv run --with openai --with python-dotenv python scripts/render_voiceover.py

Cost: ~$0.08 for the full demo at gpt-4o-mini-tts pricing.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent))
from demo_script import BEATS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI


MODEL = os.environ.get("TTS_MODEL", "gpt-4o-mini-tts")
VOICE = os.environ.get("TTS_VOICE", "cedar")
OUT_DIR = Path("credio-policies/dist/_voiceover")

# Calm, explanatory delivery — third-person narration to external prospects.
INSTRUCTIONS = (
    "Read calmly and clearly, like a confident product walkthrough narrator. "
    "Pace around 140 words per minute. Treat hyphenated initialisms like "
    "S-P-M-E and K-Y-B as letter-by-letter readings. Do not sound rushed; "
    "leave small natural breaths between sentences."
)


def wav_duration_seconds(path: Path) -> float:
    """ffprobe-based; robust to whatever header variant OpenAI's TTS returns."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def generate_one(client: OpenAI, beat: dict, out_path: Path) -> float:
    """Generate one beat's voiceover. Returns duration in seconds."""
    with client.audio.speech.with_streaming_response.create(
        model=MODEL,
        voice=VOICE,
        input=beat["narration"],
        instructions=INSTRUCTIONS,
        response_format="wav",
    ) as response:
        response.stream_to_file(str(out_path))
    return wav_duration_seconds(out_path)


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set. Populate it in .env or export it.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI()

    manifest = {"model": MODEL, "voice": VOICE, "beats": []}
    total_chars = 0
    total_seconds = 0.0

    for beat in BEATS:
        out_path = OUT_DIR / f"{beat['id']}.wav"
        duration = generate_one(client, beat, out_path)
        chars = len(beat["narration"])
        total_chars += chars
        total_seconds += duration
        manifest["beats"].append({
            "id": beat["id"],
            "chars": chars,
            "duration_seconds": round(duration, 3),
            "wav_path": str(out_path.relative_to(OUT_DIR.parent.parent.parent)),
        })
        print(f"  {beat['id']:32}  {chars:4}ch  {duration:5.2f}s")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print()
    print(f"✓ {len(BEATS)} beats · {total_chars} chars · "
          f"{total_seconds:.1f}s total ({total_seconds / 60:.1f} min)")
    print(f"✓ Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
