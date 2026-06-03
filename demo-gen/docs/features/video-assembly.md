# Video Assembly

## Summary
Converts a `DemoScript` and its visual assets into an MP4 with burned subtitles, audio voiceovers, and visual transitions. Used by anyone invoking `demo-gen generate --format mp4|both`.

## Users / Use Cases
- **Engineer / DX team**: generates a narrated MP4 demo without any manual video editing.
- **Worker**: N/A

## Technologies
- **ffmpeg (subprocess)** — video/audio muxing, concat demuxer, fade filters, subtitle burning. All calls use explicit arg lists with `shell=False`.
- **Pillow** — slide image composition, letterboxing, highlight-ring annotation.
- **moviepy** — extracts a still frame from screen recordings (optional; only needed when `--recordings` is supplied).

## Technical Overview
Stage 5 of the 6-stage pipeline. `video.assemble()` receives rendered slide images, per-step WAV files, and timing info, then produces a single MP4 via sequential ffmpeg calls: each slide becomes a silent video clip (`image_to_video`), audio is muxed in (`add_audio_to_video`), fade transitions are applied at `standard`/`production` polish, all clips are joined with the concat demuxer, and subtitles are burned in last. No sound effects are inserted at any polish level.

## API Endpoints
None — CLI only.

## Key Files
| File | Purpose |
|---|---|
| `demo_gen/stages/video.py` | Stage 5 orchestrator: `assemble()` |
| `demo_gen/utils/ffmpeg.py` | ffmpeg helpers: `image_to_video`, `add_audio_to_video`, `fade_video`, `concat_videos`, `burn_subtitles` |
| `demo_gen/stages/assets.py` | Image helpers: `load_screenshots`, `extract_recording_still`, `letterbox`, `annotate` |
| `demo_gen/stages/slides.py` | Stage 4: renders each step to a PNG slide |
| `demo_gen/pipeline.py` | Orchestrates all 6 stages; resolves `video_canvas_bg` from tokens |

## Technical Detail

### No SFX policy
`generate_ding` has been removed from `ffmpeg.py`. No sound effects are inserted at any polish level (`draft`, `standard`, or `production`). The `demo.md` polish matrix reflects this: SFX row is "none" across all levels.

### Screenshot-first visual selection
`_build_script_from_dict` in `stages/script.py` applies a round-robin fallback: if the LLM returns a `null`, out-of-range, or non-integer `screenshot_index`, it falls back to `i % num_visuals` (where `i` is the step index). This guarantees every step that has visuals available always references one — no step silently degrades to a placeholder.

### Asset loading order
Stage 2 in `pipeline.py` loads assets in a defined order: all `config.screenshots` are loaded first (via `load_screenshots`), then one still frame per entry in `config.recordings` (via `extract_recording_still`). The combined list maps directly to the 0-based indices the LLM is prompted with, so the round-robin fallback stays coherent.

### `letterbox()` is public
`letterbox(img, target_w, target_h, bg)` in `assets.py` is a public function. It resizes the image proportionally and pads with a solid background colour to fill the target canvas. `load_screenshots` and `extract_recording_still` both call it internally. The background colour defaults to `#f8f9fc` (light, matching page backgrounds of typical light-themed web apps).

### `extract_recording_still()` dimensions
`extract_recording_still(recording_path, width, height, canvas_bg, timestamp_seconds)` now accepts optional `width` and `height`. When both are supplied it calls `letterbox` internally, matching the output size to the slide canvas. When omitted it returns the raw frame at native resolution.

### `video_canvas_bg` token
The design token `video_canvas_bg` (default `#f8f9fc`, light background) controls the letterbox padding colour for all slide images and recording stills. It is resolved in `pipeline.py` via `tok.get("video_canvas_bg", "#f8f9fc")` and passed through to `load_screenshots` and `extract_recording_still`. Override it in your project's `design_tokens.json`.

The default was changed from `#0f172a` (near-black navy) to `#f8f9fc` (light grey) because typical web app UIs are light-themed — dark letterbox padding creates jarring contrast halos around screenshots.

### `ffmpeg_binary()` auto-detection
`ffmpeg_binary()` in `utils/ffmpeg.py` is a cached function that returns the correct ffmpeg binary path. It prefers `/opt/homebrew/bin/ffmpeg` on macOS (Homebrew installation, includes libx264), falls back to `shutil.which("ffmpeg")`, and raises `RuntimeError` with installation instructions if ffmpeg is not found anywhere.

### `has_drawtext()` and `has_libass()`
Two cached capability-probe functions detect whether the available ffmpeg binary was compiled with libfreetype (`drawtext` filter) and libass (`subtitles` filter). Stock Homebrew ffmpeg lacks both. `burn_subtitles()` now checks `has_libass()` and falls back to a stream-copy with a logged warning when libass is absent, rather than raising an exception.

### Slide text rendering via Pillow
All text (title cards, caption bars, closing card) is rendered by Pillow `ImageDraw` onto PNG frames, not by ffmpeg `drawtext`. This works on any ffmpeg build. `slides.py` uses `_load_font(size)` which tries macOS and Linux system TrueType font paths and falls back to Pillow's built-in bitmap font.

### Caption bar layout
Step slides that have a screenshot use a two-region layout: the screenshot is scaled to fill `(w × h-barHeight)` with light letterbox padding, then a navy bar (`brand_gradient_start`) occupies the bottom `_CAPTION_BAR_H` pixels (default 80px, grows by `_CAPTION_LINE_H=26` per additional wrapped line) and contains the caption text in white.

### Consent prompt default
In `pipeline.py`, `Confirm.ask("Proceed?", default=False)` — the consent prompt defaults to **No**. Users must explicitly confirm before any file context is read or transmitted.

### `DemoOutput` dataclass
`DemoOutput` in `pipeline.py` is a `@dataclass` with three optional `Path` fields: `html_path`, `mp4_path`, `srt_path`. Fields default to `None`; only the fields relevant to the requested `--format` are populated.

## Changelog
| Date | Change |
|---|---|
| 2026-05-16 | Initial documentation |
| 2026-05-16 | SFX removed; screenshot round-robin fallback; `letterbox` public; `extract_recording_still` dimensions param; `video_canvas_bg` token; consent default=False; `DemoOutput` dataclass |
| 2026-05-16 | `ffmpeg_binary()` auto-detection prefers Homebrew on macOS; `has_libass()` capability probe; `_ffmpeg_filters()` shared helper; `burn_subtitles()` graceful degradation with filter-graph path escaping (`_escape_filter_path`); `_safe_float()` numeric guard on all filter-string embeddings; slide text via Pillow (not drawtext); caption bar layout with `img_area_h` floor guard; `hex_to_rgb` moved to `utils/color.py`; `extract_recording_still` default bg changed to `#f8f9fc`; `_make_silence`/`_pad_audio` now use `ffmpeg_binary()` |
