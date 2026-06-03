# demo-gen — Project Overview

## Purpose

demo-gen is a standalone Python CLI tool that generates polished demo artifacts (HTML demo scripts and MP4 videos) for software products. It uses locally-running AI models for all processing — text-to-speech, image annotation, and script generation — so no data leaves your machine by default.

## Users

- Software engineers who need to generate demos for features they've built
- Developer-experience teams maintaining product documentation
- Anyone running the `/demo` Claude Code skill (which delegates to this CLI when installed)

## Tech stack

| Component | Library | Why |
|---|---|---|
| CLI | Click | Ergonomic, composable CLI with auto-generated help |
| Script generation | Ollama (local, default) / Anthropic SDK (cloud opt-in) | Local-first for privacy |
| TTS | kokoro-onnx | MIT license, ONNX runtime, runs natively on Apple Silicon |
| TTS fallback | piper-tts | Fast CPU inference for draft mode |
| Image processing | Pillow | Annotation rings, slide composition |
| Video assembly | ffmpeg (subprocess) | Industry standard; explicit arg lists for security |
| HTML rendering | Jinja2 (autoescape=True) | Template engine with XSS prevention |
| Data models | Pydantic v2 | Config validation and structured output |
| Terminal UI | Rich | Progress output and consent prompts |

## Architecture

The pipeline has 6 stages: script generation → asset loading → voiceover synthesis → slide rendering → video assembly → HTML rendering. All stages run in sequence in a single process. Temporary files live in a `TemporaryDirectory` context that cleans up on exit or exception. Output is written to a user-specified `--output-dir`.

## Privacy model

Local mode (default): all processing on-device, zero network calls after model weights are downloaded.
Cloud mode (`--cloud`): only text context files are sent to the Anthropic API; screenshots are never transmitted. A pre-flight consent prompt lists every file before any transmission.

## Key directories

| Path | Purpose |
|---|---|
| `demo_gen/` | Python package |
| `demo_gen/stages/` | Pipeline stage implementations |
| `demo_gen/models/` | Model weight downloader and TTS backends |
| `demo_gen/templates/` | Jinja2 HTML template and design token presets |
| `demo_gen/utils/` | Path validation, SRT generation, ffmpeg helpers |
| `tests/` | Unit and integration tests |
| `~/.demo-gen/models/` | Downloaded model weights (created at runtime) |
