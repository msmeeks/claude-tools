"""Shared colour utilities."""

from __future__ import annotations


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse a CSS hex colour string (#rrggbb) to an RGB tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
