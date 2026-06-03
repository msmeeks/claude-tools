"""Tests for the shared colour utility."""

from __future__ import annotations

from demo_gen.utils.color import hex_to_rgb


def test_parses_with_hash():
    assert hex_to_rgb("#1e3a5f") == (30, 58, 95)


def test_parses_without_hash():
    assert hex_to_rgb("ffffff") == (255, 255, 255)


def test_black():
    assert hex_to_rgb("#000000") == (0, 0, 0)


def test_white():
    assert hex_to_rgb("#ffffff") == (255, 255, 255)
