"""Whole-iteration runs of run-next-plan.py as a real subprocess against a real git repo and
bare origin, with fake `gh` and `claude` (see conftest.py). Unlike test_config_root.py, which
calls main() in-process with subprocess stubbed, nothing in the runner is patched here.

Asserts on die()/warn() read stderr; info() lines are on stdout."""

import json
import re
import shutil
import subprocess
from pathlib import Path

from .conftest import BRANCH, _plan

SEED_PR = {
    "number": 7, "state": "OPEN", "headRefName": BRANCH, "isCrossRepository": False,
    "body": "Synthetic PR body\n",
}


def _commit_bodies(it):
    raw = it.git("log", f"{it.seed_sha}..HEAD", "--format=%H%x1f%s%x1f%b%x1e")
    return [rec.strip("\n").split("\x1f") for rec in raw.split("\x1e") if rec.strip()]


def test_e2e_two_plan_run_completes(make_iteration):
    it = make_iteration(pr_number=7)
    it.set_state(prs=[SEED_PR])

    result = it.run()

    assert result.returncode == 0, result.stderr
    commits = _commit_bodies(it)
    assert commits
    for _sha, subject, body in commits:
        assert re.search(r"^Refs #\d+(, Refs #\d+)*$", body, re.M), subject
        assert "at runner exit" not in subject
    assert it.git("status", "--porcelain") == ""
    assert it.git("rev-parse", "HEAD") == it.remote_git("rev-parse", BRANCH)
    # Each plan's attempt bookkeeping is committed on its own, not left for a later sweep (#94).
    subjects = [subject for _sha, subject, _body in commits]
    for plan in ("alpha.md", "beta.md"):
        assert f"chore: record attempt for plan {plan}" in subjects
    # The gate ran end to end: docs committed, summary spliced into the PR, Closes synced.
    assert "docs/feature.md" in it.git("ls-files")
    body = it.state()["prs"][0]["body"]
    assert "For the Engineer" in body
    assert all(f"Closes #{n}" in body for n in (11, 12, 13))


def test_e2e_commit_refs_honour_custom_template(make_iteration):
    it = make_iteration(pr_number=7, gate_complete=True)
    it.set_state(prs=[SEED_PR])
    tracker = it.repo / "docs" / "agents" / "issue-tracker.md"
    tracker.write_text("# Tracker\n\n## Commit references\n\nTracks: GH-{n}\n")
    it.git("add", "-A")
    it.git("commit", "-q", "-m", "chore: tracker config")
    it.seed_sha = it.git("rev-parse", "HEAD").strip()

    result = it.run()

    assert result.returncode == 0, result.stderr
    commits = _commit_bodies(it)
    assert commits
    for _sha, subject, body in commits:
        assert re.search(r"^Tracks: GH-\d+(, Tracks: GH-\d+)*$", body, re.M), subject
    assert "Refs #" not in it.git("log", "--format=%B")


def _pr(state):
    return {**SEED_PR, "state": state}


def test_e2e_iteration_guard_merged_pr_by_number(make_iteration):
    it = make_iteration(pr_number=7)
    it.set_state(prs=[_pr("MERGED")])
    _assert_guard_stops(it, "finished iteration")


def test_e2e_iteration_guard_merged_pr_found_by_branch(make_iteration):
    it = make_iteration()
    it.set_state(prs=[_pr("MERGED")])
    _assert_guard_stops(it, "finished iteration")


def test_e2e_iteration_guard_branch_deleted_on_origin(make_iteration):
    it = make_iteration()
    it.git("push", "-q", "-u", "origin", BRANCH)
    it.remote_git("branch", "-q", "-D", BRANCH)
    it.git("fetch", "-q", "--prune", "origin")
    _assert_guard_stops(it, "finished iteration")


def test_e2e_iteration_guard_closed_pr_says_reopen_or_archive(make_iteration):
    it = make_iteration(pr_number=7)
    it.set_state(prs=[_pr("CLOSED")])
    result = _assert_guard_stops(it, "unresolved iteration")
    assert "reopen" in result.stderr
    assert "/plan-iteration" in result.stderr


def _assert_guard_stops(it, message):
    head = it.git("rev-parse", "HEAD")
    remote_branches = it.remote_git("branch", "--list")

    result = it.run()

    assert result.returncode != 0
    assert message in result.stderr
    assert it.git("rev-parse", "HEAD") == head
    assert it.remote_git("branch", "--list") == remote_branches
    return result


def test_e2e_dry_run_with_all_plans_done_makes_no_pr_edit(make_iteration):
    it = make_iteration(
        plans=[_plan("alpha.md", [11], status="done")], pr_number=7, gate_complete=True
    )
    it.set_state(prs=[SEED_PR])

    result = it.run("--dry-run")

    assert result.returncode == 0, result.stderr
    assert not [c for c in it.gh_calls() if c[:2] == ["pr", "edit"]]


def test_e2e_pr_edit_failure_warns_and_exits_zero(make_iteration):
    it = make_iteration(pr_number=7)
    it.set_state(prs=[SEED_PR], fail={"pr edit": True})

    result = it.run()

    assert result.returncode == 0, result.stderr
    assert "gh pr edit" in result.stderr
    assert "Traceback" not in result.stdout + result.stderr


def test_e2e_net_empty_review_round_commits_its_bookkeeping_with_refs(make_iteration):
    it = make_iteration(plans=[_plan("alpha.md", [11], status="done")], pr_number=7)
    it.set_state(prs=[SEED_PR])
    (it.repo / "scratch.txt").write_text("temporary\n")
    it.git("add", "scratch.txt")
    it.git("commit", "-q", "-m", "feat: temporary")
    it.git("revert", "--no-edit", "HEAD")
    # Runner bookkeeping lands in every real range; it must not count as a change (#115).
    (it.plans_dir / "progress.md").write_text("bookkeeping\n")
    it.git("add", "-A")
    it.git("commit", "-q", "-m", "chore: progress")
    # The default branch already holds everything else, so main...HEAD has no net diff.
    it.git("branch", "-f", "main", "HEAD~3")
    it.seed_sha = it.git("rev-parse", "HEAD").strip()

    result = it.run()

    assert result.returncode == 0, result.stderr
    assert "no net changes" in result.stdout
    commits = _commit_bodies(it)
    assert commits, "the gate's prd.json write was left uncommitted"
    for _sha, subject, body in commits:
        assert "at runner exit" not in subject
        assert re.search(r"^Refs #7$", body, re.M), subject
    assert it.git("status", "--porcelain") == ""
    assert it.git("rev-parse", "HEAD") == it.remote_git("rev-parse", BRANCH)


def test_e2e_env_is_isolated_to_fakes_and_git(e2e_env):
    env, bin_dir, _ = e2e_env
    assert env["PATH"] == str(bin_dir)
    for tool in ("gh", "claude"):
        found = shutil.which(tool, path=env["PATH"])
        assert found and Path(found).parent == bin_dir
    out = subprocess.run(["git", "--version"], env=env, capture_output=True, timeout=30)
    assert out.returncode == 0
    assert not {"GH_TOKEN", "ANTHROPIC_API_KEY", "SSH_AUTH_SOCK"} & env.keys()


def test_e2e_silent_sessions_stop_the_runner_without_charging_a_plan(make_iteration):
    it = make_iteration(pr_number=7)
    it.set_state(prs=[SEED_PR], claude_silent=True)

    result = it.run()

    assert result.returncode != 0
    assert "consecutive sessions made no attributable progress" in result.stderr
    assert it.state()["claude_calls"] == 5
    plans = json.loads((it.plans_dir / "prd.json").read_text())["plans"]
    assert all(p["attempts"] == 0 and p["status"] != "stalled" for p in plans)
