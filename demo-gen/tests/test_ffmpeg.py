"""Tests for ffmpeg utility helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Imports are deferred into each test body so that cache_clear() runs before the
# module-level singleton is captured by the test runner.


def test_ffmpeg_binary_prefers_homebrew(tmp_path):
    """Returns Homebrew path when it exists."""
    homebrew = tmp_path / "ffmpeg"
    homebrew.touch()
    with patch("demo_gen.utils.ffmpeg._HOMEBREW_FFMPEG", str(homebrew)):
        from demo_gen.utils.ffmpeg import ffmpeg_binary
        ffmpeg_binary.cache_clear()
        result = ffmpeg_binary()
        ffmpeg_binary.cache_clear()
    assert result == str(homebrew)


def test_ffmpeg_binary_falls_back_to_path(tmp_path):
    """Falls back to PATH lookup when Homebrew path does not exist."""
    absent = str(tmp_path / "nonexistent_ffmpeg")
    fake_path = str(tmp_path / "ffmpeg_in_path")
    with (
        patch("demo_gen.utils.ffmpeg._HOMEBREW_FFMPEG", absent),
        patch("demo_gen.utils.ffmpeg.shutil.which", return_value=fake_path),
    ):
        from demo_gen.utils.ffmpeg import ffmpeg_binary
        ffmpeg_binary.cache_clear()
        result = ffmpeg_binary()
        ffmpeg_binary.cache_clear()
    assert result == fake_path


def test_ffmpeg_binary_raises_when_not_found(tmp_path):
    """Raises RuntimeError with installation hint when ffmpeg is not found anywhere."""
    absent = str(tmp_path / "nonexistent_ffmpeg")
    with (
        patch("demo_gen.utils.ffmpeg._HOMEBREW_FFMPEG", absent),
        patch("demo_gen.utils.ffmpeg.shutil.which", return_value=None),
    ):
        from demo_gen.utils.ffmpeg import ffmpeg_binary
        ffmpeg_binary.cache_clear()
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            ffmpeg_binary()
        ffmpeg_binary.cache_clear()


def test_has_libass_returns_false_when_filter_absent():
    from demo_gen.utils.ffmpeg import _ffmpeg_filters, has_libass
    _ffmpeg_filters.cache_clear()
    with patch("demo_gen.utils.ffmpeg.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="scale\npad\n")
        result = has_libass()
        _ffmpeg_filters.cache_clear()
    assert result is False


def test_has_libass_returns_true_when_filter_present():
    from demo_gen.utils.ffmpeg import _ffmpeg_filters, has_libass
    _ffmpeg_filters.cache_clear()
    with patch("demo_gen.utils.ffmpeg.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="scale\nsubtitles\nfps\n")
        result = has_libass()
        _ffmpeg_filters.cache_clear()
    assert result is True


def test_burn_subtitles_falls_back_to_copy_when_no_libass(tmp_path):
    """burn_subtitles copies the file unchanged and logs a warning when libass is absent."""
    src = tmp_path / "in.mp4"
    srt = tmp_path / "sub.srt"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"fake")
    srt.write_text("fake srt")

    with (
        patch("demo_gen.utils.ffmpeg.has_libass", return_value=False),
        patch("demo_gen.utils.ffmpeg._run") as mock_run,
    ):
        from demo_gen.utils.ffmpeg import burn_subtitles
        result = burn_subtitles(src, srt, out)
        call_args = mock_run.call_args[0][0]
        assert "-c" in call_args
        assert "copy" in call_args
        assert not any("subtitles=" in a for a in call_args)
    assert result == out


def test_burn_subtitles_uses_subtitles_filter_when_libass_present(tmp_path):
    """burn_subtitles embeds the subtitles filter when libass is available."""
    src = tmp_path / "in.mp4"
    srt = tmp_path / "sub.srt"
    out = tmp_path / "out.mp4"
    src.write_bytes(b"fake")
    srt.write_text("fake srt")

    with (
        patch("demo_gen.utils.ffmpeg.has_libass", return_value=True),
        patch("demo_gen.utils.ffmpeg._run") as mock_run,
    ):
        from demo_gen.utils.ffmpeg import burn_subtitles
        result = burn_subtitles(src, srt, out)
        call_args = mock_run.call_args[0][0]
        assert any("subtitles=" in a for a in call_args)
    assert result == out


def test_escape_filter_path_escapes_metacharacters():
    """Colons and single quotes in paths are backslash-escaped for libavfilter."""
    from demo_gen.utils.ffmpeg import _escape_filter_path
    path = Path("/tmp/demo:gen/sub's.srt")
    result = _escape_filter_path(path)
    assert ":" not in result.replace("\\:", "")
    assert "'" not in result.replace("\\'", "")
    assert "\\:" in result
    assert "\\'" in result


def test_safe_float_rejects_negative():
    from demo_gen.utils.ffmpeg import _safe_float
    with pytest.raises(ValueError, match="duration"):
        _safe_float(-1.0, "duration")


def test_safe_float_rejects_nan():
    import math

    from demo_gen.utils.ffmpeg import _safe_float
    with pytest.raises(ValueError):
        _safe_float(math.nan, "fps")


def test_safe_float_accepts_valid():
    from demo_gen.utils.ffmpeg import _safe_float
    assert _safe_float(5.0, "duration") == 5.0
    assert _safe_float(0, "duration") == 0.0
