#!/usr/bin/env bash
# Renders the ArchMAP 1.4.0 + 1.4.1 release video (1920x1080, 30 fps, ~96 s).
# Needs: node + playwright (Chromium), python3 + numpy, ffmpeg.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out
python3 music.py                      # out/music.wav (synthesized soundtrack)
node render.cjs video                  # out/video_noaudio.mp4 (frame-by-frame capture)
ffmpeg -loglevel error -y -i out/video_noaudio.mp4 -i out/music.wav \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart out/ArchMAP-1.4-release.mp4
echo "out/ArchMAP-1.4-release.mp4"
