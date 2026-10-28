#!/usr/bin/env python3
"""Remove the gitignored runner artifacts once /close-iteration has merged the iteration.

Usage: clean-iteration-artifacts.py [--findings-filed]

Prints one line per artifact — `removed: <relpath>` or `skipped: <relpath> (<reason>)` — and
exits 0 even when something is skipped. Output is names and reasons only: the artifacts are
the most sensitive files the runner writes, so their contents never reach the transcript.
Without --findings-filed the findings file is kept; it is the only local copy of findings
nobody has filed yet.
"""

import fcntl
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

_RUNNER_PATH = Path(__file__).resolve().parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _RUNNER_PATH)
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

ABSENT = "absent"
SYMLINK = "symlink"
NOT_IGNORED = "not ignored"
TRACKED = "tracked"
LOCKED = "locked"
FINDINGS_UNFILED = "findings unfiled"


def _git_ok(top: Path, *args: str) -> bool:
    return subprocess.run(["git", *args], cwd=top, capture_output=True).returncode == 0


def _tracked(top: Path, rel: str) -> bool:
    r = subprocess.run(
        ["git", "ls-files", "--", rel], cwd=top, capture_output=True, text=True
    )
    return r.returncode != 0 or bool(r.stdout.strip())


def _unsafe_reason(top: Path, rel: str) -> str | None:
    """Why `rel` must not be deleted, or None when it is a plain ignored untracked path."""
    path = top / rel.rstrip("/")
    if not path.is_symlink() and not path.exists():
        return ABSENT
    top_real = top.resolve()
    parent_real = path.parent.resolve()
    # Trailing slash so /repo-evil doesn't pass as under /repo.
    if path.is_symlink() or not (
        parent_real == top_real or str(parent_real).startswith(f"{top_real}/")
    ):
        return SYMLINK
    # Tracked first: check-ignore says "not ignored" for a tracked path even when a pattern
    # matches, and on a directory it doesn't prove a force-added file inside is untracked.
    if _tracked(top, rel):
        return TRACKED
    if not _git_ok(top, "check-ignore", "-q", "--", rel):
        return NOT_IGNORED
    return None


def _remove_logs_and_lock(logs: Path, lock: Path, lock_present: bool) -> bool:
    """Delete the logs dir and lock while holding the lock. False if it couldn't be taken."""
    if not lock_present:
        shutil.rmtree(logs, ignore_errors=True)
        return True
    try:
        with open(lock) as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            shutil.rmtree(logs)
            # Unlink while still holding the lock; a runner started after this creates a
            # fresh one. Accepted: the user is closing the iteration, so none should run.
            lock.unlink()
    except OSError:
        return False
    return True


def main(argv: list[str]) -> int:
    findings_filed = "--findings-filed" in argv
    top = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    # resolve_config_root dies on a symlinked root, so look before it does.
    symlinked_root = any(
        (top / name).is_symlink() for name in (runner.CONFIG_ROOT_NEW, runner.CONFIG_ROOT_OLD)
    )
    config_root = top / (
        runner.CONFIG_ROOT_OLD if (top / runner.CONFIG_ROOT_OLD).is_dir() else runner.CONFIG_ROOT_NEW
    )
    if not symlinked_root:
        config_root = runner.resolve_config_root(top)
    plans = config_root / "plans"
    logs_rel, lock_rel, findings_rel, summary_rel = runner._artifact_ignore_paths(top, config_root)

    def report(rel: str, reason: str | None) -> None:
        print(f"removed: {rel}" if reason is None else f"skipped: {rel} ({reason})")

    if symlinked_root or plans.is_symlink():
        for rel in (logs_rel, lock_rel, findings_rel, summary_rel):
            report(rel, SYMLINK)
        return 0

    logs_reason = _unsafe_reason(top, logs_rel)
    lock_reason = _unsafe_reason(top, lock_rel)
    if logs_reason is None and lock_reason in (None, ABSENT):
        lock_present = lock_reason is None
        if _remove_logs_and_lock(top / logs_rel.rstrip("/"), top / lock_rel, lock_present):
            report(logs_rel, None)
            report(lock_rel, None if lock_present else ABSENT)
        else:
            logs_reason = lock_reason = LOCKED
            report(logs_rel, LOCKED)
            report(lock_rel, LOCKED)
    else:
        report(logs_rel, logs_reason)
        report(lock_rel, lock_reason)

    for rel in (findings_rel, summary_rel):
        reason = _unsafe_reason(top, rel)
        if reason is None and rel == findings_rel and not findings_filed:
            reason = FINDINGS_UNFILED
        if reason is None:
            (top / rel).unlink()
        report(rel, reason)

    if plans.is_dir() and not any(plans.iterdir()):
        plans.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
