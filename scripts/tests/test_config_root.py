"""Layout resolution: where a repo's project-scoped agent config lives.

Two layouts are supported forever — `docs/agents/` (the upstream Pocock scaffolding this
repo migrated to) and `meta/` (claude-tools' original layout, still used by every repo that
hasn't migrated). The orchestrator must read both, and must refuse to guess when a repo
carries both, because the loop runs unattended under bypassPermissions and commits code and
files issues from whatever it read.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

resolve_config_root = run_next_plan.resolve_config_root


def test_old_layout_resolves_to_meta(tmp_path):
    (tmp_path / "meta" / "plans").mkdir(parents=True)

    assert resolve_config_root(tmp_path) == (tmp_path / "meta").resolve()


def test_new_layout_resolves_to_docs_agents(tmp_path):
    (tmp_path / "docs" / "agents" / "plans").mkdir(parents=True)

    assert resolve_config_root(tmp_path) == (tmp_path / "docs" / "agents").resolve()


def test_both_layouts_present_aborts_naming_both(tmp_path, capsys):
    (tmp_path / "meta" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "agents" / "plans").mkdir(parents=True)

    with pytest.raises(SystemExit):
        resolve_config_root(tmp_path)

    err = capsys.readouterr().err
    assert "docs/agents" in err
    assert "meta" in err


def test_symlinked_config_root_escaping_the_repo_is_refused(tmp_path, capsys):
    outside = tmp_path / "outside" / "agents"
    outside.mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "agents").symlink_to(outside)

    with pytest.raises(SystemExit):
        resolve_config_root(repo)

    assert "symlink" in capsys.readouterr().err.lower()


def test_unscaffolded_repo_defaults_to_the_new_layout(tmp_path):
    """Neither root exists yet. Point at the default for new repos so the missing-prd.json
    error names the path a fresh repo should be scaffolded into."""
    assert resolve_config_root(tmp_path) == (tmp_path / "docs" / "agents").resolve()


@pytest.mark.parametrize(
    ("layout", "prefix"),
    [(("meta",), "meta"), (("docs", "agents"), "docs/agents")],
)
def test_derived_paths_follow_the_resolved_root(tmp_path, layout, prefix):
    (tmp_path.joinpath(*layout) / "plans").mkdir(parents=True)

    assert run_next_plan.config_root_rel(tmp_path) == prefix
    assert run_next_plan.plans_dir_for(tmp_path) == (tmp_path.joinpath(*layout) / "plans").resolve()
    assert run_next_plan.logs_rel(tmp_path) == f"{prefix}/plans/implementation-logs/"
    assert run_next_plan.work_pathspec(tmp_path) == [
        ".",
        f":(exclude){prefix}/plans/implementation-logs/",
    ]
    assert run_next_plan.findings_path(tmp_path).name == "sdlc-review-findings.md"
    assert run_next_plan.findings_path(tmp_path).parent == tmp_path.joinpath(*layout).resolve()
    assert run_next_plan.pr_summary_path(tmp_path).name == "pr-summary.md"
    assert run_next_plan.pr_summary_path(tmp_path).parent == tmp_path.joinpath(*layout).resolve()


def _init_repo(path):
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)


def _is_ignored(repo_root, rel_path):
    import subprocess

    return (
        subprocess.run(["git", "check-ignore", "-q", rel_path], cwd=repo_root).returncode == 0
    )


@pytest.mark.parametrize("prefix", ["meta", "docs/agents"])
def test_artifacts_are_gitignored_under_either_layout(tmp_path, prefix):
    _init_repo(tmp_path)
    (tmp_path / prefix / "plans").mkdir(parents=True)

    run_next_plan._ensure_artifacts_gitignored(tmp_path)

    for rel in (
        f"{prefix}/plans/implementation-logs/run.log",
        f"{prefix}/plans/prd.json.lock",
        f"{prefix}/sdlc-review-findings.md",
        f"{prefix}/pr-summary.md",
    ):
        assert _is_ignored(tmp_path, rel), rel


def test_old_layout_repo_does_not_gain_new_layout_ignore_rules(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "meta" / "plans").mkdir(parents=True)

    run_next_plan._ensure_artifacts_gitignored(tmp_path)

    assert "docs/agents" not in (tmp_path / ".gitignore").read_text()


def test_logging_is_refused_when_the_resolved_log_dir_stays_unignored(tmp_path, capsys):
    """A nested .gitignore negation outranks the root rule the runner appends. Raw session
    transcripts must never become trackable silently — fail loudly instead."""
    _init_repo(tmp_path)
    (tmp_path / "meta" / "plans").mkdir(parents=True)
    (tmp_path / "meta" / "plans" / ".gitignore").write_text(
        "!implementation-logs/\n!implementation-logs/**\n"
    )

    with pytest.raises(SystemExit):
        run_next_plan._ensure_artifacts_gitignored(tmp_path)

    assert "not ignored" in capsys.readouterr().err.lower()


class _FakePopen:
    """Stands in for the plan session: records the prompt, marks the plan done, exits 0."""

    def __init__(self, prompts, prd_path, *args, **kwargs):
        self._prompts = prompts
        self._prd_path = prd_path
        self.returncode = 0
        self.stdin = self
        self.stdout = iter(["<plan>only-plan.md</plan>\n", "<promise>COMPLETE</promise>\n"])

    def write(self, text):
        self._prompts.append(text)

    def close(self):
        import json

        data = json.loads(self._prd_path.read_text())
        for entry in data["plans"]:
            entry["status"] = "done"
        self._prd_path.write_text(json.dumps(data))

    def wait(self):
        return 0


@pytest.mark.parametrize("prefix", ["meta", "docs/agents"])
def test_orchestrator_drives_a_plan_set_to_completion_under_either_layout(
    tmp_path, prefix, monkeypatch
):
    """The whole point of the dual read: a migrated repo and an un-migrated one both run."""
    import subprocess as sp

    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("hi\n")
    sp.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    plans_dir = tmp_path / prefix / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "only-plan.md").write_text("# Plan\n\nNo issue references here.\n")
    (plans_dir / "prd.json").write_text(
        '{"plans": [{"file": "only-plan.md", "status": "pending", "attempts": 0, '
        '"blocked_by": []}], "integration_branch": "integration/x", '
        '"sdlc_review_status": "complete", "sdlc_review_rounds": 99}'
    )

    prompts: list[str] = []
    monkeypatch.setattr(sys, "argv", ["run-next-plan.py"])
    monkeypatch.setattr(run_next_plan.shutil, "which", lambda _cmd: "/usr/bin/claude")
    real_popen = sp.Popen

    def popen(cmd, *a, **kw):
        if cmd and cmd[0] == "claude":
            return _FakePopen(prompts, plans_dir / "prd.json")
        return real_popen(cmd, *a, **kw)

    monkeypatch.setattr(run_next_plan.subprocess, "Popen", popen)
    monkeypatch.setattr(run_next_plan, "invoke_claude", lambda prompt, repo_root: ("", 0))
    monkeypatch.setattr(run_next_plan, "_push_branch", lambda *a, **kw: None)
    monkeypatch.setattr(run_next_plan, "_register_exit_flush", lambda *a, **kw: None)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        run_next_plan.main()

    assert exc.value.code == 0
    import json

    data = json.loads((plans_dir / "prd.json").read_text())
    assert [p["status"] for p in data["plans"]] == ["done"]
    assert f"{prefix}/plans/prd.json" in prompts[0]
    assert (tmp_path / prefix / "plans" / "implementation-logs").is_dir()
    # The run log must never be trackable, under either layout.
    log = next((tmp_path / prefix / "plans" / "implementation-logs").glob("*.log"))
    assert _is_ignored(tmp_path, str(log.relative_to(tmp_path)))
    run_next_plan._log_fh = None
