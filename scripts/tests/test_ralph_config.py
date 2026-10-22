import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

load_ralph_config = run_next_plan.load_ralph_config


def _write(config_root, payload):
    config_root.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (config_root / "ralph.json").write_text(text)


def test_absent_file_gives_defaults(tmp_path):
    cfg = load_ralph_config(tmp_path)
    assert cfg["review"]["recipe"] == "agents"
    assert cfg["review"]["skill"] is None
    assert cfg["review"]["reviewers"] == list(run_next_plan.SDLC_REVIEW_AGENTS)
    assert cfg["review"]["registry"] is False
    assert cfg["plan_review"]["reviewers"] == list(run_next_plan.PLAN_REVIEW_AGENTS)


def test_absent_keys_fall_back_to_defaults(tmp_path):
    _write(tmp_path, {"review": {"recipe": "agents"}})
    cfg = load_ralph_config(tmp_path)
    assert cfg["review"]["reviewers"] == list(run_next_plan.SDLC_REVIEW_AGENTS)
    assert cfg["plan_review"]["reviewers"] == list(run_next_plan.PLAN_REVIEW_AGENTS)


def test_full_skill_config_is_loaded(tmp_path):
    _write(
        tmp_path,
        {
            "review": {
                "recipe": "skill",
                "skill": "my-review",
                "reviewers": ["sdlc-code-reviewer", "spec"],
                "registry": True,
            },
            "plan_review": {"reviewers": ["sdlc-security-reviewer"]},
        },
    )
    cfg = load_ralph_config(tmp_path)
    assert cfg["review"] == {
        "recipe": "skill",
        "skill": "my-review",
        "reviewers": ["sdlc-code-reviewer", "spec"],
        "registry": True,
    }
    assert cfg["plan_review"]["reviewers"] == ["sdlc-security-reviewer"]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        {"review": []},
        {"review": {"recipe": "bogus"}},
        {"review": {"recipe": "skill"}},
        {"review": {"recipe": "skill", "skill": ""}},
        {"review": {"recipe": "skill", "skill": 3}},
        {"review": {"recipe": "agents", "skill": "x"}},
        {"review": {"reviewers": []}},
        {"review": {"reviewers": "sdlc-code-reviewer"}},
        {"review": {"reviewers": ["a", "a"]}},
        {"review": {"reviewers": ["Bad Name"]}},
        {"review": {"reviewers": ["-lead"]}},
        {"review": {"reviewers": [1]}},
        {"review": {"registry": "yes"}},
        {"review": {"registry": 1}},
        {"plan_review": {"reviewers": []}},
        {"plan_review": {"reviewers": ["x", "x"]}},
        {"plan_review": []},
    ],
)
def test_invalid_config_dies(tmp_path, payload):
    _write(tmp_path, payload)
    with pytest.raises(SystemExit):
        load_ralph_config(tmp_path)


def test_unknown_top_level_key_warns_not_dies(tmp_path, capsys):
    _write(tmp_path, {"mystery": 1})
    cfg = load_ralph_config(tmp_path)
    assert cfg["review"]["recipe"] == "agents"
    assert "mystery" in capsys.readouterr().err
