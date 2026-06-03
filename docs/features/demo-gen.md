# demo-gen

## Summary
Python CLI that generates demo artifacts — a polished HTML script with screenshots/captions and an MP4 video with talk-track, subtitles, and brand-consistent slides. Local-first: TTS via Kokoro/Piper ONNX, script generation via Ollama by default. The `/demo` skill (`skills/demo/SKILL.md`) delegates to this binary when it is available on PATH or at `~/Code/claude-tools/demo-gen/.venv/bin/demo-gen`.

## Users / Use Cases
- **Developer / PM** finishing a feature: `/demo <feature>` produces an HTML walkthrough plus MP4 ready for the help-docs gallery.
- **Demo author** building a marketing-grade walkthrough: `--polish production --voice af_sky --format both` for a higher-quality TTS/subtitles pass.

## Technologies
- Python 3.11+, packaged via `pyproject.toml` (entry point `demo-gen = demo_gen.cli:main`).
- Pillow (slide rendering — title/step/closing cards).
- ffmpeg (encoding + concat + optional libass subtitle burn-in). Stock Homebrew ffmpeg lacks `libfreetype` and `libass`; the package probes capabilities at runtime.
- Kokoro ONNX (`af_sky` default voice) or Piper (faster, lower quality) for TTS.
- Ollama (local) or Anthropic Claude (opt-in `--cloud`) for script generation.
- Jinja2 for HTML templating.

## Technical Overview
A six-stage pipeline (`demo_gen/pipeline.py`): script → assets → voice → slides → video → html. Each stage is in `demo_gen/stages/`. Utilities in `demo_gen/utils/` handle ffmpeg capability probes, SRT generation, path validation, and color conversion. Templates and design tokens live in `demo_gen/templates/`. Unit tests in `tests/` cover config, color, ffmpeg probes, HTML escaping, paths, script, slides, and SRT parsing.

## Install
```bash
bash demo-gen/install.sh
```

`install.sh` is idempotent: creates `.venv` only if missing, then `pip install -e '.[kokoro]'`. Re-running is safe.

Optionally expose the binary on PATH:
```bash
ln -sf ~/Code/claude-tools/demo-gen/.venv/bin/demo-gen ~/.local/bin/demo-gen
```

## Key Files
| File | Purpose |
|---|---|
| `demo-gen/demo_gen/cli.py` | CLI entry point (argparse) |
| `demo-gen/demo_gen/pipeline.py` | Six-stage pipeline orchestration |
| `demo-gen/demo_gen/stages/` | script / assets / voice / slides / video / html stages |
| `demo-gen/demo_gen/utils/ffmpeg.py` | ffmpeg binary detection + libfreetype/libass probes |
| `demo-gen/demo_gen/utils/srt.py` | SRT subtitle generation |
| `demo-gen/demo.md` | Canonical demo specification (referenced by SKILL.md) |
| `demo-gen/meta/BRAND_VOICE.md` | Brand voice rules read by the script stage |
| `demo-gen/help-docs/` | Reference example output (HTML demos + screenshots) |
| `demo-gen/install.sh` | Idempotent venv + editable install bootstrap |
| `skills/demo/SKILL.md` | The `/demo` skill that invokes this binary |
