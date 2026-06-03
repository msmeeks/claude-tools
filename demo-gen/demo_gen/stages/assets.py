"""Stage 2: Load and annotate screenshot/recording assets."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from demo_gen.config import DemoConfig, PolishLevel
from demo_gen.utils.color import hex_to_rgb
from demo_gen.utils.paths import sanitize_media_path

logger = logging.getLogger(__name__)

_HIGHLIGHT_COLOR = "#ef4444"
_HIGHLIGHT_BORDER = 4
_SHADOW_EXPAND = 8


def load_screenshots(config: DemoConfig, canvas_bg: str = "#f8f9fc") -> list[Image.Image]:
    """Load and resize all input screenshots to target resolution."""
    images: list[Image.Image] = []
    w, h = config.resolution.width, config.resolution.height
    for raw_path in config.screenshots:
        path = sanitize_media_path(raw_path)
        img = Image.open(path).convert("RGB")
        img = letterbox(img, w, h, canvas_bg)
        images.append(img)
    return images


def annotate(
    img: Image.Image,
    region: tuple[int, int, int, int] | None,
    polish: PolishLevel,
) -> Image.Image:
    """Draw a highlight annotation ring on the image if a region is specified."""
    if region is None or polish == PolishLevel.draft:
        return img
    img = img.copy()
    draw = ImageDraw.Draw(img)
    x, y, rw, rh = region
    for expand in range(_SHADOW_EXPAND, 0, -2):
        alpha = int(30 * (expand / _SHADOW_EXPAND))
        glow_color = (239, 68, 68, alpha)
        draw.rectangle(
            [x - expand, y - expand, x + rw + expand, y + rh + expand],
            outline=glow_color,
        )
    draw.rectangle(
        [x - _HIGHLIGHT_BORDER, y - _HIGHLIGHT_BORDER,
         x + rw + _HIGHLIGHT_BORDER, y + rh + _HIGHLIGHT_BORDER],
        outline=_HIGHLIGHT_COLOR,
        width=_HIGHLIGHT_BORDER,
    )
    return img


def extract_recording_still(
    recording_path: Path,
    width: int | None = None,
    height: int | None = None,
    canvas_bg: str = "#f8f9fc",
    timestamp_seconds: float = 1.0,
) -> Image.Image:
    """Extract a single frame from a video recording at the given timestamp."""
    recording_path = sanitize_media_path(recording_path)
    try:
        from moviepy import VideoFileClip  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("moviepy not installed. Run: pip install moviepy") from e

    with VideoFileClip(str(recording_path)) as clip:
        # Clamp to avoid seeking past the end of the clip
        seek_time = min(timestamp_seconds, max(0.0, clip.duration - 0.1))
        frame = clip.get_frame(seek_time)
    img = Image.fromarray(frame)
    if width is not None and height is not None:
        img = letterbox(img, width, height, canvas_bg)
    return img


def make_placeholder(
    width: int,
    height: int,
    text: str,
    bg_color: str = "#e5e7eb",
    text_color: str = "#6b7280",
) -> Image.Image:
    """Create a placeholder screenshot image with centered label text."""
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    # Pillow default font has fixed ~7px-per-char metrics; use that to centre the text
    tw = len(text) * 7
    th = 14
    draw.text(
        ((width - tw) // 2, (height - th) // 2),
        text,
        fill=text_color,
    )
    return img


def letterbox(img: Image.Image, target_w: int, target_h: int, bg: str = "#f8f9fc") -> Image.Image:
    """Resize image to fit within target dimensions, padding with canvas background."""
    iw, ih = img.size
    scale = min(target_w / iw, target_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    result = Image.new("RGB", (target_w, target_h), hex_to_rgb(bg))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    result.paste(resized, (offset_x, offset_y))
    return result
