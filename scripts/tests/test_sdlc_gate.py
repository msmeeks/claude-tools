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


def test_review_runs_parallel_for_first_two_attempts_then_serial():
    # First two gate runs fan reviewers out in parallel; after parallel has hit the
    # session limit twice, subsequent runs execute reviewers one at a time.
    assert run_next_plan._review_runs_parallel(1) is True
    assert run_next_plan._review_runs_parallel(2) is True
    assert run_next_plan._review_runs_parallel(3) is False
    assert run_next_plan._review_runs_parallel(5) is False


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


def test_load_prd_accepts_review_completed_agents_field(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_completed_agents"] = ["sdlc-code-reviewer", "sdlc-test-reviewer"]
    save_prd(prd_path, data)

    loaded = load_prd(prd_path)

    assert loaded["sdlc_review_completed_agents"] == ["sdlc-code-reviewer", "sdlc-test-reviewer"]


def test_load_prd_rejects_non_string_completed_agents(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_completed_agents"] = [7]
    save_prd(prd_path, data)

    with pytest.raises(SystemExit):
        load_prd(prd_path)


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


def test_run_sdlc_review_gate_waits_out_a_session_limit_then_completes(tmp_path):
    # Regression: a session limit must NOT be misread as a human-review need, and must NOT
    # bail — the gate waits for the reset (like the main loop) and retries automatically.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    state = {"review_calls": 0}

    def fake_invoke_claude(prompt, repo_root):
        if "Dispatch these review agents" in prompt or "review agent on the diff" in prompt:
            state["review_calls"] += 1
            if state["review_calls"] == 1:
                return "You've hit your session limit · resets 3:20am (America/New_York)"
            return "ok"
        if "file a GitHub issue" in prompt:
            return "ISSUE: #11\nISSUE: #12\n"
        if "run /triage" in prompt:
            return "HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE"
        return "ok"

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    assert get_sdlc_review_status(load_prd(prd_path)) != "needs-human"
    assert slept  # it waited for the reset before retrying


def test_run_sdlc_review_gate_resumes_triage_after_waiting_out_a_limit(tmp_path):
    # The specific failure that motivated this: reviews + issue-filing succeed, then triage
    # hits the limit. The gate waits, then re-runs ONLY triage (reviews already complete,
    # issues already filed) — no needs-human, no duplicate issue filing.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    state = {"triage_calls": 0, "file_calls": 0}

    def fake_invoke_claude(prompt, repo_root):
        if "run /triage" in prompt:
            state["triage_calls"] += 1
            if state["triage_calls"] == 1:
                return "You've hit your session limit · resets 3:20am"
            return "HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE"
        if "file a GitHub issue" in prompt:
            state["file_calls"] += 1
            return "ISSUE: #11\nISSUE: #12\n"
        return "ok"

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    data = load_prd(prd_path)
    assert get_sdlc_review_status(data) != "needs-human"
    assert data["sdlc_finding_issues"] == [11, 12]
    assert state["file_calls"] == 1  # issues filed once, not re-filed on the retry


def test_run_sdlc_review_gate_escalates_to_serial_after_two_parallel_limit_hits(tmp_path):
    # Two parallel attempts hit the limit; the gate then runs reviewers one at a time.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = []

    def fake_invoke_claude(prompt, repo_root):
        prompts.append(prompt)
        if "Dispatch these review agents" in prompt:  # parallel dispatch
            return "You've hit your session limit · resets 3:20am"
        if "review agent on the diff" in prompt:  # serial single-agent
            return "ok"
        if "file a GitHub issue" in prompt:
            return "ISSUE: #11\n"
        if "run /triage" in prompt:
            return "HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE"
        return "ok"

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    parallel_calls = [p for p in prompts if "Dispatch these review agents" in p]
    serial_calls = [p for p in prompts if "review agent on the diff" in p]
    assert len(parallel_calls) == run_next_plan.REVIEW_PARALLEL_ATTEMPTS  # two parallel tries
    assert len(serial_calls) == len(run_next_plan.SDLC_REVIEW_AGENTS)  # then each agent serially
    assert (
        load_prd(prd_path)["sdlc_review_completed_agents"]
        == list(run_next_plan.SDLC_REVIEW_AGENTS)
    )


def test_run_sdlc_review_gate_gives_up_incomplete_after_max_attempts_not_needs_human(tmp_path):
    # If the limit never resets, the gate bounds its waiting to MAX_REVIEW_ATTEMPTS and then
    # gives up as 'incomplete' — it must NOT wait forever and must NOT claim needs-human.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake_invoke_claude(prompt, repo_root):
        return "You've hit your session limit · resets 3:20am"

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "incomplete"
    assert get_sdlc_review_status(load_prd(prd_path)) != "needs-human"
    assert len(slept) == run_next_plan.MAX_REVIEW_ATTEMPTS  # bounded, not infinite


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
