"""Real-git repo builders shared by the unit and e2e suites. Non-test module: importing it
must not load the runner (test_orchestration does that in-process)."""

import subprocess


def _run(cmd, env=None, **kwargs):
    return subprocess.run(cmd, check=True, env=env, timeout=30, **kwargs)


def _init_repo(path, env=None):
    _run(["git", "init", "-q", "-b", "main"], env=env, cwd=path)
    _run(["git", "config", "user.email", "test@example.com"], env=env, cwd=path)
    _run(["git", "config", "user.name", "Test"], env=env, cwd=path)
    (path / "README.md").write_text("hello\n")
    _run(["git", "add", "."], env=env, cwd=path)
    _run(["git", "commit", "-q", "-m", "init"], env=env, cwd=path)


def _init_repo_with_remote(tmp_path, env=None):
    remote = tmp_path / "remote.git"
    _run(["git", "init", "-q", "--bare", str(remote)], env=env)
    local = tmp_path / "local"
    local.mkdir()
    _init_repo(local, env=env)
    _run(["git", "remote", "add", "origin", str(remote)], env=env, cwd=local)
    return local, remote


def _remote_log(remote, branch):
    r = subprocess.run(
        ["git", "log", branch, "--format=%s"], cwd=remote, capture_output=True, text=True
    )
    return r.stdout.splitlines()


def _git(local, *args, env=None):
    subprocess.run(["git", *args], cwd=local, check=True, capture_output=True, env=env, timeout=30)
