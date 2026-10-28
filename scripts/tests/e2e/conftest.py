"""Fixtures for the subprocess e2e layer: a real git repo with a bare origin, fake `gh` and
`claude` on an isolated PATH, and a runner invocation helper.

Fixtures live here, never in tests/conftest.py: the unit tests stub the iteration-state guard
and this layer needs the real one."""

import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from .._git_helpers import _git, _init_repo_with_remote

RUNNER = Path(__file__).resolve().parents[2] / "run-next-plan.py"
FAKES = Path(__file__).resolve().parent / "fakes"
BRANCH = "integration/e2e"
RUN_TIMEOUT = 60


@dataclass
class RunResult:
    returncode: int
    stdout: str  # info() lines (`==> `)
    stderr: str  # warn()/die() lines (`WARN: `/`ERROR: `)


@dataclass
class Iteration:
    repo: Path
    remote: Path
    env: dict
    state_path: Path
    bin_dir: Path
    seed_sha: str = ""

    @property
    def plans_dir(self) -> Path:
        return self.repo / "docs" / "agents" / "plans"

    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def set_state(self, **fields) -> None:
        state = self.state()
        state.update(fields)
        self.state_path.write_text(json.dumps(state))

    def gh_calls(self) -> list[list[str]]:
        return self.state()["calls"]

    def git(self, *args) -> str:
        r = subprocess.run(
            ["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True,
            timeout=30, check=True,
        )
        return r.stdout

    def remote_git(self, *args) -> str:
        r = subprocess.run(
            ["git", *args], cwd=self.remote, env=self.env, capture_output=True, text=True,
            timeout=30, check=True,
        )
        return r.stdout

    def run(self, *args: str) -> RunResult:
        proc = subprocess.Popen(
            [sys.executable, str(RUNNER), *args],
            cwd=self.repo, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            out, err = proc.communicate(timeout=RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            # A spinning fake `claude` would otherwise outlive the test.
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            pytest.fail(f"runner timed out after {RUN_TIMEOUT}s\nstdout:\n{out}\nstderr:\n{err}")
        return RunResult(proc.returncode, out, err)


def _install_fake(src: Path, dest: Path) -> None:
    # Copied, not symlinked: the shebang names this interpreter, and the tracked file stays clean.
    dest.write_text(f"#!{sys.executable}\n{src.read_text()}")
    dest.chmod(0o755)
    # A non-executable file is skipped by PATH lookup, which would fall through to a real tool.
    assert os.access(dest, os.X_OK), dest


def _isolated_env(tmp_path: Path, bin_dir: Path, state_path: Path) -> dict:
    home = tmp_path / "home"
    home.mkdir()
    return {
        "PATH": str(bin_dir),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "TMPDIR": str(tmp_path),
        "E2E_STATE": str(state_path),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "E2E Bot",
        "GIT_AUTHOR_EMAIL": "e2e@example.invalid",
        "GIT_COMMITTER_NAME": "E2E Bot",
        "GIT_COMMITTER_EMAIL": "e2e@example.invalid",
    }


def _link_git(bin_dir: Path) -> None:
    found = shutil.which("git")
    assert found, "git is required for the e2e suite"
    # realpath: macOS /usr/bin/git is an xcrun shim that misbehaves when linked by name.
    target = os.path.realpath(found)
    link = bin_dir / "git"
    try:
        link.symlink_to(target)
        ok = subprocess.run([str(link), "--version"], capture_output=True, timeout=30).returncode == 0
    except OSError:
        ok = False
    if not ok:
        link.unlink(missing_ok=True)
        link.write_text(f'#!/bin/sh\nexec "{target}" "$@"\n')
        link.chmod(0o755)


@pytest.fixture
def e2e_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"prs": [], "issues": {}, "fail": {}, "calls": []}))
    _install_fake(FAKES / "gh.py", bin_dir / "gh")
    _install_fake(FAKES / "claude.py", bin_dir / "claude")
    _link_git(bin_dir)
    return _isolated_env(tmp_path, bin_dir, state_path), bin_dir, state_path


def _plan(file, issues, status="pending"):
    return {"file": file, "status": status, "attempts": 0, "blocked_by": [], "issues": issues}


@pytest.fixture
def make_iteration(tmp_path, e2e_env):
    """Build a repo (HEAD on the integration branch, `main` pushed to a bare origin) holding
    a prd.json for `plans`. Synthetic titles and bodies only."""
    env, bin_dir, state_path = e2e_env

    def build(plans=None, pr_number=None, gate_complete=False, **prd_fields) -> Iteration:
        plans = plans if plans is not None else [
            _plan("alpha.md", [11]), _plan("beta.md", [12, 13]),
        ]
        repo, remote = _init_repo_with_remote(tmp_path, env=env)
        _git(repo, "push", "-q", "origin", "main", env=env)
        _git(repo, "checkout", "-q", "-b", BRANCH, env=env)
        plans_dir = repo / "docs" / "agents" / "plans"
        plans_dir.mkdir(parents=True)
        for entry in plans:
            issues = ", ".join(f"#{n}" for n in entry["issues"])
            (plans_dir / entry["file"]).write_text(f"# Plan\n\n**Issues:** {issues}\n")
        prd = {"integration_branch": BRANCH, "plans": plans, **prd_fields}
        if pr_number is not None:
            prd["pr_number"] = pr_number
        if gate_complete:
            prd.update(sdlc_review_status="complete", sdlc_review_rounds=99)
        (plans_dir / "prd.json").write_text(json.dumps(prd, indent=2) + "\n")
        (plans_dir / "progress.md").write_text("# Progress\n")
        _git(repo, "add", "-A", env=env)
        _git(repo, "commit", "-q", "-m", "chore: seed iteration", env=env)
        it = Iteration(repo, remote, env, state_path, bin_dir)
        it.seed_sha = it.git("rev-parse", "HEAD").strip()
        return it

    return build
