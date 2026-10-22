#!/usr/bin/env bash
# Renders the ArchMAP 1.4.0 + 1.4.1 release video (1920x1080, 30 fps, 96 s).
# Needs: node + playwright (Chromium), python3 + numpy, ffmpeg.
# WORKERS parallel browsers split the 2880 frames (default 4).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out
WORKERS=${WORKERS:-4}; FRAMES=2880; STEP=$(( (FRAMES + WORKERS - 1) / WORKERS ))
python3 music.py                                   # out/music.wav
: > out/parts.txt
for ((k = 0; k < WORKERS; k++)); do
  a=$((k * STEP)); b=$(( (k + 1) * STEP < FRAMES ? (k + 1) * STEP : FRAMES ))
  node render_part.cjs "$a" "$b" "out/part$k.mp4" &
  echo "file 'part$k.mp4'" >> out/parts.txt
done
wait
ffmpeg -loglevel error -y -f concat -safe 0 -i out/parts.txt -i out/music.wav \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart out/ArchMAP-1.4-release.mp4
echo "out/ArchMAP-1.4-release.mp4"
