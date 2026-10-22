# Release video — ArchMAP 1.4.0 + 1.4.1

Motion-graphics video (PT-BR captions, ~96 s, 1920×1080 @ 30 fps) announcing
what shipped in 1.4.0 and 1.4.1 and the next updates on Sunday at 22h.

- `index.html` — the whole video as a deterministic timeline: `seek(t)` draws
  any instant. Open it in a browser to preview it live (loops).
- `render.cjs` — captures every frame with Playwright and pipes it to ffmpeg.
  `node render.cjs stills 3.5 20 54` writes single frames to `out/` for review.
- `music.py` — synthesizes the soundtrack (pad, bass, beat, transition whooshes)
  with numpy; no third-party audio assets, no licensing issues.
- `build.sh` — runs the three steps and muxes `out/ArchMAP-1.4-release.mp4`.

Visuals reuse the project's own assets: `resources/logo-negative*.png`
(converted to transparent white in `assets/`) and the Web UI screenshots in
`docs/assets/ui/`. Numbers come from `CHANGELOG.md`.

To edit text or timing, change the `CAP` array (captions) and the
`data-s`/`data-e` attributes (scene start/end, seconds) in `index.html`.
