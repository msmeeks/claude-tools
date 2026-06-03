"""demo-gen CLI entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from demo_gen import log_filter
from demo_gen.config import (
    DemoConfig,
    OutputFormat,
    PolishLevel,
    Resolution,
    TonePreset,
    VoicePreset,
)
from demo_gen.utils.paths import sanitize_doc_path, sanitize_media_path

console = Console()

_VOICE_CHOICES = [v.value for v in VoicePreset]
_POLISH_CHOICES = [p.value for p in PolishLevel]
_TONE_CHOICES = [t.value for t in TonePreset]
_FORMAT_CHOICES = [f.value for f in OutputFormat]
_RESOLUTION_CHOICES = [r.value for r in Resolution]


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s", stream=sys.stderr)
    log_filter.install()


@click.group()
def main() -> None:
    """demo-gen — ship demos as fast as you ship code.

    All processing runs locally by default. Use --cloud to route scripting
    through the Claude API (requires ANTHROPIC_API_KEY). See PRIVACY.md.
    """


@main.command()
@click.option("--product", required=True, help="Product name")
@click.option("--feature", required=True, help="Feature or demo name")
@click.option("--brand-voice", "brand_voice", type=click.Path(exists=True), default=None, help="Path to BRAND_VOICE.md")
@click.option("--include-docs", "include_docs", multiple=True, help="Doc files to include in scripting context")
@click.option("--screenshot", "screenshots", multiple=True, help="Screenshot file paths")
@click.option("--recording", "recordings", multiple=True, help="Screen recording file paths")
@click.option("--tokens", "tokens_path", type=click.Path(exists=True), default=None, help="design_tokens.json path")
@click.option("--output-dir", "output_dir", default="./output", show_default=True, help="Output directory")
@click.option("--format", "fmt", type=click.Choice(_FORMAT_CHOICES), default="both", show_default=True)
@click.option("--polish", type=click.Choice(_POLISH_CHOICES), default="standard", show_default=True)
@click.option("--tone", type=click.Choice(_TONE_CHOICES), default="professional", show_default=True)
@click.option("--voice", type=click.Choice(_VOICE_CHOICES), default="af_heart", show_default=True)
@click.option("--resolution", type=click.Choice(_RESOLUTION_CHOICES), default="1280x720", show_default=True)
@click.option("--wpm", default=150, show_default=True, help="Narration words per minute")
@click.option("--local/--cloud", "local_mode", default=True, show_default=True, help="Use local LLM (default) or Claude API")
@click.option("--local-model", "local_model", default="llama3.2", show_default=True, help="Ollama model name")
@click.option("--scope", type=click.Choice(["feature", "whole"]), default="feature", show_default=True)
@click.option("--title", default=None, help="Override demo title")
@click.option("-v", "--verbose", is_flag=True, default=False)
def generate(
    product: str,
    feature: str,
    brand_voice: str | None,
    include_docs: tuple[str, ...],
    screenshots: tuple[str, ...],
    recordings: tuple[str, ...],
    tokens_path: str | None,
    output_dir: str,
    fmt: str,
    polish: str,
    tone: str,
    voice: str,
    resolution: str,
    wpm: int,
    local_mode: bool,
    local_model: str,
    scope: str,
    title: str | None,
    verbose: bool,
) -> None:
    """Generate a demo artifact (HTML script and/or MP4 video)."""
    _setup_logging(verbose)

    # Validate and sanitize all input paths up front
    try:
        validated_screenshots = [sanitize_media_path(p) for p in screenshots]
        validated_recordings = [sanitize_media_path(p) for p in recordings]
        validated_docs = [sanitize_doc_path(p) for p in include_docs]
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    config = DemoConfig(
        product=product,
        feature=feature,
        brand_voice_path=Path(brand_voice) if brand_voice else None,
        include_docs=validated_docs,
        screenshots=validated_screenshots,
        recordings=validated_recordings,
        tokens_path=Path(tokens_path) if tokens_path else None,
        output_dir=Path(output_dir),
        format=OutputFormat(fmt),
        polish=PolishLevel(polish),
        tone=TonePreset(tone),
        voice=VoicePreset(voice),
        resolution=Resolution(resolution),
        wpm=wpm,
        local=local_mode,
        local_model=local_model,
        scope=scope,
        title=title,
    )

    from demo_gen import pipeline  # noqa: PLC0415
    output = pipeline.run(config)

    console.print("\n[bold green]Done.[/bold green]")
    if output.html_path:
        console.print(f"  HTML: {output.html_path}")
    if output.mp4_path:
        console.print(f"  MP4:  {output.mp4_path}")
    if output.srt_path:
        console.print(f"  SRT:  {output.srt_path}")


@main.command("list-voices")
def list_voices() -> None:
    """List available TTS voices."""
    _setup_logging(False)
    console.print("\n[bold]Kokoro ONNX voices:[/bold]")
    for v in VoicePreset:
        if v != VoicePreset.piper:
            console.print(f"  {v.value}")
    console.print("\n[bold]Piper:[/bold] Install piper-tts and run demo-gen download-models --tts-only")


@main.command("list-models")
def list_models() -> None:
    """Show model download status."""
    _setup_logging(False)
    from demo_gen.models import downloader  # noqa: PLC0415
    manifest = downloader.load_manifest()
    console.print("\n[bold]Model status:[/bold]")
    for key in manifest:
        status = "[green]✓[/green]" if downloader.is_downloaded(key) else "[yellow]not downloaded[/yellow]"
        console.print(f"  {key}: {status}")


@main.command("download-models")
@click.option("--tts-only", is_flag=True, help="Only download TTS models")
@click.option("--force", is_flag=True, help="Re-download even if already present")
def download_models(tts_only: bool, force: bool) -> None:
    """Download AI model weights to ~/.demo-gen/models/."""
    _setup_logging(False)
    from demo_gen.models import downloader  # noqa: PLC0415
    manifest = downloader.load_manifest()
    keys = [k for k in manifest if not tts_only or "kokoro" in k or "piper" in k]
    for key in keys:
        console.print(f"Downloading [bold]{key}[/bold]…")
        try:
            path = downloader.download(key, force=force)
            console.print(f"  [green]✓[/green] {path}")
        except Exception as e:
            console.print(f"  [red]✗[/red] {e}")
