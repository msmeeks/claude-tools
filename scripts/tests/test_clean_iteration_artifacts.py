"""`/close-iteration` Step 9e helper: removes the gitignored runner artifacts after merge.

Runs the script as a subprocess against a real git repo, since the safety rules (ignore,
tracked, symlink) are all properties of git's view of the tree.
"""

import fcntl
import shutil
import subprocess
import sys
from pathlib import Path

from ._git_helpers import _git, _init_repo

_SCRIPT = Path(__file__).resolve().parent.parent / "clean-iteration-artifacts.py"
CFG = "docs/agents"
LOGS = f"{CFG}/plans/implementation-logs/"
LOCK = f"{CFG}/plans/prd.json.lock"
FINDINGS = f"{CFG}/sdlc-review-findings.md"
SUMMARY = f"{CFG}/pr-summary.md"
IGNORED = [LOGS, LOCK, FINDINGS, SUMMARY]


def _repo(tmp_path, ignore=tuple(IGNORED), populate=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / CFG / "plans").mkdir(parents=True)
    (repo / ".git" / "info" / "exclude").write_text("".join(f"{p}\n" for p in ignore))
    if populate:
        (repo / LOGS).mkdir()
        (repo / LOGS / "x.log").write_text("log\n")
        (repo / LOCK).write_text("")
        (repo / FINDINGS).write_text("findings\n")
        (repo / SUMMARY).write_text("summary\n")
    return repo


def _clean(repo, *flags):
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), *flags],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_removes_all_four_and_empty_plans_dir(tmp_path):
    repo = _repo(tmp_path)

    out = _clean(repo, "--findings-filed")

    assert out == [
        f"removed: {LOGS}",
        f"removed: {LOCK}",
        f"removed: {FINDINGS}",
        f"removed: {SUMMARY}",
    ]
    assert not (repo / CFG / "plans").exists()
    assert not (repo / FINDINGS).exists()


def test_archive_survives(tmp_path):
    repo = _repo(tmp_path)
    (repo / CFG / "plans" / "archive").mkdir()
    (repo / CFG / "plans" / "archive" / "p.md").write_text("plan\n")

    _clean(repo, "--findings-filed")

    assert (repo / CFG / "plans" / "archive" / "p.md").exists()
    assert not (repo / LOGS).exists()


def test_tracked_file_inside_logs_is_kept(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "add", "-f", f"{LOGS}x.log")

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {LOGS} (tracked)" in out
    assert (repo / LOGS / "x.log").exists()


def test_tracked_findings_file_is_kept(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "add", "-f", FINDINGS)

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {FINDINGS} (tracked)" in out
    assert (repo / FINDINGS).exists()


def test_not_ignored_file_is_kept(tmp_path):
    repo = _repo(tmp_path, ignore=[LOGS, LOCK, FINDINGS])

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {SUMMARY} (not ignored)" in out
    assert (repo / SUMMARY).exists()


def test_symlinked_plans_dir_touches_nothing_outside(tmp_path):
    repo = _repo(tmp_path, populate=False)
    outside = tmp_path / "outside"
    (outside / "implementation-logs").mkdir(parents=True)
    (outside / "implementation-logs" / "x.log").write_text("log\n")
    (outside / "prd.json.lock").write_text("")
    (repo / CFG / "plans").rmdir()
    (repo / CFG / "plans").symlink_to(outside)
    (repo / FINDINGS).write_text("findings\n")

    out = _clean(repo, "--findings-filed")

    assert out == [
        f"skipped: {LOGS} (symlink)",
        f"skipped: {LOCK} (symlink)",
        # Config-root files sit outside plans/, so the symlink is no reason to keep them.
        f"removed: {FINDINGS}",
        f"skipped: {SUMMARY} (absent)",
    ]
    assert (outside / "implementation-logs" / "x.log").exists()
    assert (outside / "prd.json.lock").exists()
    assert not (repo / FINDINGS).exists()


def test_symlinked_leaf_is_kept(tmp_path):
    repo = _repo(tmp_path)
    target = tmp_path / "elsewhere.md"
    target.write_text("keep\n")
    (repo / SUMMARY).unlink()
    (repo / SUMMARY).symlink_to(target)

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {SUMMARY} (symlink)" in out
    assert target.exists()


def test_held_lock_keeps_logs_and_lock_but_removes_config_root_files(tmp_path):
    repo = _repo(tmp_path)
    with open(repo / LOCK) as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        out = _clean(repo, "--findings-filed")

    assert f"skipped: {LOGS} (locked)" in out
    assert f"skipped: {LOCK} (locked)" in out
    assert (repo / LOGS / "x.log").exists()
    assert (repo / LOCK).exists()
    assert not (repo / FINDINGS).exists()
    assert not (repo / SUMMARY).exists()


def test_findings_kept_without_flag(tmp_path):
    repo = _repo(tmp_path)

    out = _clean(repo)

    assert f"skipped: {FINDINGS} (findings unfiled)" in out
    assert (repo / FINDINGS).exists()
    assert not (repo / SUMMARY).exists()


def test_absent_artifacts_reported_absent(tmp_path):
    repo = _repo(tmp_path, populate=False)

    out = _clean(repo, "--findings-filed")

    assert out == [f"skipped: {p} (absent)" for p in IGNORED]


def test_output_never_includes_file_contents(tmp_path):
    repo = _repo(tmp_path)
    (repo / LOGS / "x.log").write_text("SECRET-LOG-LINE\n")
    (repo / FINDINGS).write_text("SECRET-FINDING\n")

    out = "\n".join(_clean(repo))

    assert "SECRET" not in out


def test_logs_removed_and_lock_skipped_when_lock_is_tracked(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "add", "-f", LOCK)

    out = _clean(repo, "--findings-filed")

    assert f"removed: {LOGS}" in out
    assert f"skipped: {LOCK} (tracked)" in out
    assert not (repo / LOGS).exists()
    assert (repo / LOCK).exists()


def test_lock_removed_when_logs_absent(tmp_path):
    repo = _repo(tmp_path)
    shutil.rmtree(repo / LOGS)

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {LOGS} (absent)" in out
    assert f"removed: {LOCK}" in out
    assert not (repo / LOCK).exists()


def test_logs_kept_and_lock_removed_when_logs_tracked(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "add", "-f", f"{LOGS}x.log")

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {LOGS} (tracked)" in out
    assert f"removed: {LOCK}" in out
    assert (repo / LOGS / "x.log").exists()
    assert not (repo / LOCK).exists()


def test_logs_removed_when_lock_absent(tmp_path):
    repo = _repo(tmp_path)
    (repo / LOCK).unlink()

    out = _clean(repo, "--findings-filed")

    assert f"removed: {LOGS}" in out
    assert f"skipped: {LOCK} (absent)" in out
    assert not (repo / LOGS).exists()


def test_legacy_meta_root_is_cleaned(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    meta = "meta"
    paths = [
        f"{meta}/plans/implementation-logs/",
        f"{meta}/plans/prd.json.lock",
        f"{meta}/sdlc-review-findings.md",
        f"{meta}/pr-summary.md",
    ]
    (repo / ".git" / "info" / "exclude").write_text("".join(f"{p}\n" for p in paths))
    (repo / paths[0]).mkdir(parents=True)
    (repo / paths[0] / "x.log").write_text("log\n")
    for p in paths[1:]:
        (repo / p).write_text("")

    out = _clean(repo, "--findings-filed")

    assert out == [f"removed: {p}" for p in paths]
    assert not (repo / meta / "plans").exists()


def test_symlinked_config_root_skips_all_four(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    outside = tmp_path / "outside"
    (outside / "plans" / "implementation-logs").mkdir(parents=True)
    (outside / "plans" / "implementation-logs" / "x.log").write_text("log\n")
    (outside / "plans" / "prd.json.lock").write_text("")
    (outside / "sdlc-review-findings.md").write_text("findings\n")
    (outside / "pr-summary.md").write_text("summary\n")
    (repo / "docs").mkdir()
    (repo / CFG).symlink_to(outside)

    out = _clean(repo, "--findings-filed")

    assert out == [f"skipped: {p} (symlink)" for p in IGNORED]
    assert sorted(p.name for p in outside.rglob("*") if p.is_file()) == [
        "pr-summary.md",
        "prd.json.lock",
        "sdlc-review-findings.md",
        "x.log",
    ]


def test_config_root_resolving_outside_repo_is_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    outside = tmp_path / "outside"
    (outside / "agents" / "plans" / "implementation-logs").mkdir(parents=True)
    (outside / "agents" / "plans" / "implementation-logs" / "x.log").write_text("log\n")
    (outside / "agents" / "plans" / "prd.json.lock").write_text("")
    (outside / "agents" / "sdlc-review-findings.md").write_text("findings\n")
    (outside / "agents" / "pr-summary.md").write_text("summary\n")
    (repo / "docs").symlink_to(outside)
    (repo / ".git" / "info" / "exclude").write_text("".join(f"{p}\n" for p in IGNORED))

    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--findings-filed"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # The runner's root validation refuses before any delete is considered.
    assert r.returncode != 0
    assert "removed:" not in r.stdout
    assert (outside / "agents" / "plans" / "implementation-logs" / "x.log").exists()
    assert (outside / "agents" / "plans" / "prd.json.lock").exists()
    assert (outside / "agents" / "pr-summary.md").exists()


def test_tracked_lock_is_kept(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "add", "-f", LOCK)

    out = _clean(repo, "--findings-filed")

    assert f"skipped: {LOCK} (tracked)" in out
    assert (repo / LOCK).exists()


def test_rmtree_failure_reports_delete_failed_and_keeps_lock(tmp_path):
    repo = _repo(tmp_path)
    stuck = repo / LOGS / "sub"
    stuck.mkdir()
    (stuck / "y.log").write_text("log\n")
    stuck.chmod(0o500)
    try:
        out = _clean(repo, "--findings-filed")
    finally:
        stuck.chmod(0o700)

    assert f"skipped: {LOGS} (delete failed)" in out
    assert f"skipped: {LOCK} (delete failed)" in out
    assert not any(line.startswith("removed") and "plans" in line for line in out[:2])
    assert (repo / LOCK).exists()
    assert (stuck / "y.log").exists()


def test_non_empty_plans_dir_is_not_removed(tmp_path):
    repo = _repo(tmp_path)
    (repo / CFG / "plans" / "keep.md").write_text("plan\n")

    _clean(repo, "--findings-filed")

    assert (repo / CFG / "plans" / "keep.md").exists()


def test_outside_git_repo_fails_without_deleting(tmp_path):
    r = subprocess.run(
        [sys.executable, str(_SCRIPT)], cwd=tmp_path, capture_output=True, text=True, timeout=30
    )

    assert r.returncode != 0
    assert "removed:" not in r.stdout
