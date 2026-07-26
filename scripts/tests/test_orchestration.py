import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

select_next_plan = run_next_plan.select_next_plan
scan_output = run_next_plan.scan_output
account_attempt = run_next_plan.account_attempt

# A representative sample of the CLI's real session-limit output. The specific clock time is
# arbitrary and load-bearing to nothing — detection keys on the non-zero exit code, not the
# time — so it lives here once, clearly labelled, rather than as a stray literal in tests.
SAMPLE_LIMIT_MESSAGE = "You've hit your session limit · resets 3:20am (America/New_York)"
_working_tree_dirty = run_next_plan._working_tree_dirty
_push_branch = run_next_plan._push_branch
ensure_committed_and_pushed = run_next_plan.ensure_committed_and_pushed
_ensure_logs_gitignored = run_next_plan._ensure_logs_gitignored
_LOGS_REL = run_next_plan._LOGS_REL


def _init_repo(path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def _init_repo_with_remote(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    local = tmp_path / "local"
    local.mkdir()
    _init_repo(local)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=local, check=True)
    return local, remote


def _remote_log(remote, branch):
    r = subprocess.run(
        ["git", "log", branch, "--format=%s"], cwd=remote, capture_output=True, text=True
    )
    return r.stdout.splitlines()


def _plan(file, status="pending", blocked_by=None, attempts=0):
    return {
        "file": file,
        "status": status,
        "attempts": attempts,
        "blocked_by": blocked_by or [],
    }


def test_select_next_plan_returns_none_when_all_done():
    plans = [_plan("a.md", status="done"), _plan("b.md", status="done")]
    assert select_next_plan(plans) is None


def test_select_next_plan_returns_none_when_all_stalled():
    plans = [_plan("a.md", status="stalled"), _plan("b.md", status="stalled")]
    assert select_next_plan(plans) is None


def test_select_next_plan_skips_done_and_stalled_entries():
    plans = [
        _plan("a.md", status="done"),
        _plan("b.md", status="stalled"),
        _plan("c.md", status="pending"),
    ]
    result = select_next_plan(plans)
    assert result["file"] == "c.md"


def test_select_next_plan_returns_none_on_circular_blocked_by():
    plans = [
        _plan("a.md", status="pending", blocked_by=["b.md"]),
        _plan("b.md", status="pending", blocked_by=["a.md"]),
    ]
    assert select_next_plan(plans) is None


def test_select_next_plan_returns_first_eligible_plan_with_no_blockers():
    plans = [
        _plan("a.md", status="pending"),
        _plan("b.md", status="pending"),
    ]
    result = select_next_plan(plans)
    assert result["file"] == "a.md"


def test_scan_output_detects_standalone_complete_sigil():
    text = "some output\n<promise>COMPLETE</promise>\nmore text\n"
    assert scan_output(text, 0) == "complete"


def test_scan_output_does_not_fire_on_embedded_mid_line_sigil():
    text = "blah blah <promise>COMPLETE</promise> trailing text\n"
    assert scan_output(text, 0) != "complete"


def test_scan_output_detects_rate_limit_pattern():
    text = "Error: usage limit reached, please try again later"
    assert scan_output(text, 1) == "rate_limit"


def test_scan_output_ignores_review_prose_mentioning_rate_limits():
    # Real false positive observed in the SDLC gate: a reviewer flagged code as
    # "not rate-limit-aware" — substantive review output, not a CLI limit message.
    text = (
        "| Minor | `_generate_pr_summary` invocation not rate-limit-aware | code |\n"
        "The function quotes usage limit / 429 / too many requests handling.\n"
        "<promise>COMPLETE</promise>\n"
    )
    assert scan_output(text, 0) == "complete"


def test_scan_output_ignores_incidental_limit_words_without_announcement():
    text = "This code path handles the usage limit and 429 too-many-requests branches."
    assert scan_output(text, 0) == "ok"


def test_scan_output_detects_reset_time_announcement():
    text = "Claude usage limit reached ∙ resets 4:00pm"
    assert scan_output(text, 1) == "rate_limit"


def test_scan_output_detects_real_session_limit_message():
    # Exact wording the Claude CLI emits on a session limit (paired with a non-zero exit).
    assert scan_output(SAMPLE_LIMIT_MESSAGE, 1) == "rate_limit"


def test_parse_retry_after_reads_on_the_hour_reset_time():
    # "resets 9pm" (no minutes) must yield a real wait, not the 60s fallback,
    # otherwise the gate re-loops tightly until the limit clears.
    secs = run_next_plan._parse_retry_after_text(
        "You've hit your session limit · resets 9pm (America/New_York)"
    )
    assert secs > run_next_plan.RETRY_WAIT_DEFAULT


def test_scan_output_ignores_quoted_limit_message_on_successful_exit():
    # Real false positive (2026-07-14): a successful run whose answer *quoted* the CLI
    # session-limit string was misread as a real limit and triggered a 22-hour wait.
    # A genuine limit terminates the CLI non-zero; a clean exit-0 completion never has.
    text = (
        "Done — one plan complete, committed and pushed.\n"
        f"Worth knowing: the 16:36 log says `{SAMPLE_LIMIT_MESSAGE}`, so that attempts "
        "counter is a red herring.\n"
    )
    assert scan_output(text, 0) == "ok"


def test_scan_output_returns_error_on_nonzero_exit_without_rate_limit_text():
    text = "Some unrelated failure occurred"
    assert scan_output(text, 1) == "error"


def test_scan_output_returns_ok_on_zero_exit_with_no_sigil():
    text = "Did some work, nothing special happened"
    assert scan_output(text, 0) == "ok"


def _write_prd(tmp_path, plans):
    prd_path = tmp_path / "prd.json"
    prd_path.write_text(json.dumps({"integration_branch": "integration/x", "plans": plans}))
    return prd_path


def _attempts(prd_path, file):
    data = json.loads(prd_path.read_text())
    return next(p["attempts"] for p in data["plans"] if p["file"] == file)


def _status(prd_path, file):
    data = json.loads(prd_path.read_text())
    return next(p["status"] for p in data["plans"] if p["file"] == file)


def test_account_attempt_does_not_charge_on_rate_limit(tmp_path):
    # #46: a session/usage-limit death does zero work — it must not burn an attempt.
    plans = [_plan("a.md", status="in-progress", attempts=2)]
    prd_path = _write_prd(tmp_path, plans)
    pre = {"a.md": "in-progress"}

    charged, stalled = account_attempt(prd_path, "rate_limit", pre, "some output", plans)

    assert charged is None
    assert stalled is False
    assert _attempts(prd_path, "a.md") == 2


def test_account_attempt_charges_plan_that_flipped_to_done(tmp_path):
    # #45: the runner's eligible[0] guess ("a.md") may differ from the plan Claude actually
    # advanced ("b.md"). The attempt is charged to whichever plan flipped to done this run.
    plans = [_plan("a.md", attempts=1), _plan("b.md", attempts=0)]
    prd_path = _write_prd(tmp_path, [_plan("a.md", attempts=1), _plan("b.md", status="done", attempts=0)])
    pre = {"a.md": "pending", "b.md": "pending"}

    charged, stalled = account_attempt(prd_path, "ok", pre, "no sigil here", plans)

    assert charged == "b.md"
    assert _attempts(prd_path, "b.md") == 1
    assert _attempts(prd_path, "a.md") == 1  # eligible[0] guess untouched


def test_account_attempt_falls_back_to_declared_plan_sigil(tmp_path):
    plans = [_plan("a.md", attempts=0), _plan("b.md", attempts=0)]
    prd_path = _write_prd(tmp_path, plans)
    pre = {"a.md": "pending", "b.md": "pending"}
    output = "starting work\n<plan>b.md</plan>\n…did stuff\n"

    charged, _ = account_attempt(prd_path, "ok", pre, output, plans)

    assert charged == "b.md"
    assert _attempts(prd_path, "b.md") == 1
    assert _attempts(prd_path, "a.md") == 0


def test_account_attempt_ignores_sigil_naming_ineligible_plan(tmp_path):
    # Untrusted sigil trust boundary: an injected/echoed plan name that isn't in the eligible
    # set must not charge (nor stall) an unrelated plan. Attribute nothing instead.
    plans = [_plan("a.md", attempts=0)]
    prd_path = _write_prd(tmp_path, plans)
    pre = {"a.md": "pending"}
    output = "<plan>../../etc/passwd.md</plan>\n<plan>other.md</plan>\n"

    charged, stalled = account_attempt(prd_path, "ok", pre, output, plans)

    assert charged is None
    assert stalled is False
    assert _attempts(prd_path, "a.md") == 0


def test_account_attempt_attributes_nothing_when_undeterminable(tmp_path):
    # No plan flipped to done and no sigil — never fall back to charging eligible[0].
    plans = [_plan("a.md", attempts=0), _plan("b.md", attempts=0)]
    prd_path = _write_prd(tmp_path, plans)
    pre = {"a.md": "pending", "b.md": "pending"}

    charged, stalled = account_attempt(prd_path, "ok", pre, "did some work, no signal", plans)

    assert charged is None
    assert stalled is False
    assert _attempts(prd_path, "a.md") == 0
    assert _attempts(prd_path, "b.md") == 0


def test_account_attempt_stalls_plan_only_after_exceeding_max_attempts(tmp_path):
    plans = [_plan("a.md", attempts=run_next_plan.MAX_ATTEMPTS)]
    prd_path = _write_prd(tmp_path, plans)
    pre = {"a.md": "in-progress"}
    output = "<plan>a.md</plan>\nworked on it\n"

    charged, stalled = account_attempt(prd_path, "ok", pre, output, plans)

    assert charged == "a.md"
    assert stalled is True
    assert _status(prd_path, "a.md") == "stalled"


def test_account_attempt_does_not_stall_unrun_plan(tmp_path):
    # A plan that no session demonstrably executed (no done-flip, no sigil) is never charged,
    # so it can never be pushed to stalled — even if its attempts already sit at the ceiling.
    plans = [_plan("a.md", attempts=run_next_plan.MAX_ATTEMPTS + 1)]
    prd_path = _write_prd(tmp_path, plans)
    pre = {"a.md": "pending"}

    charged, stalled = account_attempt(prd_path, "ok", pre, "unrelated output", plans)

    assert charged is None
    assert stalled is False
    assert _status(prd_path, "a.md") == "pending"


def test_working_tree_dirty_false_on_clean_repo(tmp_path):
    _init_repo(tmp_path)
    assert _working_tree_dirty(tmp_path) is False


def test_working_tree_dirty_true_with_uncommitted_change(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("changed\n")
    assert _working_tree_dirty(tmp_path) is True


def _write_run_log(repo_root, name="run-next-plan-2026_01_01_T00_00_00.log"):
    logs_dir = repo_root / "meta" / "plans" / "implementation-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / name).write_text("a log line\n")


def _is_ignored(repo_root, rel_path):
    return subprocess.run(
        ["git", "check-ignore", "-q", rel_path], cwd=repo_root
    ).returncode == 0


def test_ensure_logs_gitignored_adds_the_entry_when_absent(tmp_path):
    _init_repo(tmp_path)
    _ensure_logs_gitignored(tmp_path)
    assert _is_ignored(tmp_path, "meta/plans/implementation-logs/some.log")


def test_ensure_logs_gitignored_appends_below_existing_rules_without_clobbering_them(tmp_path):
    _init_repo(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\ndist/\n")

    _ensure_logs_gitignored(tmp_path)

    text = gitignore.read_text()
    assert text.startswith("node_modules/\ndist/\n")
    assert text.endswith(f"{_LOGS_REL}\n")
    assert _is_ignored(tmp_path, f"{_LOGS_REL}some.log")
    assert not _is_ignored(tmp_path, "src/app.py")


def test_ensure_logs_gitignored_leaves_an_already_ignoring_gitignore_untouched(tmp_path):
    _init_repo(tmp_path)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\n")
    _ensure_logs_gitignored(tmp_path)
    assert gitignore.read_text() == "*.log\n"


def test_ensure_logs_gitignored_untracks_logs_the_repo_already_committed(tmp_path):
    _init_repo(tmp_path)
    _write_run_log(tmp_path, "old-run.log")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "tracked log"], cwd=tmp_path, check=True)

    _ensure_logs_gitignored(tmp_path)

    tracked = subprocess.run(
        ["git", "ls-files", _LOGS_REL], capture_output=True, text=True, cwd=tmp_path, check=True
    ).stdout
    assert tracked == ""
    # The log itself must survive on disk — the runner is writing to it right now.
    assert (tmp_path / _LOGS_REL / "old-run.log").exists()


def test_working_tree_dirty_ignores_the_scripts_own_run_log(tmp_path):
    # The runner writes its live log inside the repo, so a log-only diff is not real work.
    _init_repo(tmp_path)
    _write_run_log(tmp_path)
    assert _working_tree_dirty(tmp_path) is False


def test_working_tree_dirty_true_when_real_work_accompanies_the_run_log(tmp_path):
    _init_repo(tmp_path)
    _write_run_log(tmp_path)
    (tmp_path / "README.md").write_text("changed\n")
    assert _working_tree_dirty(tmp_path) is True


def test_push_branch_sets_upstream_and_pushes_when_none_exists(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    _push_branch(local, "main")
    assert _remote_log(remote, "main") == ["init"]


def test_push_branch_pushes_new_commits_when_ahead_of_upstream(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    _push_branch(local, "main")
    (local / "file2.txt").write_text("more\n")
    subprocess.run(["git", "add", "."], cwd=local, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=local, check=True)
    _push_branch(local, "main")
    assert _remote_log(remote, "main") == ["second", "init"]


def test_push_branch_is_noop_when_not_ahead_of_upstream(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    _push_branch(local, "main")
    # Nothing new to push; calling again must not error and must leave remote unchanged.
    _push_branch(local, "main")
    assert _remote_log(remote, "main") == ["init"]


def test_ensure_committed_and_pushed_pushes_without_invoking_claude_when_clean(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    with patch.object(run_next_plan, "invoke_claude") as fake_invoke:
        ensure_committed_and_pushed(local, "main", "plan a.md")
    fake_invoke.assert_not_called()
    assert _remote_log(remote, "main") == ["init"]


def test_ensure_committed_and_pushed_asks_claude_to_commit_dirty_changes(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    (local / "README.md").write_text("changed by plan\n")

    def fake_commit(prompt, repo_root):
        subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "claude commit"], cwd=repo_root, check=True)
        return "ok"

    with patch.object(run_next_plan, "invoke_claude", side_effect=fake_commit) as fake_invoke:
        ensure_committed_and_pushed(local, "main", "plan a.md")

    fake_invoke.assert_called_once()
    assert _remote_log(remote, "main") == ["claude commit", "init"]


def test_ensure_committed_and_pushed_keeps_the_run_log_out_of_the_safety_net_commit(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    (local / "README.md").write_text("changed by plan\n")
    _write_run_log(local)

    with patch.object(run_next_plan, "invoke_claude", return_value="ok"):
        ensure_committed_and_pushed(local, "main", "plan a.md")

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, cwd=local, check=True,
    ).stdout.split()
    assert committed == ["README.md"]


def test_ensure_committed_and_pushed_does_not_ask_claude_to_commit_only_the_run_log(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    _write_run_log(local)

    with patch.object(run_next_plan, "invoke_claude") as fake_invoke:
        ensure_committed_and_pushed(local, "main", "plan a.md")

    fake_invoke.assert_not_called()
    assert _remote_log(remote, "main") == ["init"]


def test_ensure_committed_and_pushed_auto_commits_when_still_dirty_after_claude(tmp_path):
    local, remote = _init_repo_with_remote(tmp_path)
    (local / "README.md").write_text("changed by plan\n")

    with patch.object(run_next_plan, "invoke_claude", return_value="ok") as fake_invoke:
        ensure_committed_and_pushed(local, "main", "plan a.md")

    fake_invoke.assert_called_once()
    assert _working_tree_dirty(local) is False
    log = _remote_log(remote, "main")
    assert log[0].startswith("wip: uncommitted changes from plan a.md")
    assert log[1] == "init"
