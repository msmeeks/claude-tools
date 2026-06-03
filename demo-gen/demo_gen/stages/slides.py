"""Stage 4: Compose slide images (title, steps, closing) via Pillow."""

from __future__ import annotations

import functools
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from demo_gen.config import DemoConfig, DemoScript
from demo_gen.utils.color import hex_to_rgb

# macOS and Linux system font candidates for Pillow text rendering.
# Falls back to Pillow's built-in bitmap font as a last resort.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

import logging  # noqa: E402

logger = logging.getLogger(__name__)

_CAPTION_BAR_H = 80    # minimum caption bar height (pixels)
_CAPTION_LINE_H = 26   # additional height per wrapped caption line beyond the first


@functools.cache
def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                pass
    logger.warning("No TrueType font found for size %d; falling back to bitmap default", size)
    return ImageFont.load_default()


def _gradient_image(w: int, h: int, start_hex: str, end_hex: str) -> Image.Image:
    img = Image.new("RGB", (w, h))
    start = hex_to_rgb(start_hex)
    end = hex_to_rgb(end_hex)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(start[0] + (end[0] - start[0]) * t)
        g = int(start[1] + (end[1] - start[1]) * t)
        b = int(start[2] + (end[2] - start[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, w: int, fill: str, font: Any, wrap: int = 50) -> None:
    lines = textwrap.wrap(text, wrap)
    line_h = 28
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        draw.text((x, y + i * line_h), line, fill=fill, font=font)


def make_title_slide(
    product: str,
    demo_title: str,
    tagline: str,
    tokens: dict[str, Any],
    w: int,
    h: int,
) -> Image.Image:
    img = _gradient_image(w, h, tokens["brand_gradient_start"], tokens["brand_gradient_end"])
    draw = ImageDraw.Draw(img)
    f_sub = _load_font(26)
    f_main = _load_font(44)
    f_tag = _load_font(21)
    _draw_centered(draw, product,    int(h * 0.34), w, fill="#ffffff",  font=f_sub,  wrap=40)
    _draw_centered(draw, demo_title, int(h * 0.45), w, fill="#ffffff",  font=f_main, wrap=30)
    _draw_centered(draw, tagline,    int(h * 0.57), w, fill="#93c5fd",  font=f_tag,  wrap=60)
    return img


def make_step_slide(
    step_num: int,
    heading: str,
    caption: str,
    screenshot: Image.Image | None,
    tokens: dict[str, Any],
    w: int,
    h: int,
) -> Image.Image:
    """Render a step slide.

    With a screenshot: image fills (w × img_area_h), navy caption bar at the bottom.
    Without a screenshot: plain page_bg canvas with centered caption text.
    """
    lines = textwrap.wrap(caption, 90)
    bar_h = _CAPTION_BAR_H + max(0, len(lines) - 1) * _CAPTION_LINE_H
    img_area_h = max(1, h - bar_h)

    f_caption = _load_font(18)

    if screenshot is not None:
        src = screenshot.copy()
        src.thumbnail((w, img_area_h), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), hex_to_rgb(tokens["page_bg"]))
        px = (w - src.width) // 2
        py = (img_area_h - src.height) // 2
        canvas.paste(src, (px, py))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(0, img_area_h), (w, h)], fill=hex_to_rgb(tokens["brand_gradient_start"]))
        for i, line in enumerate(lines):
            draw.text((24, img_area_h + 16 + i * _CAPTION_LINE_H), line, font=f_caption, fill="#ffffff")
    else:
        canvas = Image.new("RGB", (w, h), hex_to_rgb(tokens["page_bg"]))
        draw = ImageDraw.Draw(canvas)
        full_text = "\n".join(lines)
        bbox = draw.multiline_textbbox((0, 0), full_text, font=f_caption, spacing=8)
        th = bbox[3] - bbox[1]
        tw = bbox[2] - bbox[0]
        draw.multiline_text(
            ((w - tw) // 2, (h - th) // 2),
            full_text, font=f_caption, fill=tokens["body_text"], spacing=8,
        )

    return canvas


def make_closing_slide(
    product: str,
    tagline: str,
    cta: str,
    tokens: dict[str, Any],
    w: int,
    h: int,
) -> Image.Image:
    img = _gradient_image(w, h, tokens["brand_gradient_start"], tokens["brand_gradient_end"])
    draw = ImageDraw.Draw(img)
    f_main = _load_font(30)
    f_sub = _load_font(20)
    _draw_centered(draw, product, int(h * 0.40), w, fill="#ffffff", font=f_main, wrap=40)
    _draw_centered(draw, tagline, int(h * 0.53), w, fill="#ffffff", font=f_sub,  wrap=60)
    _draw_centered(draw, cta,     int(h * 0.63), w, fill="#93c5fd", font=f_sub,  wrap=60)
    return img


def render_all_slides(
    script: DemoScript,
    screenshots: list[Image.Image],
    tokens: dict[str, Any],
    config: DemoConfig,
    tmp_dir: Path,
) -> list[Path]:
    """Render title + step + closing slides as PNG files. Returns list of paths."""
    w, h = config.resolution.width, config.resolution.height
    paths: list[Path] = []

    title = make_title_slide(config.product, script.title, script.tagline, tokens, w, h)
    title_path = tmp_dir / "slide_000_title.png"
    title.save(title_path)
    paths.append(title_path)

    for i, step in enumerate(script.steps):
        shot = None
        if step.screenshot_index is not None and step.screenshot_index < len(screenshots):
            shot = screenshots[step.screenshot_index]
        slide = make_step_slide(i + 1, step.heading, step.caption, shot, tokens, w, h)
        slide_path = tmp_dir / f"slide_{i + 1:03d}_step.png"
        slide.save(slide_path)
        paths.append(slide_path)

    closing = make_closing_slide(config.product, script.tagline, script.cta, tokens, w, h)
    closing_path = tmp_dir / f"slide_{len(script.steps) + 1:03d}_closing.png"
    closing.save(closing_path)
    paths.append(closing_path)

    return paths
