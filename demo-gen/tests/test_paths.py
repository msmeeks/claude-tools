"""Tests for path validation utilities."""

import tempfile
from pathlib import Path

import pytest

from demo_gen.utils.paths import safe_output_filename, sanitize_output_dir


def test_safe_output_filename_strips_path_separators():
    assert "/" not in safe_output_filename("../../etc/passwd.png")
    assert "\\" not in safe_output_filename("..\\..\\evil.png")


def test_safe_output_filename_strips_null():
    result = safe_output_filename("file\x00name.png")
    assert "\x00" not in result


def test_safe_output_filename_strips_leading_dots():
    result = safe_output_filename("...hidden.png")
    assert not result.startswith(".")


def test_safe_output_filename_fallback():
    assert safe_output_filename("") == "output"
    assert safe_output_filename(".") == "output"


def test_sanitize_output_dir_allows_tmp():
    with tempfile.TemporaryDirectory() as tmp:
        result = sanitize_output_dir(tmp)
        assert result.is_absolute()


def test_sanitize_output_dir_allows_home_subdir():
    home_sub = Path.home() / ".demo-gen-test-path"
    result = sanitize_output_dir(home_sub)
    assert str(result).startswith(str(Path.home()))


def test_sanitize_output_dir_rejects_system_root():
    with pytest.raises(ValueError, match="outside allowed roots"):
        sanitize_output_dir("/etc/cron.d")
