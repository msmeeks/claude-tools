"""Layout resolution: where a repo's project-scoped agent config lives.

Two layouts are supported forever — `docs/agents/` (the upstream Pocock scaffolding this
repo migrated to) and `meta/` (claude-tools' original layout, still used by every repo that
hasn't migrated). The orchestrator must read both, and must refuse to guess when a repo
carries both, because the loop runs unattended under bypassPermissions and commits code and
files issues from whatever it read.
"""

import importlib.util
import json
import subprocess
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


def test_intermediate_symlinked_ancestor_escaping_the_repo_is_refused(tmp_path, capsys):
    """The leaf itself (`docs/agents`) can be a real directory while a parent (`docs`) is a
    symlink pointing outside the repo — resolve() still follows it, so the outside-repo check,
    not the leaf-is-symlink check, must be what catches this."""
    outside = tmp_path / "outside" / "docs"
    (outside / "agents" / "plans").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "docs").symlink_to(outside)

    with pytest.raises(SystemExit):
        resolve_config_root(repo)

    assert "outside the repo" in capsys.readouterr().err.lower()


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
    config_root = resolve_config_root(tmp_path)

    assert run_next_plan.config_root_rel(tmp_path, config_root) == prefix
    assert run_next_plan.plans_dir_for(config_root) == (tmp_path.joinpath(*layout) / "plans").resolve()
    assert run_next_plan.logs_rel(tmp_path, config_root) == f"{prefix}/plans/implementation-logs/"
    assert run_next_plan.work_pathspec(tmp_path, config_root) == [
        ".",
        f":(exclude){prefix}/plans/implementation-logs/",
    ]
    assert run_next_plan.findings_path(config_root).name == "sdlc-review-findings.md"
    assert run_next_plan.findings_path(config_root).parent == tmp_path.joinpath(*layout).resolve()
    assert run_next_plan.pr_summary_path(config_root).name == "pr-summary.md"
    assert run_next_plan.pr_summary_path(config_root).parent == tmp_path.joinpath(*layout).resolve()


@pytest.fixture(autouse=True)
def _no_network_finished_iteration_guard(monkeypatch):
    monkeypatch.setattr(run_next_plan, "_iteration_finished", lambda *a, **kw: None)


def _init_repo(path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)


def _exclude_text(repo_root):
    exclude = repo_root / ".git" / "info" / "exclude"
    return exclude.read_text() if exclude.exists() else ""


def test_artifact_ignores_never_touch_the_tracked_gitignore(tmp_path):
    """A .gitignore edit would be swept into the first work commit and show up in the diff
    the SDLC reviewers see. The ignores must live in .git/info/exclude instead."""
    _init_repo(tmp_path)
    (tmp_path / "meta" / "plans").mkdir(parents=True)
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    run_next_plan._ensure_artifacts_gitignored(tmp_path, resolve_config_root(tmp_path))

    assert (tmp_path / ".gitignore").read_text() == "node_modules/\n"
    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=tmp_path, check=True
    ).stdout
    assert status == ""
    assert _is_ignored(tmp_path, "meta/pr-summary.md")


def test_artifact_ignores_are_written_inside_a_linked_worktree(tmp_path):
    _init_repo(tmp_path)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "c"], cwd=tmp_path, check=True)
    wt = tmp_path.parent / (tmp_path.name + "-wt")
    subprocess.run(["git", "worktree", "add", "-q", str(wt)], cwd=tmp_path, check=True)
    (wt / "meta" / "plans").mkdir(parents=True)

    run_next_plan._ensure_artifacts_gitignored(wt, resolve_config_root(wt))

    assert _is_ignored(wt, "meta/pr-summary.md")
    assert not (wt / ".gitignore").exists()


def _is_ignored(repo_root, rel_path):
    return (
        subprocess.run(["git", "check-ignore", "-q", rel_path], cwd=repo_root).returncode == 0
    )


@pytest.mark.parametrize("prefix", ["meta", "docs/agents"])
def test_artifacts_are_gitignored_under_either_layout(tmp_path, prefix):
    _init_repo(tmp_path)
    (tmp_path / prefix / "plans").mkdir(parents=True)

    run_next_plan._ensure_artifacts_gitignored(tmp_path, resolve_config_root(tmp_path))

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

    run_next_plan._ensure_artifacts_gitignored(tmp_path, resolve_config_root(tmp_path))

    assert "docs/agents" not in _exclude_text(tmp_path)


def test_exclude_append_separates_from_a_final_line_without_a_trailing_newline(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "meta" / "plans").mkdir(parents=True)
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text("node_modules/")  # no trailing newline

    run_next_plan._ensure_artifacts_gitignored(tmp_path, resolve_config_root(tmp_path))

    contents = exclude.read_text()
    assert "node_modules/\nmeta/plans/prd.json.lock" not in contents
    assert _is_ignored(tmp_path, "meta/plans/prd.json.lock")


def test_logging_is_refused_when_the_resolved_log_dir_stays_unignored(tmp_path, capsys):
    """A nested .gitignore negation outranks the root rule the runner appends. Raw session
    transcripts must never become trackable silently — fail loudly instead."""
    _init_repo(tmp_path)
    (tmp_path / "meta" / "plans").mkdir(parents=True)
    (tmp_path / "meta" / "plans" / ".gitignore").write_text(
        "!implementation-logs/\n!implementation-logs/**\n"
    )

    with pytest.raises(SystemExit):
        run_next_plan._ensure_artifacts_gitignored(tmp_path, resolve_config_root(tmp_path))

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
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("hi\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

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
    real_popen = subprocess.Popen

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
    data = json.loads((plans_dir / "prd.json").read_text())
    assert [p["status"] for p in data["plans"]] == ["done"]
    assert f"{prefix}/plans/prd.json" in prompts[0]
    assert (tmp_path / prefix / "plans" / "implementation-logs").is_dir()
    # The run log must never be trackable, under either layout.
    log = next((tmp_path / prefix / "plans" / "implementation-logs").glob("*.log"))
    assert _is_ignored(tmp_path, str(log.relative_to(tmp_path)))
    run_next_plan._log_fh = None


def test_config_root_is_resolved_exactly_once_per_run(tmp_path, monkeypatch):
    """resolve_config_root performs real filesystem checks, including the both-layouts-present
    abort. It must run once near the top of main() and hand its result down, not be
    re-derived at each of the many call sites that need a config-root-relative value —
    otherwise a mid-run change to the working tree could trip the abort deep into a run,
    after other work has already been committed."""
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("hi\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    plans_dir = tmp_path / "docs" / "agents" / "plans"
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
    real_popen = subprocess.Popen

    def popen(cmd, *a, **kw):
        if cmd and cmd[0] == "claude":
            return _FakePopen(prompts, plans_dir / "prd.json")
        return real_popen(cmd, *a, **kw)

    monkeypatch.setattr(run_next_plan.subprocess, "Popen", popen)
    monkeypatch.setattr(run_next_plan, "invoke_claude", lambda prompt, repo_root: ("", 0))
    monkeypatch.setattr(run_next_plan, "_push_branch", lambda *a, **kw: None)
    monkeypatch.setattr(run_next_plan, "_register_exit_flush", lambda *a, **kw: None)
    monkeypatch.chdir(tmp_path)

    calls = []
    real_resolve = run_next_plan.resolve_config_root

    def counting_resolve(repo_root):
        calls.append(repo_root)
        return real_resolve(repo_root)

    monkeypatch.setattr(run_next_plan, "resolve_config_root", counting_resolve)

    with pytest.raises(SystemExit):
        run_next_plan.main()

    run_next_plan._log_fh = None
    assert len(calls) == 1


# --- commit reference template -------------------------------------------------------------

DEFAULT_REF = "Refs #{n}"


@pytest.fixture(params=["docs/agents", "meta"])
def tracker_root(request, tmp_path):
    root = tmp_path / request.param
    (root / "plans").mkdir(parents=True)
    return resolve_config_root(tmp_path)


def _write_tracker(root, section_body):
    (root / "issue-tracker.md").write_text(f"# Tracker\n\n## Commit references\n\n{section_body}")


def test_commit_ref_template_defaults_when_file_missing(tracker_root):
    assert run_next_plan._load_commit_ref_template(tracker_root) == DEFAULT_REF


def test_commit_ref_template_defaults_when_section_missing(tracker_root):
    (tracker_root / "issue-tracker.md").write_text("# Tracker\n\nNothing here.\n")

    assert run_next_plan._load_commit_ref_template(tracker_root) == DEFAULT_REF


def test_commit_ref_template_custom_is_used(tracker_root):
    _write_tracker(tracker_root, "\nSee #{n}\n")

    assert run_next_plan._load_commit_ref_template(tracker_root) == "See #{n}"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("Refs #\n", "no {n}"),
        ("{n} and {n}\n", "multiple {n}"),
        ("Refs `#{n}`\n", "disallowed characters"),
        ("Refs $(x) #{n}\n", "disallowed characters"),
        ("R" * 41 + " {n}\n", "too long"),
    ],
)
def test_commit_ref_template_invalid_warns_with_reason_and_defaults(tracker_root, capsys, body, reason):
    _write_tracker(tracker_root, body)

    assert run_next_plan._load_commit_ref_template(tracker_root) == DEFAULT_REF
    err = capsys.readouterr().err
    assert "issue-tracker.md" in err
    assert reason in err
    assert f"'{body.strip()}'" not in err and f"({body.strip()}" not in err


def test_commit_ref_template_only_first_line_is_read(tracker_root):
    _write_tracker(tracker_root, "Refs #{n}\n\nignored {n} `x`\n")

    assert run_next_plan._load_commit_ref_template(tracker_root) == DEFAULT_REF


def test_commit_ref_template_trailing_newline_bypass_is_rejected(tracker_root, capsys):
    # A control character after a valid prefix must not slip past the whitelist.
    _write_tracker(tracker_root, "Refs #{n}\x00payload\n")

    assert run_next_plan._load_commit_ref_template(tracker_root) == DEFAULT_REF
    assert "disallowed characters" in capsys.readouterr().err


def test_commit_ref_template_oversized_file_is_capped(tracker_root):
    (tracker_root / "issue-tracker.md").write_text("x" * 100_000 + "\n## Commit references\n\nSee #{n}\n")

    assert run_next_plan._load_commit_ref_template(tracker_root) == DEFAULT_REF


@pytest.mark.parametrize("bad", [True, False, "7", -1, 0, 10**9, None, 1.5])
def test_coerce_refs_drops_non_positive_ints_bools_and_out_of_range(bad):
    assert run_next_plan._coerce_refs([bad, 5]) == [5]


def test_coerce_refs_dedupes_in_order_and_caps_at_20(capsys):
    assert run_next_plan._coerce_refs([3, 1, 3, 2]) == [3, 1, 2]
    assert run_next_plan._coerce_refs(list(range(1, 40))) == list(range(1, 21))


def test_coerce_refs_warns_with_count_only(capsys):
    run_next_plan._coerce_refs(["secret", 4])

    err = capsys.readouterr().err
    assert "1" in err
    assert "secret" not in err


def test_format_refs_renders_template_per_issue():
    assert run_next_plan._format_refs("Refs #{n}", [7, 8]) == "Refs #7, Refs #8"
    assert run_next_plan._format_refs("Refs #{n}", []) == ""
