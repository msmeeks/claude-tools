"""Tests for script-stage screenshot assignment logic."""

from __future__ import annotations

from demo_gen.stages.script import _build_script_from_dict


def _raw_steps(n: int, idx_override: int | None = None) -> list[dict]:
    return [
        {
            "heading": f"Step {i + 1}",
            "caption": "Caption.",
            "talk_track": "Talk.",
            "screenshot_index": idx_override,
            "callout_label": None,
            "callout_region": None,
        }
        for i in range(n)
    ]


def _raw_script(n_steps: int, idx_override: int | None = None) -> dict:
    return {
        "title": "T",
        "tagline": "TL",
        "executive_summary": "ES.",
        "steps": _raw_steps(n_steps, idx_override),
        "takeaways": ["a"],
        "cta": "Go.",
    }


def test_null_index_falls_back_to_round_robin():
    script = _build_script_from_dict(_raw_script(4, idx_override=None), num_visuals=2)
    assert [s.screenshot_index for s in script.steps] == [0, 1, 0, 1]


def test_out_of_range_index_clamped_to_round_robin():
    script = _build_script_from_dict(_raw_script(3, idx_override=99), num_visuals=2)
    assert [s.screenshot_index for s in script.steps] == [0, 1, 0]


def test_negative_index_falls_back_to_round_robin():
    script = _build_script_from_dict(_raw_script(3, idx_override=-1), num_visuals=2)
    assert [s.screenshot_index for s in script.steps] == [0, 1, 0]


def test_single_visual_all_steps_get_zero():
    script = _build_script_from_dict(_raw_script(4, idx_override=None), num_visuals=1)
    assert all(s.screenshot_index == 0 for s in script.steps)


def test_valid_index_preserved():
    data = _raw_script(2)
    data["steps"][0]["screenshot_index"] = 0
    data["steps"][1]["screenshot_index"] = 1
    script = _build_script_from_dict(data, num_visuals=2)
    assert script.steps[0].screenshot_index == 0
    assert script.steps[1].screenshot_index == 1


def test_no_visuals_always_none():
    script = _build_script_from_dict(_raw_script(3, idx_override=0), num_visuals=0)
    assert all(s.screenshot_index is None for s in script.steps)
