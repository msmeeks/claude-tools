import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

parse_issue_numbers = run_next_plan.parse_issue_numbers
get_sdlc_review_status = run_next_plan.get_sdlc_review_status
load_prd = run_next_plan.load_prd
save_prd = run_next_plan.save_prd


def test_parse_issue_numbers_extracts_strict_issue_lines():
    output = (
        "Some preamble noise\n"
        "ISSUE: #42\n"
        "random chatter mentioning ISSUE: #999 mid-sentence should not count\n"
        "ISSUE: 7\n"
    )
    assert parse_issue_numbers(output) == ["#42", "#7"]


def _valid_prd():
    return {
        "integration_branch": "integration/batch",
        "plans": [],
    }


def test_get_sdlc_review_status_defaults_to_pending_when_key_absent():
    assert get_sdlc_review_status(_valid_prd()) == "pending"


def test_get_sdlc_review_status_returns_explicit_value():
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    assert get_sdlc_review_status(data) == "complete"


def test_load_prd_does_not_mutate_data_when_status_key_absent(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    loaded = load_prd(prd_path)

    assert "sdlc_review_status" not in loaded


def test_save_prd_refuses_to_revert_complete_status_to_pending(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    save_prd(prd_path, data)

    regressed = _valid_prd()
    regressed["sdlc_review_status"] = "pending"
    with pytest.raises(SystemExit):
        save_prd(prd_path, regressed)

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def test_save_prd_allows_setting_complete_when_previously_pending(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "pending"
    save_prd(prd_path, data)

    data["sdlc_review_status"] = "complete"
    save_prd(prd_path, data)

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def _fake_subprocess_run(cmd, **kwargs):
    if cmd[:2] == ["gh", "auth"]:
        return type("R", (), {"returncode": 0})()
    if cmd[:2] == ["git", "symbolic-ref"]:
        return type("R", (), {"returncode": 0, "stdout": "refs/remotes/origin/main\n"})()
    if cmd[:2] == ["git", "status"]:
        # Working tree clean — ensure_committed_and_pushed should not need to ask Claude
        # to commit anything, only check whether a push is needed.
        return type("R", (), {"returncode": 0, "stdout": ""})()
    if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
        return type("R", (), {"returncode": 0, "stdout": "origin/main\n"})()
    if cmd[:2] == ["git", "rev-list"]:
        # Not ahead of upstream — _push_branch should no-op rather than actually pushing.
        return type("R", (), {"returncode": 0, "stdout": "0\n"})()
    raise AssertionError(f"unexpected subprocess.run call: {cmd}")


def test_run_sdlc_review_gate_marks_status_complete_after_running(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    calls = []

    def fake_invoke_claude(prompt, repo_root):
        calls.append(prompt)
        if "file a GitHub issue" in prompt:
            return "ISSUE: #11\nISSUE: #12\n"
        if "run /triage" in prompt:
            return "HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE"
        return "ok"

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"
    assert len(calls) == 4
    assert "#11" in calls[2] and "#12" in calls[2]


def test_run_sdlc_review_gate_dies_when_gh_not_authenticated(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    with (
        patch.object(
            run_next_plan.subprocess,
            "run",
            return_value=type("R", (), {"returncode": 1})(),
        ),
        pytest.raises(SystemExit),
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert load_prd(prd_path).get("sdlc_review_status", "pending") == "pending"
