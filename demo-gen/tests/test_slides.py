"""Tests for slide rendering (Stage 4)."""

from __future__ import annotations

from PIL import Image

from demo_gen.stages.slides import (
    _load_font,
    make_closing_slide,
    make_step_slide,
    make_title_slide,
)
from demo_gen.tokens import _DEFAULT_TOKENS


def _tokens() -> dict:
    return dict(_DEFAULT_TOKENS)


def test_load_font_returns_font_object():
    """_load_font always returns something — either TrueType or bitmap fallback."""
    from PIL.ImageFont import FreeTypeFont, ImageFont
    font = _load_font(18)
    assert isinstance(font, (FreeTypeFont, ImageFont))


def test_load_font_cache_returns_same_object():
    # functools.cache exposes cache_clear just like lru_cache
    _load_font.cache_clear()
    f1 = _load_font(18)
    f2 = _load_font(18)
    assert f1 is f2
    _load_font.cache_clear()  # restore so other tests see a clean cache


def test_title_slide_correct_size():
    img = make_title_slide("Product", "Title", "Tagline", _tokens(), 1280, 720)
    assert img.size == (1280, 720)


def test_title_slide_is_rgb():
    img = make_title_slide("P", "T", "TL", _tokens(), 640, 360)
    assert img.mode == "RGB"


def test_step_slide_with_screenshot_correct_size():
    tok = _tokens()
    screenshot = Image.new("RGB", (1280, 800), "#cccccc")
    img = make_step_slide(1, "Do a thing", "Caption text here.", screenshot, tok, 1280, 720)
    assert img.size == (1280, 720)


def test_step_slide_without_screenshot_uses_page_bg():
    tok = _tokens()
    img = make_step_slide(2, "Step heading", "No screenshot.", None, tok, 1280, 720)
    assert img.size == (1280, 720)
    # Top-left pixel should be close to page_bg (#f8f9fc)
    r, g, b = img.getpixel((10, 10))
    assert r > 200 and g > 200 and b > 200


def test_step_slide_caption_bar_exists_in_lower_region():
    """When a screenshot is supplied the bottom bar should use the brand colour."""
    tok = _tokens()
    screenshot = Image.new("RGB", (1280, 800), "#ffffff")
    img = make_step_slide(1, "Heading", "Caption text.", screenshot, tok, 1280, 720)
    # Bottom strip should be the brand navy, not white
    r, g, b = img.getpixel((640, 710))
    # Brand gradient start is #1e3a5f — dark, not white
    assert r < 100


def test_closing_slide_correct_size():
    img = make_closing_slide("P", "TL", "CTA", _tokens(), 1280, 720)
    assert img.size == (1280, 720)


def test_render_all_slides_returns_correct_count(tmp_path):
    from demo_gen.config import DemoConfig, DemoScript, PolishLevel, Resolution, Step
    from demo_gen.stages.slides import render_all_slides

    steps = [
        Step(heading="Step 1", caption="Cap 1", talk_track="Talk 1", screenshot_index=0),
        Step(heading="Step 2", caption="Cap 2", talk_track="Talk 2", screenshot_index=None),
    ]
    script = DemoScript(
        title="T", tagline="TL", executive_summary="ES.",
        steps=steps, takeaways=["a"], cta="Go.",
    )
    config = DemoConfig(product="P", feature="f", resolution=Resolution.hd, polish=PolishLevel.standard)
    screenshots = [Image.new("RGB", (1280, 800), "#aabbcc")]
    paths = render_all_slides(script, screenshots, _tokens(), config, tmp_path)
    # title + 2 steps + closing = 4
    assert len(paths) == 4
    for p in paths:
        assert p.exists()
