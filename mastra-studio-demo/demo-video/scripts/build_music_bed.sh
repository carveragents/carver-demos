#!/usr/bin/env bash
# Build the background music bed for the demo.
#
# WHY THIS EXISTS instead of `bg_music_mood: tech` in branding.yaml:
# the bundled source track is 207.5s, the video is longer, and show-n-tell loops the bed with
# `aloop=loop=-1`. The track also ends with its own fade — measured digital silence (-91dB) from
# 196s — so the loop restart jumps from silence to full level. Wherever that lands, you hear it.
#
# This re-cuts the track so it never reaches a loop point at all:
#   body 0-192s (its own fade-out stripped) crossfaded 5s into 30s-onward  -> one long continuous bed
#   front-padded 0.4s  -> establishes over the title card, the only stretch with no narration on it
#   faded out over the last 6.8s and trimmed to the exact runtime -> resolves on the final frame
#
# RERUN THIS WHENEVER THE RUNTIME CHANGES. The fade is pinned to the total; a stale bed silently
# reintroduces the loop restart it exists to avoid.
#
# Music: "This Or That" by Luigi Talluto via Jamendo (CC-BY-SA 3.0)
#        https://www.jamendo.com/track/1114380
#        Attribution is required wherever the video is published. show-n-tell prints the credit
#        line at finalize time but does NOT burn it into the video.
set -euo pipefail

SRC="${SRC:-$HOME/.claude/skills/show-n-tell/_assets/bg_music/tech_modern_pulse.mp3}"
OUT="${OUT:-$(cd "$(dirname "$0")/.." && pwd)/assets/bg_music_tech.mp3}"

# Total runtime of the FINAL mp4 = intro(4.0) + branded body + outro(5.0) - 2 x 0.5s crossfade.
# Pass it in, or pass the branded body duration and let this work it out.
if [ $# -lt 1 ]; then
  echo "usage: $0 <total_runtime_seconds | --from-branded <branded.mp4>>" >&2
  exit 2
fi

if [ "$1" = "--from-branded" ]; then
  BRANDED=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$2")
  TOTAL=$(python3 -c "print(round($BRANDED + 4.0 + 5.0 - 1.0, 3))")
else
  TOTAL="$1"
fi

[ -f "$SRC" ] || { echo "source track not found: $SRC" >&2; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Second segment is sized generously so the crossfaded body always clears TOTAL; the trim below
# sets the real length. 48s of tail covers a runtime up to ~235s.
ffmpeg -y -loglevel error -ss 0 -t 192 -i "$SRC" -ss 30 -t 48 -i "$SRC" \
  -filter_complex "[0:a][1:a]acrossfade=d=5:c1=tri:c2=tri[a]" -map "[a]" "$TMP/body.wav"

BODY=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$TMP/body.wav")
python3 -c "import sys; sys.exit(0 if $BODY >= $TOTAL else 1)" || {
  echo "body ${BODY}s is shorter than the ${TOTAL}s runtime — widen the second segment" >&2
  exit 1
}

FADE=$(python3 -c "print(round($TOTAL - 6.8, 3))")
ffmpeg -y -loglevel error -i "$TMP/body.wav" \
  -af "adelay=400|400,afade=t=out:st=${FADE}:d=6.8,atrim=end=${TOTAL}" -b:a 192k "$OUT"

echo "bed: $OUT  ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")s, target ${TOTAL}s)"
