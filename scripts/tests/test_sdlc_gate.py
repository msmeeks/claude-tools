import importlib.util
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


def test_save_prd_still_forbids_needs_human_to_pending_even_with_baseline(tmp_path):
    # 'needs-human' is a hard human-in-the-loop stop; only a human hand-editing the file
    # (bypassing save_prd) may resume it. The automated latch never re-arms it.
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["sdlc_review_status"] = "needs-human"
    data["last_reviewed_sha"] = "deadbeef"
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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            state["triage_issues"] = prompt
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)  # faked reviewers do not rewrite the file

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run
    ):
        run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

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
        run_next_plan._rotate_findings_file(tmp_path)

    assert outside.exists()  # symlink target left untouched


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
                return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero
            return ("ok", 0)
        if "file a GitHub issue" in prompt:
            return ("ISSUE: #11\nISSUE: #12\n", 0)
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    assert get_sdlc_review_status(load_prd(prd_path)) != "needs-human"
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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    slept = []
    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep", side_effect=slept.append
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    assert not slept  # never mistook the quoted limit string for a real limit


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
                return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        if "file a GitHub issue" in prompt:
            state["file_calls"] += 1
            return ("ISSUE: #11\nISSUE: #12\n", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    data = load_prd(prd_path)
    assert get_sdlc_review_status(data) != "needs-human"
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
        if "run /triage" in prompt:
            return ("HUMAN_IN_LOOP_REQUIRED: false\nTRIAGE_DONE", 0)
        return ("ok", 0)

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_invoke_claude), patch.object(
        run_next_plan.time, "sleep"
    ), patch.object(run_next_plan.subprocess, "run", side_effect=_fake_subprocess_run):
        result = run_next_plan.run_sdlc_review_gate(prd_path, tmp_path)

    assert result == "complete"
    parallel_calls = [p for p in prompts if "Dispatch these review agents" in p]
    serial_calls = [p for p in prompts if "review agent on the diff" in p]
    assert len(parallel_calls) == run_next_plan.REVIEW_PARALLEL_ATTEMPTS  # two parallel tries
    assert len(serial_calls) == len(run_next_plan.SDLC_REVIEW_AGENTS)  # then each agent serially
    # Completed-agent bookkeeping drove the serial resume during the round, then is cleared
    # once the round completes so the next incremental round starts fresh.
    assert load_prd(prd_path)["sdlc_review_completed_agents"] == []


def test_run_sdlc_review_gate_gives_up_incomplete_after_max_attempts_not_needs_human(tmp_path):
    # If the limit never resets, the gate bounds its waiting to MAX_REVIEW_ATTEMPTS and then
    # gives up as 'incomplete' — it must NOT wait forever and must NOT claim needs-human.
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    def fake_invoke_claude(prompt, repo_root):
        return (SAMPLE_LIMIT_MESSAGE, 1)  # real limit → CLI exits non-zero

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
