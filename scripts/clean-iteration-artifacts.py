#!/usr/bin/env python3
"""Remove the gitignored runner artifacts once /close-iteration has merged the iteration.

Usage: clean-iteration-artifacts.py [--findings-filed] (see --help)

Prints one line per artifact — `removed: <relpath>` or `skipped: <relpath> (<reason>)` — and
exits 0 even when something is skipped. Output is names and reasons only: the artifacts are
the most sensitive files the runner writes, so their contents never reach the transcript.
Without --findings-filed the findings file is kept; it is the only local copy of findings
nobody has filed yet.
"""

import argparse
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
DELETE_FAILED = "delete failed"
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


def _remove_logs_and_lock(
    logs: Path, lock: Path, logs_reason: str | None, lock_reason: str | None
) -> tuple[str | None, str | None]:
    """Delete whichever of logs/lock is safe; return each one's skip reason (None = removed).

    The lock, when it is a real file, is held while deleting. The runner takes it only around
    each prd.json write, so this catches a runner mid-write, not one that is merely running —
    /close-iteration assumes no runner is active.
    """
    # A symlinked lock must not be opened: flock would follow it out of the repo.
    guard = lock_reason in (None, TRACKED, NOT_IGNORED)
    if not guard:
        return _delete_logs_and_lock(logs, lock, logs_reason, lock_reason)
    try:
        with open(lock) as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return _delete_logs_and_lock(logs, lock, logs_reason, lock_reason)
    except OSError:
        return LOCKED, LOCKED


def _delete_logs_and_lock(
    logs: Path, lock: Path, logs_reason: str | None, lock_reason: str | None
) -> tuple[str | None, str | None]:
    if logs_reason is None:
        try:
            shutil.rmtree(logs)
        except OSError:
            # Lock stays so the next /close-iteration still has a guard for the leftovers.
            return DELETE_FAILED, lock_reason or DELETE_FAILED
    if lock_reason is None:
        # Unlink while still holding the lock; a runner started after this creates a
        # fresh one. Accepted: the user is closing the iteration, so none should run.
        try:
            lock.unlink()
        except OSError:
            return logs_reason, DELETE_FAILED
    return logs_reason, lock_reason


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove the gitignored runner artifacts after /close-iteration's merge."
    )
    parser.add_argument(
        "--findings-filed",
        action="store_true",
        help="also remove the SDLC findings file (only once every finding is filed or dismissed)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    findings_filed = _parse_args(argv).findings_filed
    toplevel = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if toplevel.returncode != 0:
        print("error: not inside a git repository; run from the project root", file=sys.stderr)
        return 1
    top = Path(toplevel.stdout.strip())
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

    if symlinked_root:
        for rel in (logs_rel, lock_rel, findings_rel, summary_rel):
            report(rel, SYMLINK)
        return 0

    # Logs and lock live under plans/; the findings and summary files don't, so a symlinked
    # plans/ only rules out the first two.
    plans_symlinked = plans.is_symlink()
    if plans_symlinked:
        logs_reason = lock_reason = SYMLINK
    else:
        logs_reason, lock_reason = _remove_logs_and_lock(
            top / logs_rel.rstrip("/"),
            top / lock_rel,
            _unsafe_reason(top, logs_rel),
            _unsafe_reason(top, lock_rel),
        )
    report(logs_rel, logs_reason)
    report(lock_rel, lock_reason)

    for rel in (findings_rel, summary_rel):
        reason = _unsafe_reason(top, rel)
        if reason is None and rel == findings_rel and not findings_filed:
            reason = FINDINGS_UNFILED
        if reason is None:
            (top / rel).unlink()
        report(rel, reason)

    if not plans_symlinked and plans.is_dir() and not any(plans.iterdir()):
        plans.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
