"""FFmpeg subprocess helpers. All calls use shell=False with explicit arg lists."""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Stock macOS does not ship libx264; Homebrew's build does.
_HOMEBREW_FFMPEG = "/opt/homebrew/bin/ffmpeg"


@lru_cache(maxsize=1)
def ffmpeg_binary() -> str:
    """Return the ffmpeg binary path, preferring Homebrew on macOS."""
    if Path(_HOMEBREW_FFMPEG).exists():
        return _HOMEBREW_FFMPEG
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise RuntimeError(
        "ffmpeg not found. Install via: brew install ffmpeg  (macOS) "
        "or  apt install ffmpeg  (Linux)"
    )


@lru_cache(maxsize=1)
def _ffmpeg_filters() -> str:
    """Return the full output of `ffmpeg -filters` for the resolved binary."""
    try:
        result = subprocess.run(
            [ffmpeg_binary(), "-filters"],
            capture_output=True, text=True, shell=False,  # noqa: S603
        )
        return result.stdout
    except subprocess.SubprocessError:
        return ""


def has_libass() -> bool:
    """Return True only if the available ffmpeg supports the subtitles filter (needs libass)."""
    return bool(_ffmpeg_filters()) and "subtitles" in _ffmpeg_filters()


def _escape_filter_path(p: Path) -> str:
    """Escape a file path for embedding inside an ffmpeg filter-graph argument string.

    libavfilter uses ':', '=', and "'" as metacharacters within filter option values.
    This escaping follows the ffmpeg filter-graph escaping convention.
    """
    s = str(p)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace(":", "\\:")
    return s


def _safe_float(v: float, name: str) -> float:
    """Validate that v is a finite non-negative number safe to embed in a filter string."""
    if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise ValueError(f"Invalid {name}: {v!r}")
    return float(v)


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with an explicit arg list. Never uses shell=True."""
    cmd = [ffmpeg_binary(), "-y"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check, shell=False)  # noqa: S603


def burn_subtitles(input_video: Path, srt_path: Path, output_video: Path) -> Path:
    """Burn SRT subtitles into a video file.

    Falls back to a stream-copy (no subtitles) when libass is not available.
    srt_path is escaped for ffmpeg filter-graph syntax before embedding.
    """
    if not has_libass():
        logger.warning(
            "ffmpeg lacks libass — subtitles will not be burned. "
            "Install ffmpeg with libass support (e.g. brew install ffmpeg --with-libass) "
            "or embed subtitles via a player-side .srt file."
        )
        _run(["-i", str(input_video), "-c", "copy", str(output_video)])
        return output_video

    escaped = _escape_filter_path(srt_path)
    subtitle_filter = (
        f"subtitles={escaped}:force_style='"
        "FontSize=32,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
        "Outline=2,Shadow=2,Alignment=2,MarginV=30'"
    )
    _run([
        "-i", str(input_video),
        "-vf", subtitle_filter,
        "-c:a", "copy",
        str(output_video),
    ])
    return output_video


def concat_videos(clip_paths: list[Path], output_path: Path, tmp_dir: Path) -> Path:
    """Concatenate video clips via ffmpeg concat demuxer."""
    list_file = tmp_dir / "concat_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clip_paths)
    )
    _run([
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path),
    ])
    return output_path


def image_to_video(image_path: Path, duration: float, output_path: Path, fps: int = 25) -> Path:
    """Convert a still image to a video clip of given duration."""
    safe_dur = _safe_float(duration, "duration")
    safe_fps = _safe_float(fps, "fps")
    _run([
        "-loop", "1",
        "-i", str(image_path),
        "-c:v", "libx264",
        "-t", str(safe_dur),
        "-pix_fmt", "yuv420p",
        "-vf", f"fps={int(safe_fps)}",
        str(output_path),
    ])
    return output_path


def add_audio_to_video(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """Mux a video file with an audio file."""
    _run([
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ])
    return output_path


def fade_video(input_path: Path, output_path: Path, duration: float = 0.5) -> Path:
    """Apply fade-in and fade-out to a video clip."""
    safe_dur = _safe_float(duration, "duration")
    _run([
        "-i", str(input_path),
        "-vf", f"fade=t=in:st=0:d={safe_dur},fade=t=out:st=0:d={safe_dur}",
        "-c:a", "copy",
        str(output_path),
    ])
    return output_path
