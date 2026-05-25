"""Mux the recorded webm with the per-beat TTS into a single mp4.

For each beat, builds a synced audio segment:

  silence(action_ms + pre_narration_ms) + tts_wav + silence(post_narration_ms)

These segments concatenate to the same total duration the recorder produced,
so audio and video stay in lock-step.

Input:
  credio-policies/dist/demo-reference.webm
  credio-policies/dist/_voiceover/*.wav
  credio-policies/dist/_voiceover/manifest.json
  credio-policies/dist/_voiceover/timings.json

Output:
  credio-policies/dist/demo-final.mp4

Run:
  uv run --with pydub python scripts/mux_demo.py
"""
import json
import subprocess
import sys
from pathlib import Path

from pydub import AudioSegment


OUT_DIR = Path("credio-policies/dist")
VOICE_DIR = OUT_DIR / "_voiceover"
VIDEO_IN = OUT_DIR / "demo-reference.webm"
VIDEO_OUT = OUT_DIR / "demo-final.mp4"
AUDIO_OUT = VOICE_DIR / "full.wav"


def build_audio_track() -> AudioSegment:
    manifest = json.loads((VOICE_DIR / "manifest.json").read_text())
    timings = json.loads((VOICE_DIR / "timings.json").read_text())
    timing_by_id = {b["id"]: b for b in timings["beats"]}

    full = AudioSegment.silent(duration=0)
    # Use a consistent frame rate (matches OpenAI TTS wav output, typically 24kHz)
    target_fr = None

    for entry in manifest["beats"]:
        beat_id = entry["id"]
        t = timing_by_id.get(beat_id)
        if t is None:
            sys.exit(f"No recording timing for beat {beat_id}. "
                     "Re-run scripts/record_demo.py.")

        wav_path = VOICE_DIR / f"{beat_id}.wav"
        tts = AudioSegment.from_wav(str(wav_path))
        if target_fr is None:
            target_fr = tts.frame_rate
        elif tts.frame_rate != target_fr:
            tts = tts.set_frame_rate(target_fr)

        pre = AudioSegment.silent(
            duration=t["action_ms"] + t["pre_ms"],
            frame_rate=target_fr,
        )
        post = AudioSegment.silent(
            duration=t["post_ms"],
            frame_rate=target_fr,
        )
        full += pre + tts + post

    return full


def mux(audio_path: Path, video_path: Path, out_path: Path):
    """Mux audio onto video, re-encoding to h264+aac for universal mp4 playback."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    if not VIDEO_IN.exists():
        sys.exit(f"Video not found at {VIDEO_IN}. Run scripts/record_demo.py first.")
    if not (VOICE_DIR / "timings.json").exists():
        sys.exit("timings.json missing — run scripts/record_demo.py to produce it.")

    print("Building synced audio track…")
    audio = build_audio_track()
    audio.export(str(AUDIO_OUT), format="wav")
    print(f"✓ Audio: {AUDIO_OUT} ({len(audio)/1000:.1f}s)")

    print("\nMuxing audio + video → mp4…")
    mux(AUDIO_OUT, VIDEO_IN, VIDEO_OUT)
    print(f"\n✓ Final video: {VIDEO_OUT} "
          f"({VIDEO_OUT.stat().st_size/1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
