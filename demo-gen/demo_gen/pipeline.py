"""Pipeline orchestrator: consent prompt → stages 1–6 → output."""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from demo_gen import tokens as token_loader
from demo_gen.config import DemoConfig, OutputFormat
from demo_gen.stages import assets, html, script, slides, video, voice
from demo_gen.utils.paths import safe_output_filename, sanitize_output_dir

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class DemoOutput:
    html_path: Path | None = field(default=None)
    mp4_path: Path | None = field(default=None)
    srt_path: Path | None = field(default=None)


def _consent_prompt(config: DemoConfig) -> None:
    """Display pre-flight data disclosure. Required when cloud mode or any docs are included."""
    if config.local and not config.include_docs and not config.brand_voice_path:
        return

    console.print("\n[bold yellow]⚠  Data disclosure[/bold yellow]")
    if not config.local:
        console.print(
            "[yellow]Cloud mode is enabled. The following will be sent to the Anthropic API:[/yellow]"
        )
        if config.brand_voice_path:
            console.print(f"  • {config.brand_voice_path}")
        for p in config.include_docs:
            console.print(f"  • {p}")
        console.print(
            "[dim]Also included: product name, feature name, and asset count (not asset content).[/dim]"
        )
        console.print(
            "[dim]Screenshots and recordings are NOT sent — only text context files.[/dim]"
        )
        console.print(
            "[dim]Anthropic may retain inputs for safety review. "
            "See PRIVACY.md for details.[/dim]\n"
        )
    else:
        console.print(
            "[yellow]The following files will be read for local scripting context:[/yellow]"
        )
        if config.brand_voice_path:
            console.print(f"  • {config.brand_voice_path}")
        for p in config.include_docs:
            console.print(f"  • {p}")
        console.print()

    if not Confirm.ask("Proceed?", default=False):
        raise SystemExit("Aborted by user.")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def run(config: DemoConfig) -> DemoOutput:
    if not config.local:
        import os  # noqa: PLC0415
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "Error: ANTHROPIC_API_KEY is not set.\n"
                "Use --local (default) for air-gapped operation, or set ANTHROPIC_API_KEY."
            )

    _consent_prompt(config)

    output_dir = sanitize_output_dir(config.output_dir)
    output_dir.mkdir(mode=0o750, parents=True, exist_ok=True)

    tok = token_loader.load(config.tokens_path)
    if not tok.get("tagline"):
        tok["tagline"] = ""
    canvas_bg: str = tok.get("video_canvas_bg", "#f8f9fc")

    output = DemoOutput()
    slug = _slug(config.feature)
    output_slug = safe_output_filename(slug)

    with tempfile.TemporaryDirectory(prefix="demo-gen-", dir="/tmp") as tmp_str:
        tmp_dir = Path(tmp_str)

        # Stage 1: Generate script
        console.print("[bold blue]Stage 1/6:[/bold blue] Generating script…")
        demo_script = script.generate(config)

        # Stage 2: Load assets — screenshots first, then one still per recording.
        # Order matches the visual indices told to the LLM in script.generate().
        console.print("[bold blue]Stage 2/6:[/bold blue] Loading assets…")
        w, h = config.resolution.width, config.resolution.height
        screenshots_pil = assets.load_screenshots(config, canvas_bg)
        for rec_path in config.recordings:
            try:
                still = assets.extract_recording_still(rec_path, w, h, canvas_bg)
                screenshots_pil.append(still)
            except Exception as exc:
                logger.warning("Could not extract still from recording %s: %s", rec_path.name, exc)

        # Stage 3: Voiceovers (skip for HTML-only)
        wav_paths: list[Path] = []
        durations: list[float] = []
        if config.format in (OutputFormat.mp4, OutputFormat.both):
            console.print("[bold blue]Stage 3/6:[/bold blue] Generating voiceovers…")
            wav_paths, durations = voice.generate_voiceovers(demo_script, config, tmp_dir)
        else:
            console.print("[dim]Stage 3/6: Skipped (HTML-only mode)[/dim]")

        # Stage 4: Render slides (skip for HTML-only)
        slide_paths: list[Path] = []
        if config.format in (OutputFormat.mp4, OutputFormat.both):
            console.print("[bold blue]Stage 4/6:[/bold blue] Rendering slides…")
            slide_paths = slides.render_all_slides(demo_script, screenshots_pil, tok, config, tmp_dir)
        else:
            console.print("[dim]Stage 4/6: Skipped (HTML-only mode)[/dim]")

        # Stage 5: Assemble video
        if config.format in (OutputFormat.mp4, OutputFormat.both):
            console.print("[bold blue]Stage 5/6:[/bold blue] Assembling video…")
            tmp_mp4 = tmp_dir / f"{output_slug}.mp4"
            video.assemble(demo_script, slide_paths, wav_paths, durations, config, tmp_dir, tmp_mp4)
            dest_mp4 = output_dir / f"{output_slug}.mp4"
            shutil.move(tmp_mp4, dest_mp4)
            output.mp4_path = dest_mp4
            tmp_srt = tmp_dir / "subtitles.srt"
            if tmp_srt.exists():
                dest_srt = output_dir / f"{output_slug}.srt"
                shutil.copy2(tmp_srt, dest_srt)
                output.srt_path = dest_srt
        else:
            console.print("[dim]Stage 5/6: Skipped (HTML-only mode)[/dim]")

        # Stage 6: HTML
        if config.format in (OutputFormat.html, OutputFormat.both):
            console.print("[bold blue]Stage 6/6:[/bold blue] Rendering HTML…")
            screenshot_rel: list[str] = []
            for screenshot_path in config.screenshots:
                dest = output_dir / "assets" / screenshot_path.name
                dest.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
                shutil.copy2(screenshot_path, dest)
                screenshot_rel.append(f"assets/{screenshot_path.name}")
            html_path = output_dir / f"{output_slug}.html"
            html.render(demo_script, config, tok, screenshot_rel, html_path)
            output.html_path = html_path
        else:
            console.print("[dim]Stage 6/6: Skipped (MP4-only mode)[/dim]")

    return output
