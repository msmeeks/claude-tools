"""Tests for config models."""

import pytest
from pydantic import ValidationError

from demo_gen.config import DemoConfig, DemoScript, PolishLevel, Resolution, Step, TonePreset


def test_resolution_dimensions():
    assert Resolution.hd.width == 1280
    assert Resolution.hd.height == 720
    assert Resolution.fhd.width == 1920
    assert Resolution.fhd.height == 1080


def test_demo_config_defaults():
    config = DemoConfig(product="Test", feature="login")
    assert config.local is True
    assert config.polish == PolishLevel.standard
    assert config.tone == TonePreset.professional
    assert config.wpm == 150


def test_demo_config_wpm_bounds():
    with pytest.raises(ValidationError):
        DemoConfig(product="P", feature="f", wpm=50)
    with pytest.raises(ValidationError):
        DemoConfig(product="P", feature="f", wpm=500)


def test_demo_script_step():
    step = Step(heading="Create a Task", caption="Tasks track work.", talk_track="We create a task.")
    assert step.screenshot_index is None
    assert step.callout_label is None


def test_demo_script_roundtrip():
    script = DemoScript(
        title="Task Demo",
        tagline="Ship faster.",
        executive_summary="This demo shows task creation.",
        steps=[Step(heading="Create", caption="Create a task.", talk_track="We create.")],
        takeaways=["Easy to use", "Fast"],
        cta="Try it today.",
    )
    assert len(script.steps) == 1
    assert script.steps[0].heading == "Create"
