# demo-gen

Ship demos as fast as you ship code. `demo-gen` is a Python CLI that generates polished demo artifacts — an HTML demo script and an MP4 video with narration and subtitles — from screenshots, screen recordings, and doc files. All processing runs locally by default; no data leaves your machine.

## Features

- **HTML demo script** — slide-by-slide walkthrough with captions, ready to share
- **MP4 video** — auto-assembled from slides with narrated voice-over and burned-in subtitles
- **Local-first** — script generation via Ollama, TTS via Kokoro ONNX (runs natively on Apple Silicon)
- **Cloud opt-in** — route scripting through the Claude API with an explicit consent prompt before any data is sent
- **Claude Code skill** — the `/demo` skill in Claude Code delegates to this CLI when installed

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) on `PATH`
- [Ollama](https://ollama.com/) running locally (for local mode, default)

## Installation

```bash
pip install -e ".[kokoro]"         # with Kokoro TTS (recommended)
pip install -e ".[kokoro,piper]"   # add Piper TTS fallback
pip install -e ".[kokoro,image-gen]" # add local image generation
```

Then download model weights:

```bash
demo-gen download-models
```

## Quick start

```bash
demo-gen generate \
  --product "MyApp" \
  --feature "New dashboard" \
  --screenshot path/to/screen1.png \
  --screenshot path/to/screen2.png \
  --include-docs docs/features/dashboard.md \
  --output-dir ./output
```

Output files are written to `--output-dir` (default `./output`):
- `demo_script.html` — shareable HTML walkthrough
- `demo_video.mp4` — narrated MP4
- `demo_video.srt` — subtitle file

## CLI reference

```
demo-gen generate [OPTIONS]

  --product TEXT          Product name (required)
  --feature TEXT          Feature or demo name (required)
  --screenshot PATH       Screenshot file (repeatable)
  --recording PATH        Screen recording file (repeatable)
  --include-docs PATH     Doc file to include in scripting context (repeatable)
  --brand-voice PATH      Path to BRAND_VOICE.md
  --tokens PATH           design_tokens.json path
  --output-dir PATH       Output directory [default: ./output]
  --format [html|mp4|both]  Output format [default: both]
  --polish [draft|standard|polished]  Polish level [default: standard]
  --tone [professional|casual|technical|friendly]  Narration tone [default: professional]
  --voice VOICE           Kokoro voice [default: af_heart]
  --resolution [1280x720|1920x1080]  Video resolution [default: 1280x720]
  --wpm INT               Narration words per minute [default: 150]
  --local / --cloud       Use local Ollama (default) or Claude API
  --local-model TEXT      Ollama model name [default: llama3.2]
  --scope [feature|whole] Demo scope [default: feature]
  --title TEXT            Override demo title
  -v, --verbose

demo-gen list-voices      # show available TTS voices
demo-gen list-models      # show model download status
demo-gen download-models  # download model weights to ~/.demo-gen/models/
  --tts-only              # only download TTS models
  --force                 # re-download even if already present
```

## Cloud mode

To use Claude for script generation instead of a local Ollama model:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
demo-gen generate --cloud --product "MyApp" --feature "Dashboard" ...
```

Before any data is sent you will see a consent prompt listing every file to be transmitted. Screenshots are **never** sent to the cloud.

## Privacy

See [PRIVACY.md](PRIVACY.md) for the full data-flow disclosure.

## Development

```bash
pip install -e ".[dev]"
pytest
python3 -m ruff check .
```

## License

MIT
