# Changelog

## [2026-05-16] — ffmpeg portability & slide rendering improvements

- **`ffmpeg_binary()` auto-detection**: prefers `/opt/homebrew/bin/ffmpeg` on macOS (has libx264); falls back to `shutil.which`; raises `RuntimeError` with install instructions if absent. Cached via `@lru_cache`.
- **`has_drawtext()` / `has_libass()` capability probes**: cached functions that check whether the available ffmpeg was compiled with libfreetype/libass. Stock Homebrew ffmpeg lacks both.
- **`burn_subtitles()` graceful degradation**: when `has_libass()` is False, falls back to stream-copy with a logged warning instead of crashing.
- **Slide text via Pillow**: all text on title cards, caption bars, and closing cards is now rendered by Pillow `ImageDraw`, not ffmpeg `drawtext`. Works on any ffmpeg build.
- **`_load_font()` with system font probing**: tries macOS and Linux TrueType font candidates; falls back to Pillow bitmap font. Cached via `@functools.cache`.
- **Caption bar layout**: screenshot slides use a two-region layout — screenshot fills top area, navy caption bar at bottom.
- **`video_canvas_bg` default changed to `#f8f9fc`**: light background avoids dark halos around light-themed app screenshots. Was `#0f172a`.
- **Security fixes**: `_escape_filter_path()` escapes `:`, `'`, and `\` in SRT paths before embedding in ffmpeg filter-graph strings; `_safe_float()` validates numeric values before embedding in `-vf`/`-af` strings; `_make_silence`/`_pad_audio` in `video.py` now call `ffmpeg_binary()` instead of bare `"ffmpeg"`.
- **`_ffmpeg_filters()` shared helper**: single cached subprocess call for both capability probes; `has_drawtext()` removed (unused).
- **`hex_to_rgb` moved to `utils/color.py`**: eliminates duplicate implementations in `slides.py` and `assets.py`.
- **`img_area_h` floor guard**: `max(1, h - bar_h)` prevents negative canvas dimensions with very long captions.
- **23 new tests**: `test_ffmpeg.py` covers binary detection, capability probes, subtitle fallback/happy-path, path escaping, and `_safe_float`; `test_slides.py` covers font loading, slide dimensions, caption bar, and `render_all_slides`; `test_color.py` covers `hex_to_rgb`.

## [2026-05-16] — Video assembly hardening & token additions

- **SFX removed**: `generate_ding` deleted from `ffmpeg.py`; all polish levels now produce silent transitions. `demo.md` polish matrix updated.
- **Screenshot-first visuals**: `_build_script_from_dict` applies round-robin fallback (`i % num_visuals`) when the LLM returns a null or invalid `screenshot_index`, so every step always has a visual when assets exist.
- **`letterbox()` made public** in `assets.py`; `extract_recording_still()` now accepts optional `width`/`height` and calls `letterbox` internally.
- **`video_canvas_bg` token** (`#0f172a`) added to `default.json`, `hospitality-scheduled.json`, and `DESIGN_BRIEF.md` Motion section.
- **`DemoOutput` converted to `@dataclass`** in `pipeline.py`.
- **Consent prompt default changed to `False`** in `pipeline.py` (`Confirm.ask("Proceed?", default=False)`).

## [0.1.0] — 2026-05-16

### Added

- Initial implementation of `demo-gen` CLI tool
- 6-stage pipeline: script generation → asset loading → voiceover → slides → video → HTML
- Local-first architecture: Ollama LLM + Kokoro ONNX TTS by default; no data leaves the machine
- `--cloud` opt-in for Claude API scripting with mandatory pre-flight consent prompt
- Jinja2 HTML output with `autoescape=True`; Variant B canonical template (aside, step-header, 4px caption border)
- Design token system (`design_tokens.json`) for per-project branding overrides
- Bundled presets: `default` and `hospitality-scheduled`
- `--polish draft|standard|production` with concrete feature matrix (screenshots, callouts, SFX, IntersectionObserver)
- `--tone professional|casual|energetic` system prompt presets
- Kokoro ONNX and Piper TTS backends; NullBackend for draft/offline mode
- FFmpeg-based video assembly: title card, step slides, closing card, SFX, fade transitions, burned subtitles
- SHA-256 checksum verification for all downloaded model weights
- Path validation: suffix allowlist, anti-traversal, reject `-`-prefix paths
- Custom log filter stripping API keys, base64, and file contents from all log output
- `PRIVACY.md`, `BRAND_VOICE.md`, `DESIGN_BRIEF.md`, `demo.md` scaffold files
- Unit test suite: config, SRT, path validation, HTML rendering (including SSTI/XSS tests)
- `demo-gen generate`, `list-voices`, `list-models`, `download-models` CLI commands
