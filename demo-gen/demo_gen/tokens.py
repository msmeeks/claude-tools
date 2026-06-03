"""Design token loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REQUIRED_KEYS = {
    "brand_gradient_start",
    "brand_gradient_end",
    "brand_primary",
    "brand_primary_light",
    "brand_primary_dark",
    "highlight_color",
    "highlight_shadow",
    "page_bg",
    "card_bg",
    "body_text",
    "secondary_text",
    "app_shell_sidebar_bg",
    "caption_border_width",
}

_DEFAULT_TOKENS: dict[str, Any] = {
    "brand_gradient_start": "#1e3a5f",
    "brand_gradient_end": "#2563eb",
    "brand_primary": "#2563eb",
    "brand_primary_light": "#dbeafe",
    "brand_primary_dark": "#1e40af",
    "highlight_color": "#ef4444",
    "highlight_shadow": "rgba(239,68,68,0.12)",
    "page_bg": "#f8f9fc",
    "card_bg": "#ffffff",
    "body_text": "#111827",
    "secondary_text": "#374151",
    "app_shell_sidebar_bg": "#111827",
    "caption_border_width": "4px",
    # Letterbox background for screenshot slides. Light by default so app UIs
    # (typically light-themed) don't get dark halos around them.
    "video_canvas_bg": "#f8f9fc",
}


def load(path: Path | None = None) -> dict[str, Any]:
    """Load design tokens from a JSON file, falling back to defaults for missing keys."""
    tokens = dict(_DEFAULT_TOKENS)
    if path is not None:
        with path.open() as f:
            overrides = json.load(f)
        if not isinstance(overrides, dict):
            raise ValueError(f"design_tokens.json must be a JSON object, got {type(overrides)}")
        tokens.update(overrides)
    missing = _REQUIRED_KEYS - tokens.keys()
    if missing:
        raise ValueError(f"design_tokens.json missing required keys: {sorted(missing)}")
    return tokens


def bundled_preset_path(name: str) -> Path:
    """Return path to a bundled token preset by name (e.g. 'hospitality-scheduled')."""
    return Path(__file__).parent / "templates" / "tokens" / f"{name}.json"
