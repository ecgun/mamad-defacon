#!/usr/bin/env bash
# Builds output/how-to-buy-usdt.mp4 (+ .srt subtitles and a thumbnail)
# from script.json and the scenes in src/. See README.md for setup.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}

$PY tools/narrate.py                 # voice-over, timeline, subtitles
node tools/render.cjs                # frames -> build/video.mp4
$PY tools/mix.py                     # voice + music + sound effects -> build/audio.wav

mkdir -p output
ffmpeg -y -loglevel error -i build/video.mp4 -i build/audio.wav -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart output/how-to-buy-usdt.mp4

node tools/render.cjs --stills 12 >/dev/null
cp build/stills/t0012.00.png output/thumbnail.png
echo "done: output/how-to-buy-usdt.mp4"
