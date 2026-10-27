import importlib.util
import json
import subprocess
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

# A representative sample of the CLI's real session-limit output. The specific clock time
# is arbitrary and load-bearing to nothing: detection is time-independent (it keys on the
# non-zero exit code), and the wait is parsed generically. Kept as one named fixture so no
# stray real timestamp reads as significant anywhere.
SAMPLE_LIMIT_MESSAGE = "You've hit your session limit · resets 3:20am (America/New_York)"


def _init_repo_with_commit(path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    (path / "f.txt").write_text("a\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "one"], cwd=path, check=True)
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True)
    return r.stdout.strip()


def test_compute_review_range_uses_default_branch_when_no_baseline(tmp_path):
    _init_repo_with_commit(tmp_path)
    rng = run_next_plan._compute_review_range(tmp_path, {}, "main")
    assert rng == "main...HEAD"


def test_compute_review_range_uses_baseline_when_present_and_reachable(tmp_path):
    sha = _init_repo_with_commit(tmp_path)
    rng = run_next_plan._compute_review_range(tmp_path, {"last_reviewed_sha": sha}, "main")
    assert rng == f"{sha}..HEAD"


def test_compute_review_range_falls_back_when_baseline_missing_from_repo(tmp_path):
    _init_repo_with_commit(tmp_path)
    rng = run_next_plan._compute_review_range(
        tmp_path, {"last_reviewed_sha": "0" * 40}, "main"
    )
    assert rng == "main...HEAD"


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


def test_load_prd_accepts_round_filed_issues_field(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_round_filed_issues"] = [11, 12]
    save_prd(prd_path, data)

    assert load_prd(prd_path)["sdlc_round_filed_issues"] == [11, 12]


def test_load_prd_rejects_non_int_round_filed_issues(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_round_filed_issues"] = ["seven"]
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


def test_save_prd_terminal_guard_still_fires_with_round_scratch_field_present(tmp_path):
    # The new sdlc_round_filed_issues scratch field must not weaken the complete→pending
    # anti-revert latch — the refusal still fires whether or not the field is present.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    data["sdlc_round_filed_issues"] = [11]
    save_prd(prd_path, data)

    data["sdlc_review_status"] = "pending"  # no baseline → not a legitimate re-arm
    with pytest.raises(SystemExit):
        save_prd(prd_path, data)

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def test_save_prd_allows_setting_complete_when_previously_pending(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "pending"
    save_prd(prd_path, data)

    data["sdlc_review_status"] = "complete"
    save_prd(prd_path, data)

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def test_save_prd_allows_rearm_complete_to_pending_when_baseline_present(tmp_path):
    # A completed review carrying a review baseline may be re-armed to 'pending' for a new
    # incremental round — the one intentional terminal→pending transition.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    data["last_reviewed_sha"] = "deadbeef"
    save_prd(prd_path, data)

    data["sdlc_review_status"] = "pending"
    save_prd(prd_path, data)

    assert load_prd(prd_path)["sdlc_review_status"] == "pending"


def test_save_prd_still_forbids_complete_to_pending_without_baseline(tmp_path):
    # Without a recorded baseline there is no legitimate new round — the original
    # anti-revert guard still fires (protects against an accidental blank reset).
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    save_prd(prd_path, data)

    data["sdlc_review_status"] = "pending"
    with pytest.raises(SystemExit):
        save_prd(prd_path, data)


# A stand-in for the integration branch's current HEAD, returned by the fake `git rev-parse
# HEAD`. Tests assert the gate persists this as last_reviewed_sha when it completes a round.
FAKE_HEAD_SHA = "headsha0000000000000000000000000000000a"
# A prior-round baseline that is reachable but distinct from HEAD (a non-empty increment).
FAKE_BASELINE_SHA = "baseline00000000000000000000000000000000"


def _fake_subprocess_run(cmd, **kwargs):
    if cmd[:2] == ["gh", "auth"]:
        return type("R", (), {"returncode": 0})()
    if cmd[:3] == ["gh", "issue", "view"]:
        # Filed issues carry a state label — nothing for the gate to flag.
        return type("R", (), {"returncode": 0, "stdout": "bug\nready-for-agent\n"})()
    if cmd[:3] == ["gh", "pr", "list"]:
        # No open PR — update_pr_description (run by the docs phase) skips cleanly.
        return type("R", (), {"returncode": 0, "stdout": "[]"})()
    if cmd[:3] == ["git", "rev-parse", "HEAD"]:
        return type("R", (), {"returncode": 0, "stdout": FAKE_HEAD_SHA + "\n"})()
    if cmd[:3] == ["git", "rev-parse", "--verify"]:
        # Baseline reachability: HEAD and the known prior baseline resolve; anything else 404s.
        reachable = FAKE_HEAD_SHA in cmd[-1] or FAKE_BASELINE_SHA in cmd[-1]
        return type("R", (), {"returncode": 0 if reachable else 1, "stdout": ""})()
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
            return ("ISSUE: #11\nISSUE: #12\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"
    assert len(calls) == 4
    assert "#11" in calls[2] and "#12" in calls[2]


def test_gate_persists_head_as_baseline_and_clears_bookkeeping_on_completion(tmp_path):
    # Completing a round records the reviewed HEAD as the baseline and clears the per-round
    # bookkeeping so the next incremental round starts clean.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_completed_agents"] = list(run_next_plan.SDLC_REVIEW_AGENTS)
    save_prd(prd_path, data)

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    loaded = load_prd(prd_path)
    assert loaded["last_reviewed_sha"] == FAKE_HEAD_SHA
    assert loaded["sdlc_review_completed_agents"] == []
    assert loaded["sdlc_round_filed_issues"] == []  # per-round scratch cleared
    assert loaded["sdlc_finding_issues"] == [11]  # cumulative record retains the round's issue


def test_gate_first_run_reviews_whole_pr_against_default_branch(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())  # no baseline

    prompts = []

    def fake_invoke_claude(prompt, repo_root):
        prompts.append(prompt)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    review_prompt = next(p for p in prompts if "Dispatch these review agents" in p)
    assert "main...HEAD" in review_prompt


def test_gate_incremental_run_reviews_only_commits_since_baseline(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA  # reachable, != HEAD
    save_prd(prd_path, data)

    prompts = []

    def fake_invoke_claude(prompt, repo_root):
        prompts.append(prompt)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    review_prompt = next(p for p in prompts if "Dispatch these review agents" in p)
    assert f"{FAKE_BASELINE_SHA}..HEAD" in review_prompt
    assert "main...HEAD" not in review_prompt


def test_gate_empty_increment_marks_complete_without_reviewing(tmp_path):
    # Baseline == HEAD: nothing new since the last review. The gate must no-op gracefully —
    # mark complete, run no reviewer/issue/triage calls, not error.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["last_reviewed_sha"] = FAKE_HEAD_SHA  # == current HEAD
    save_prd(prd_path, data)

    calls = []

    def fake_invoke_claude(prompt, repo_root):
        calls.append(prompt)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "complete"
    assert calls == []  # never invoked reviewers, issue-filing, or triage
    assert get_sdlc_review_status(load_prd(prd_path)) == "complete"


def test_rearm_sdlc_review_gate_flips_complete_to_pending_and_clears_bookkeeping(tmp_path):
    # New work appended after a completed review: re-arm the gate to run again. Flips the
    # latched 'complete' back to 'pending' (allowed because a baseline is present) and clears
    # any stale round bookkeeping. The baseline is preserved as the increment boundary.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    data["sdlc_review_completed_agents"] = ["sdlc-code-reviewer"]
    data["sdlc_finding_issues"] = [11, 12]
    data["sdlc_round_filed_issues"] = [11, 12]
    save_prd(prd_path, data)

    run_next_plan._rearm_sdlc_review_gate(prd_path)

    loaded = load_prd(prd_path)
    assert loaded["sdlc_review_status"] == "pending"
    assert loaded["last_reviewed_sha"] == FAKE_BASELINE_SHA
    assert loaded["sdlc_review_completed_agents"] == []
    assert loaded["sdlc_round_filed_issues"] == []  # per-round scratch cleared
    assert loaded["sdlc_finding_issues"] == [11, 12]  # cumulative record preserved


def test_gate_accumulates_finding_issues_across_rounds(tmp_path):
    # A re-armed round's newly filed issues are appended to the iteration-cumulative
    # sdlc_finding_issues (not overwritten), so /close-iteration sees the whole set (#47).
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_finding_issues"] = [99]  # a prior round's finding
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA  # reachable, != HEAD → a real increment
    save_prd(prd_path, data)

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    loaded = load_prd(prd_path)
    assert loaded["sdlc_finding_issues"] == [99, 11]  # cumulative, not overwritten
    assert loaded["sdlc_round_filed_issues"] == []  # per-round scratch cleared at round end


def test_gate_dedupes_finding_issues_when_a_number_recurs(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_finding_issues"] = [11]
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    save_prd(prd_path, data)

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)  # same number recurs
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert load_prd(prd_path)["sdlc_finding_issues"] == [11]  # deduped, no duplicate


def test_gate_reround_files_its_own_issues_despite_prior_cumulative(tmp_path):
    # The per-round "already filed" guard lives on sdlc_round_filed_issues, NOT the cumulative
    # list — a re-armed round with prior findings present still files its own issues once (#48).
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_finding_issues"] = [99]  # prior round already recorded
    data["sdlc_round_filed_issues"] = []  # this round has not filed yet
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    save_prd(prd_path, data)

    state = {"file_calls": 0}

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            state["file_calls"] += 1
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert state["file_calls"] == 1  # filed exactly once for the new round
    assert load_prd(prd_path)["sdlc_finding_issues"] == [99, 11]


def test_gate_round_scratch_guard_prevents_refiling_within_a_round(tmp_path):
    # If this round already filed (scratch field set) but triage was interrupted, resuming
    # must re-run triage only — never re-file the round's issues.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_finding_issues"] = [11]
    data["sdlc_round_filed_issues"] = [11]  # this round already filed
    data["sdlc_review_completed_agents"] = list(run_next_plan.SDLC_REVIEW_AGENTS)
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    save_prd(prd_path, data)

    state = {"file_calls": 0, "triage_issues": None}

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            state["file_calls"] += 1
            return ("ISSUE: #99\n", 0)
        if "labeled at filing" in prompt:
            state["triage_issues"] = prompt
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert state["file_calls"] == 0  # never re-filed
    assert "#11" in state["triage_issues"]  # triaged the already-filed round issue


def test_gate_rotates_stale_findings_file_at_fresh_round_start(tmp_path):
    # A fresh round (no reviewers completed yet) removes any prior round's leftover findings
    # file so the file-issues phase can't re-file last round's findings as duplicates (#48).
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA  # a re-armed round with a real increment
    save_prd(prd_path, data)
    findings = tmp_path / "meta" / "sdlc-review-findings.md"
    findings.parent.mkdir(parents=True)
    findings.write_text("## Stale finding from a prior round\n")

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)  # faked reviewers do not rewrite the file

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert not findings.exists()  # stale file was rotated away, not appended to


def test_gate_preserves_findings_file_on_mid_round_resume(tmp_path):
    # Rotation is once-per-round, not per-attempt: resuming a round whose reviewers already
    # ran (completed set non-empty) must NOT wipe the findings they appended.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_completed_agents"] = list(run_next_plan.SDLC_REVIEW_AGENTS)
    save_prd(prd_path, data)
    findings = tmp_path / "meta" / "sdlc-review-findings.md"
    findings.parent.mkdir(parents=True)
    findings.write_text("## This round's finding\n")

    def fake_invoke_claude(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert findings.exists()
    assert "This round's finding" in findings.read_text()  # preserved, not rotated


def test_rotate_findings_file_refuses_symlink(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n")
    meta = tmp_path / "meta"
    meta.mkdir()
    link = meta / "sdlc-review-findings.md"
    link.symlink_to(outside)

    with pytest.raises(SystemExit):
        run_next_plan._rotate_findings_file(tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert outside.exists()  # symlink target left untouched


def test_run_sdlc_review_gate_waits_out_a_session_limit_then_completes(tmp_path):
    # Regression: a session limit must NOT make the gate bail — it waits for the reset
    # (like the main loop) and retries automatically.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    state = {"review_calls": 0}

    def fake_invoke_claude(prompt, repo_root):
        if "Dispatch these review agents" in prompt or "review agent on the diff" in prompt:
            state["review_calls"] += 1
            if state["review_calls"] == 1:
                return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero
            return ("ok", 0)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\nISSUE: #12\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "complete"
    assert get_sdlc_review_status(load_prd(prd_path)) == "complete"
    assert slept  # it waited for the reset before retrying


def test_run_sdlc_review_gate_ignores_quoted_limit_text_on_successful_review(tmp_path):
    # A reviewer inspecting run-next-plan.py itself will quote this file's limit strings.
    # That is a successful (exit-0) review, not a CLI limit announcement, so the gate must
    # complete normally — never wait, never bail. A genuine limit exits the CLI non-zero.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake_invoke_claude(prompt, repo_root):
        if "Dispatch these review agents" in prompt:
            return (f"Flagged: the limit gate quotes `{SAMPLE_LIMIT_MESSAGE}`.", 0)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "complete"
    assert not slept  # never mistook the quoted limit string for a real limit


def test_run_sdlc_review_gate_resumes_triage_after_waiting_out_a_limit(tmp_path):
    # The specific failure that motivated this: reviews + issue-filing succeed, then triage
    # hits the limit. The gate waits, then re-runs ONLY triage (reviews already complete,
    # issues already filed) — no duplicate issue filing.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    state = {"triage_calls": 0, "file_calls": 0}

    def fake_invoke_claude(prompt, repo_root):
        if "labeled at filing" in prompt:
            state["triage_calls"] += 1
            if state["triage_calls"] == 1:
                return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero
            return ("TRIAGE_DONE", 0)
        if "file a GitHub issue" in prompt:
            state["file_calls"] += 1
            return ("ISSUE: #11\nISSUE: #12\n", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "complete"
    data = load_prd(prd_path)
    assert state["file_calls"] == 1  # issues filed once, not re-filed on the retry
    # Per-round scratch is cleared once the round completes; the cumulative record retains
    # this round's filed issues (see test_gate_accumulates_finding_issues_across_rounds).
    assert data["sdlc_round_filed_issues"] == []
    assert data["sdlc_finding_issues"] == [11, 12]


def test_run_sdlc_review_gate_escalates_to_serial_after_two_parallel_limit_hits(tmp_path):
    # Two parallel attempts hit the limit; the gate then runs reviewers one at a time.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = []

    def fake_invoke_claude(prompt, repo_root):
        prompts.append(prompt)
        if "Dispatch these review agents" in prompt:  # parallel dispatch
            return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero
        if "review agent on the diff" in prompt:  # serial single-agent
            return ("ok", 0)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "complete"
    parallel_calls = [p for p in prompts if "Dispatch these review agents" in p]
    serial_calls = [p for p in prompts if "review agent on the diff" in p]
    assert len(parallel_calls) == run_next_plan.REVIEW_PARALLEL_ATTEMPTS  # two parallel tries
    assert len(serial_calls) == len(run_next_plan.SDLC_REVIEW_AGENTS)  # then each agent serially
    # Completed-agent bookkeeping drove the serial resume during the round, then is cleared
    # once the round completes so the next incremental round starts fresh.
    assert load_prd(prd_path)["sdlc_review_completed_agents"] == []


def test_run_sdlc_review_gate_gives_up_incomplete_after_max_attempts(tmp_path):
    # If the limit never resets, the gate bounds its waiting to MAX_REVIEW_ATTEMPTS and then
    # gives up as 'incomplete' — it must NOT wait forever and must NOT claim completion.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake_invoke_claude(prompt, repo_root):
        return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "incomplete"
    assert get_sdlc_review_status(load_prd(prd_path)) == "pending"
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
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert load_prd(prd_path).get("sdlc_review_status", "pending") == "pending"


def _fake_gate_claude(prompt, repo_root):
    if "file a GitHub issue" in prompt:
        return ("ISSUE: #11\n", 0)
    if "labeled at filing" in prompt:
        return ("TRIAGE_DONE", 0)
    return ("ok", 0)


def _run_gate(prd_path, tmp_path):
    with patch.object(run_next_plan, "invoke_claude", side_effect=_fake_gate_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        return run_next_plan.run_sdlc_review_gate(
            prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path)
        )


def test_gate_increments_review_rounds_on_a_completed_round(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    _run_gate(prd_path, tmp_path)

    assert load_prd(prd_path)["sdlc_review_rounds"] == 1


def test_gate_counts_rounds_cumulatively_across_rounds(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_rounds"] = 1
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    save_prd(prd_path, data)

    _run_gate(prd_path, tmp_path)

    assert load_prd(prd_path)["sdlc_review_rounds"] == 2


def test_gate_does_not_count_an_empty_increment_as_a_round(tmp_path):
    # Nothing was reviewed, so nothing should be charged against the cap.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["last_reviewed_sha"] = FAKE_HEAD_SHA  # baseline == HEAD → empty increment
    save_prd(prd_path, data)

    _run_gate(prd_path, tmp_path)

    loaded = load_prd(prd_path)
    assert loaded["sdlc_review_status"] == "complete"
    assert run_next_plan.get_sdlc_review_rounds(loaded) == 0


def _completed_round_prd(rounds):
    data = _valid_prd()
    data["sdlc_review_status"] = "complete"
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    data["sdlc_review_rounds"] = rounds
    data["sdlc_finding_issues"] = [11, 12]
    return data


def test_rearm_is_allowed_after_the_first_round(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _completed_round_prd(1))

    assert run_next_plan._rearm_sdlc_review_gate(prd_path) is True
    assert load_prd(prd_path)["sdlc_review_status"] == "pending"


def test_rearm_is_suppressed_once_the_round_cap_is_reached(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _completed_round_prd(2))

    assert run_next_plan._rearm_sdlc_review_gate(prd_path) is False
    # Status stays latched complete — and crucially the suppressed path must not trip
    # save_prd's complete→pending guard.
    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def test_rearm_suppression_logs_the_deferred_issue_numbers(tmp_path, capsys):
    prd_path = tmp_path / "prd.json"
    data = _completed_round_prd(2)
    data["sdlc_deferred_issues"] = [31, 32]
    save_prd(prd_path, data)

    run_next_plan._rearm_sdlc_review_gate(prd_path)

    out = capsys.readouterr().out
    assert "#31" in out and "#32" in out
    assert "policy" in out.lower()


def test_rearm_is_suppressed_when_the_cap_is_exceeded(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _completed_round_prd(5))

    assert run_next_plan._rearm_sdlc_review_gate(prd_path) is False


def test_rearm_cap_is_overridable_by_environment(tmp_path, monkeypatch):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _completed_round_prd(2))
    monkeypatch.setenv("RALPH_MAX_REVIEW_ROUNDS", "4")

    assert run_next_plan._rearm_sdlc_review_gate(prd_path) is True
    assert load_prd(prd_path)["sdlc_review_status"] == "pending"


def test_final_round_findings_are_kept_out_of_the_cumulative_closes_record(tmp_path):
    # Round 2 of 2: its findings are filed as issues but will never be fixed in this PR, so
    # they must not reach sdlc_finding_issues, which /close-iteration turns into `Closes #N`.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_rounds"] = 1  # the round about to run is the last one
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    data["sdlc_finding_issues"] = [99]
    save_prd(prd_path, data)

    _run_gate(prd_path, tmp_path)

    loaded = load_prd(prd_path)
    assert loaded["sdlc_finding_issues"] == [99]  # unchanged: #11 was deferred, not claimed
    assert loaded["sdlc_review_rounds"] == 2


def test_non_final_round_findings_still_reach_the_cumulative_record(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_finding_issues"] = [99]
    save_prd(prd_path, data)

    _run_gate(prd_path, tmp_path)

    assert load_prd(prd_path)["sdlc_finding_issues"] == [99, 11]


def test_final_round_still_records_its_filed_issues_for_the_refile_guard(tmp_path):
    # The per-round scratch must still be written mid-round, or a session-limit resume
    # would re-file the same findings as duplicates.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_rounds"] = 1
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    save_prd(prd_path, data)

    seen = []
    real = run_next_plan._with_prd_lock

    def spy(path, mutate):
        real(path, mutate)
        seen.append(load_prd(path).get("sdlc_round_filed_issues"))

    with patch.object(run_next_plan, "invoke_claude", side_effect=_fake_gate_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ), patch.object(run_next_plan, "_with_prd_lock", side_effect=spy):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert [11] in seen


def test_final_round_triage_is_told_not_to_write_plans(tmp_path):
    (tmp_path / "meta" / "plans").mkdir(parents=True)  # un-migrated layout
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_rounds"] = 1
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    save_prd(prd_path, data)

    prompts = []

    def recording(prompt, repo_root):
        prompts.append(prompt)
        return _fake_gate_claude(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=recording), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    triage_prompt = next(p for p in prompts if "labeled at filing" in p)
    assert "Do NOT write any plan files" in triage_prompt
    assert "Do NOT add any entries to meta/plans/prd.json" in triage_prompt


def test_gate_prompts_name_the_resolved_config_root(tmp_path):
    """A migrated repo's prompts must name docs/agents/, not the layout this script was
    written against — otherwise the loop tells Claude to write to a directory that does not
    exist in the repo in front of it."""
    (tmp_path / "docs" / "agents" / "plans").mkdir(parents=True)
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = []

    def recording(prompt, repo_root):
        prompts.append(prompt)
        return _fake_gate_claude(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=recording), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    review_prompt = next(p for p in prompts if "review agents in parallel" in p)
    assert "docs/agents/sdlc-review-findings.md" in review_prompt
    file_issues_prompt = next(p for p in prompts if "file a GitHub issue" in p)
    assert "docs/agents/sdlc-review-findings.md" in file_issues_prompt
    assert "redact any such value as [REDACTED]" in file_issues_prompt
    assert "credentials, tokens, keys, connection strings" in file_issues_prompt
    triage_prompt = next(p for p in prompts if "labeled at filing" in p)
    assert "docs/agents/plans/<slug>.md" in triage_prompt
    assert "docs/agents/plans/implementation-logs/" in triage_prompt
    assert "meta/plans" not in "\n".join(prompts)


def test_non_final_round_triage_still_clusters_issues_into_plans(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = []

    def recording(prompt, repo_root):
        prompts.append(prompt)
        return _fake_gate_claude(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=recording), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    triage_prompt = next(p for p in prompts if "labeled at filing" in p)
    assert "Do NOT write any plan files" not in triage_prompt
    assert "write one" in triage_prompt


def test_a_completed_gate_round_issues_exactly_one_push(tmp_path):
    # The gate used to push at its own end *and* again from the docs phase, so every round
    # fired at least two CI runs. Reviewers, issue filing, triage and docs now share one.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    pushes = []

    def ahead_of_upstream(cmd, **kwargs):
        if cmd[:2] == ["git", "rev-list"]:
            return type("R", (), {"returncode": 0, "stdout": "3\n"})()
        if cmd[:2] == ["git", "push"]:
            pushes.append(cmd)
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        return _fake_subprocess_run(cmd, **kwargs)

    with patch.object(run_next_plan, "invoke_claude", side_effect=_fake_gate_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=ahead_of_upstream
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert len(pushes) == 1


def _triage_appends(prd_path, new_entry):
    """A gate Claude fake whose triage session appends `new_entry` to prd.json raw, the way
    a real session edits the file — bypassing save_prd's schema check."""

    def fake(prompt, repo_root):
        if "labeled at filing" in prompt:
            raw = json.loads(prd_path.read_text())
            raw["plans"].append(new_entry)
            prd_path.write_text(json.dumps(raw))
        return _fake_gate_claude(prompt, repo_root)

    return fake


def test_gate_completes_when_triage_appends_a_plan_with_null_status(tmp_path):
    # #66: triage appended plans with "status": null; the next load_prd died mid-gate, the
    # round never latched complete, and every later run died at startup.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())
    new_entry = {"file": "new-plan.md", "issues": [11], "status": None, "attempts": 0, "blocked_by": []}

    with patch.object(
        run_next_plan, "invoke_claude", side_effect=_triage_appends(prd_path, new_entry)
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    loaded = load_prd(prd_path)
    assert loaded["sdlc_review_status"] == "complete"
    assert loaded["plans"][0]["status"] == "pending"


def test_non_final_triage_prompt_spells_out_a_pending_entry_shape(tmp_path):
    # The old wording ("any entry with a non-null status field is immutable") read as though
    # new entries carry a null status, which is exactly what triage then wrote (#66).
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = []

    def recording(prompt, repo_root):
        prompts.append(prompt)
        return _fake_gate_claude(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=recording), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    triage_prompt = next(p for p in prompts if "labeled at filing" in p)
    assert '"status": "pending"' in triage_prompt
    assert '"attempts": 0' in triage_prompt
    assert "non-null" not in triage_prompt


def test_gate_survives_triage_appending_a_null_status_plan_then_hitting_a_limit(tmp_path):
    # The interrupted path reloads prd.json too (to commit progress before waiting), so a
    # partial triage that wrote a null-status plan must not wedge it either.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())
    state = {"triage_calls": 0}

    def fake(prompt, repo_root):
        if "labeled at filing" in prompt:
            state["triage_calls"] += 1
            if state["triage_calls"] == 1:
                raw = json.loads(prd_path.read_text())
                raw["plans"].append({"file": "new-plan.md", "issues": [11], "status": None})
                prd_path.write_text(json.dumps(raw))
                return (SAMPLE_LIMIT_MESSAGE, 1)
        return _fake_gate_claude(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    assert result == "complete"
    plan = load_prd(prd_path)["plans"][0]
    assert (plan["status"], plan["attempts"], plan["blocked_by"]) == ("pending", 0, [])


def test_triage_nulling_an_existing_plans_status_still_fails_loudly(tmp_path):
    # Defaults apply only to plans triage appended; a pre-existing entry it corrupted is a
    # real immutability violation and must not be quietly repaired.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["plans"] = [{"file": "old-plan.md", "status": "done", "attempts": 1, "blocked_by": []}]
    save_prd(prd_path, data)

    def fake(prompt, repo_root):
        if "labeled at filing" in prompt:
            raw = json.loads(prd_path.read_text())
            raw["plans"][0]["status"] = None
            prd_path.write_text(json.dumps(raw))
        return _fake_gate_claude(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ), pytest.raises(SystemExit):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))


def _record_gate_prompts(prd_path, tmp_path, fake=_fake_gate_claude, run=_fake_subprocess_run):
    prompts = []

    def recording(prompt, repo_root):
        prompts.append(prompt)
        return fake(prompt, repo_root)

    with patch.object(run_next_plan, "invoke_claude", side_effect=recording), patch.object(
        run_next_plan.subprocess, "run", side_effect=run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))
    return prompts


def test_only_medium_and_above_findings_are_filed_as_their_own_issues(tmp_path):
    # One issue per finding at every severity filed 100 issues across two rounds of one
    # iteration, most of them nits. Minor/low findings share a single rollup issue instead.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = _record_gate_prompts(prd_path, tmp_path)

    file_issues_prompt = next(p for p in prompts if "file a GitHub issue" in p)
    assert "Blocker, Critical, High, Major or Medium" in file_issues_prompt
    assert "ONE rollup issue" in file_issues_prompt
    assert "MINOR_ROLLUP:" in file_issues_prompt


def test_minor_rollup_is_neither_triaged_nor_claimed_by_the_pr(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\nMINOR_ROLLUP: #12\n", 0)
        return _fake_gate_claude(prompt, repo_root)

    prompts = _record_gate_prompts(prd_path, tmp_path, fake)

    triage_prompt = next(p for p in prompts if "labeled at filing" in p)
    assert "#11" in triage_prompt
    assert "#12" not in triage_prompt
    assert load_prd(prd_path)["sdlc_finding_issues"] == [11]


def test_round_with_only_minor_findings_completes_without_triage(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("MINOR_ROLLUP: #12\n", 0)
        return _fake_gate_claude(prompt, repo_root)

    prompts = _record_gate_prompts(prd_path, tmp_path, fake)

    assert not any("labeled at filing" in p for p in prompts)
    loaded = load_prd(prd_path)
    assert loaded["sdlc_review_status"] == "complete"
    assert loaded["sdlc_review_rounds"] == 1


def test_filing_skips_findings_already_covered_by_an_open_issue(tmp_path):
    # A later round re-finding a still-open issue must not file it a second time.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = _record_gate_prompts(prd_path, tmp_path)

    file_issues_prompt = next(p for p in prompts if "file a GitHub issue" in p)
    assert "gh issue list --label sdlc-finding --state open" in file_issues_prompt
    assert "DUPLICATE:" in file_issues_prompt


def test_filing_drops_cosmetic_findings_instead_of_filing_them(tmp_path):
    # Nothing triages a filed issue afterwards, so the bar is applied before filing.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = _record_gate_prompts(prd_path, tmp_path)

    file_issues_prompt = next(p for p in prompts if "file a GitHub issue" in p)
    assert "cosmetic churn" in file_issues_prompt


def test_filing_labels_each_issue_with_a_category_and_a_state(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = _record_gate_prompts(prd_path, tmp_path)

    file_issues_prompt = next(p for p in prompts if "file a GitHub issue" in p)
    for label in ("bug", "enhancement", "ready-for-agent", "ready-for-human", "needs-info"):
        assert f"`{label}`" in file_issues_prompt


def test_no_gate_prompt_invokes_the_user_only_triage_skill(tmp_path):
    # /triage is user-invoked; a headless session asked to run it is refused.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    prompts = _record_gate_prompts(prd_path, tmp_path)

    assert not any("/triage" in p for p in prompts)


def test_filed_issue_without_a_state_label_is_flagged_for_the_user_to_triage(tmp_path, capsys):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\nISSUE: #12\n", 0)
        return _fake_gate_claude(prompt, repo_root)

    def run(cmd, **kwargs):
        if cmd[:3] == ["gh", "issue", "view"]:
            labels = "bug\n" if cmd[3] == "11" else "bug\nready-for-agent\n"
            return type("R", (), {"returncode": 0, "stdout": labels})()
        return _fake_subprocess_run(cmd, **kwargs)

    _record_gate_prompts(prd_path, tmp_path, fake, run)

    err = capsys.readouterr().err
    assert "/triage #11" in err
    assert "#12" not in err
    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def test_finding_on_an_issue_this_pr_claims_to_fix_is_not_deduped_away(tmp_path):
    # Issues the PR closes stay open until it merges. A later round finding that one of them
    # is still broken means the fix fell short; deduping it would drop the finding and let
    # the PR close the issue anyway.
    plans_dir = tmp_path / "docs" / "agents" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "p.md").write_text("# Plan\n\n**Issues:** #63\n")
    prd_path = plans_dir / "prd.json"
    data = _valid_prd()
    data["plans"] = [{"file": "p.md", "status": "done", "attempts": 1, "blocked_by": []}]
    data["sdlc_finding_issues"] = [112]
    save_prd(prd_path, data)

    prompts = _record_gate_prompts(prd_path, tmp_path)

    file_issues_prompt = next(p for p in prompts if "file a GitHub issue" in p)
    assert "[63, 112]" in file_issues_prompt
    assert "is NOT a duplicate" in file_issues_prompt


# --- #78: deferred and rollup issues are recorded in sdlc_deferred_issues -------------------


def _final_round_prd():
    data = _valid_prd()
    data["sdlc_review_rounds"] = 1  # the round about to run is the last one
    data["last_reviewed_sha"] = FAKE_BASELINE_SHA
    data["sdlc_finding_issues"] = [99]
    return data


def _run_gate_with_filing_output(prd_path, tmp_path, filing_output):
    def fake(prompt, repo_root):
        if "file a GitHub issue" in prompt:
            return (filing_output, 0)
        return _fake_gate_claude(prompt, repo_root)

    return _record_gate_prompts(prd_path, tmp_path, fake)


def test_final_round_issues_are_recorded_as_deferred_not_finding_issues(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _final_round_prd())

    _run_gate(prd_path, tmp_path)

    loaded = load_prd(prd_path)
    assert loaded["sdlc_deferred_issues"] == [11]
    assert loaded["sdlc_finding_issues"] == [99]


def test_non_final_round_issues_are_not_deferred(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    _run_gate(prd_path, tmp_path)

    assert load_prd(prd_path).get("sdlc_deferred_issues", []) == []


def test_minor_rollup_is_recorded_as_deferred_on_a_non_final_round(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    _run_gate_with_filing_output(prd_path, tmp_path, "ISSUE: #11\nMINOR_ROLLUP: #12\n")

    loaded = load_prd(prd_path)
    assert loaded["sdlc_deferred_issues"] == [12]
    assert loaded["sdlc_finding_issues"] == [11]


def test_minor_rollup_is_recorded_alongside_final_round_issues(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _final_round_prd())

    _run_gate_with_filing_output(prd_path, tmp_path, "ISSUE: #11\nMINOR_ROLLUP: #12\n")

    assert load_prd(prd_path)["sdlc_deferred_issues"] == [11, 12]


def test_missing_rollup_line_is_fine(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    _run_gate_with_filing_output(prd_path, tmp_path, "ISSUE: #11\n")

    assert load_prd(prd_path)["sdlc_review_status"] == "complete"


def test_deferred_issues_are_deduped_across_rounds(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _final_round_prd()
    data["sdlc_deferred_issues"] = [12]
    save_prd(prd_path, data)

    _run_gate_with_filing_output(prd_path, tmp_path, "ISSUE: #11\nMINOR_ROLLUP: #12\n")

    assert load_prd(prd_path)["sdlc_deferred_issues"] == [12, 11]


def test_gate_completion_keeps_deferred_issues(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _final_round_prd())

    _run_gate(prd_path, tmp_path)

    loaded = load_prd(prd_path)
    assert loaded["sdlc_round_filed_issues"] == []
    assert loaded["sdlc_deferred_issues"] == [11]


def test_parse_minor_rollup_takes_the_last_match():
    assert run_next_plan.parse_minor_rollup("MINOR_ROLLUP: #5\nMINOR_ROLLUP: 7\n") == 7


def test_parse_minor_rollup_rejects_zero_and_trailing_junk_and_absence():
    assert run_next_plan.parse_minor_rollup("MINOR_ROLLUP: #0") is None
    assert run_next_plan.parse_minor_rollup("MINOR_ROLLUP: #5 extra") is None
    assert run_next_plan.parse_minor_rollup("ISSUE: #5") is None


def test_rollup_number_never_reaches_issue_parsing():
    assert run_next_plan.parse_issue_numbers("ISSUE: #11\nMINOR_ROLLUP: #12\n") == ["#11"]


def test_rearm_keeps_deferred_issues(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _completed_round_prd(1)
    data["sdlc_deferred_issues"] = [41]
    save_prd(prd_path, data)

    assert run_next_plan._rearm_sdlc_review_gate(prd_path) is True
    assert load_prd(prd_path)["sdlc_deferred_issues"] == [41]


def test_cap_message_lists_deferred_issues_not_finding_issues(tmp_path, capsys):
    prd_path = tmp_path / "prd.json"
    data = _completed_round_prd(2)  # sdlc_finding_issues == [11, 12]
    data["sdlc_deferred_issues"] = [41, 42]
    save_prd(prd_path, data)

    run_next_plan._rearm_sdlc_review_gate(prd_path)

    out = capsys.readouterr().out
    assert "#41" in out and "#42" in out
    assert "#11" not in out and "#12" not in out


def test_cap_message_says_none_when_nothing_was_deferred(tmp_path, capsys):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _completed_round_prd(2))

    run_next_plan._rearm_sdlc_review_gate(prd_path)

    assert "deferred to a human: none" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["seven", [True], ["7"]])
def test_load_prd_rejects_malformed_deferred_issues(tmp_path, bad):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_deferred_issues"] = bad
    save_prd(prd_path, data)

    with pytest.raises(SystemExit):
        load_prd(prd_path)


def test_load_prd_accepts_deferred_issues(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_deferred_issues"] = [3, 4]
    save_prd(prd_path, data)

    assert load_prd(prd_path)["sdlc_deferred_issues"] == [3, 4]


# --- commit reference wiring ----------------------------------------------------------------


def _run_gate_recording_commits(tmp_path, *, interrupt_first_review, prd_extra=None):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data.update(prd_extra or {})
    save_prd(prd_path, data)

    commits = []  # (context, refs)
    prompts = []
    state = {"limited": not interrupt_first_review}

    def fake_invoke_claude(prompt, repo_root):
        prompts.append(prompt)
        if "Dispatch these review agents" in prompt and not state["limited"]:
            state["limited"] = True
            return (SAMPLE_LIMIT_MESSAGE, 1)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\n", 0)
        if "labeled at filing" in prompt:
            return ("TRIAGE_DONE", 0)
        return ("ok", 0)

    def fake_ensure_committed(repo_root, config_root, branch, context, refs=""):
        commits.append((context, refs))

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan, "ensure_committed", side_effect=fake_ensure_committed
    ), patch.object(run_next_plan.time, "sleep"), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))
    return dict(commits), commits, prompts


def test_gate_passes_pr_ref_to_interrupt_triage_and_docs_commits(tmp_path):
    by_context, commits, prompts = _run_gate_recording_commits(
        tmp_path, interrupt_first_review=True, prd_extra={"pr_number": 4242}
    )

    for context in ("SDLC review (interrupted)", "SDLC review triage", "docs phase", "SDLC review docs phase"):
        assert by_context[context] == "Refs #4242", context
    assert any("Refs #4242" in p and "documentation" in p.lower() for p in prompts)


def test_gate_commits_carry_empty_refs_when_no_pr_resolves(tmp_path):
    # gh finds no PR for the branch (empty stdout) and prd.json has no pr_number.
    by_context, _, _ = _run_gate_recording_commits(tmp_path, interrupt_first_review=False)

    assert by_context["SDLC review triage"] == ""
    assert by_context["SDLC review docs phase"] == ""
