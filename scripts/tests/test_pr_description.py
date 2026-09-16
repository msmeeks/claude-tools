import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

resolve_pr_number = run_next_plan.resolve_pr_number
splice_summary_block = run_next_plan.splice_summary_block
update_pr_description = run_next_plan.update_pr_description
SUMMARY_START = run_next_plan.SUMMARY_START
SUMMARY_END = run_next_plan.SUMMARY_END


def _write_prd(tmp_path, **extra):
    data = {
        "integration_branch": "integration/x",
        "plans": [{"file": "issue-1.md", "status": "done", "attempts": 1, "blocked_by": []}],
    }
    data.update(extra)
    prd_path = tmp_path / "prd.json"
    prd_path.write_text(json.dumps(data))
    return prd_path


def test_resolve_pr_number_prefers_prd_json_field_without_calling_gh(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("gh should not be called when pr_number is present")

    monkeypatch.setattr(run_next_plan.subprocess, "run", boom)

    assert resolve_pr_number({"pr_number": 12}, "integration/x") == 12


def test_resolve_pr_number_falls_back_to_branch_lookup_when_field_absent(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:4] == ["gh", "pr", "list", "--head"]
        return type("R", (), {"returncode": 0, "stdout": '[{"number": 99}]'})()

    monkeypatch.setattr(run_next_plan.subprocess, "run", fake_run)

    assert resolve_pr_number({}, "integration/x") == 99


def test_resolve_pr_number_returns_none_when_no_pr_exists(monkeypatch):
    def fake_run(cmd, **kwargs):
        return type("R", (), {"returncode": 0, "stdout": "[]"})()

    monkeypatch.setattr(run_next_plan.subprocess, "run", fake_run)

    assert resolve_pr_number({}, "integration/x") is None


def test_splice_inserts_block_and_preserves_existing_closes_section():
    body = "## Plans\n- issue-1.md\n\n## Closes\n\nCloses #1\n"
    result = splice_summary_block(body, "## For the PM\nStuff happened.")

    assert result.startswith(SUMMARY_START)
    assert "## For the PM" in result
    assert "## Closes\n\nCloses #1" in result
    # Block appears exactly once.
    assert result.count(SUMMARY_START) == 1
    assert result.count(SUMMARY_END) == 1


def test_splice_replaces_prior_block_without_stacking():
    first = splice_summary_block("## Closes\n\nCloses #1\n", "OLD summary")
    second = splice_summary_block(first, "NEW summary")

    assert "NEW summary" in second
    assert "OLD summary" not in second
    assert second.count(SUMMARY_START) == 1
    assert "Closes #1" in second


def test_update_pr_description_splices_generated_summary_into_pr_body(tmp_path, monkeypatch):
    prd_path = _write_prd(tmp_path, pr_number=5)
    monkeypatch.setattr(
        run_next_plan, "_generate_pr_summary", lambda data, repo, config_root: "## For the PM\nShipped."
    )
    monkeypatch.setattr(run_next_plan, "_fetch_pr_body", lambda n: "## Closes\n\nCloses #1\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(run_next_plan.subprocess, "run", fake_run)

    update_pr_description(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    edit = next(c for c in calls if c[:3] == ["gh", "pr", "edit"])
    body = edit[edit.index("--body") + 1]
    assert SUMMARY_START in body
    assert "## For the PM" in body
    assert "## Closes\n\nCloses #1" in body
    assert edit[3] == "5"


def test_update_pr_description_scrubs_credential_shaped_text_before_publishing(tmp_path, monkeypatch):
    prd_path = _write_prd(tmp_path, pr_number=5)
    monkeypatch.setattr(
        run_next_plan,
        "_generate_pr_summary",
        lambda data, repo, config_root: "## For the PM\nSee token ghp_AAAABBBBCCCCDDDD in logs.",
    )
    monkeypatch.setattr(run_next_plan, "_fetch_pr_body", lambda n: "## Closes\n\nCloses #1\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(run_next_plan.subprocess, "run", fake_run)

    update_pr_description(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))

    edit = next(c for c in calls if c[:3] == ["gh", "pr", "edit"])
    body = edit[edit.index("--body") + 1]
    assert "ghp_AAAABBBBCCCCDDDD" not in body
    assert "[REDACTED]" in body


def test_update_pr_description_skips_when_no_pr(tmp_path, monkeypatch):
    prd_path = _write_prd(tmp_path)  # no pr_number
    monkeypatch.setattr(run_next_plan, "resolve_pr_number", lambda data, branch: None)

    def no_edit(cmd, **kwargs):
        assert cmd[:3] != ["gh", "pr", "edit"], "must not edit a PR that does not exist"
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(run_next_plan.subprocess, "run", no_edit)
    # Should not raise.
    update_pr_description(prd_path, tmp_path, run_next_plan.resolve_config_root(tmp_path))


def _prd_with_done_plan(tmp_path, plan_file="a.md"):
    plans_dir = tmp_path / "meta" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / plan_file).write_text("**Issues:** #7\n")
    prd_path = plans_dir / "prd.json"
    run_next_plan.save_prd(prd_path, {
        "integration_branch": "integration/x",
        "pr_number": 5,
        "plans": [{"file": plan_file, "status": "done", "attempts": 0, "blocked_by": []}],
    })
    return prd_path, plans_dir


def test_sync_pr_closes_skips_the_gh_round_trip_when_nothing_new_landed(tmp_path):
    prd_path, plans_dir = _prd_with_done_plan(tmp_path)
    run_next_plan._reset_pr_closes_cache()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "view"]:
            return type("R", (), {"returncode": 0, "stdout": '{"body": ""}'})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    with patch.object(run_next_plan.subprocess, "run", side_effect=fake_run):
        run_next_plan.sync_pr_closes(prd_path, plans_dir, "integration/x")
        first = len(calls)
        run_next_plan.sync_pr_closes(prd_path, plans_dir, "integration/x")

    assert any(c[:3] == ["gh", "pr", "edit"] for c in calls)
    assert len(calls) == first, "repeat call with an unchanged closes set must issue no gh calls"


def test_sync_pr_closes_scrubs_credential_shaped_text_before_publishing(tmp_path):
    prd_path, plans_dir = _prd_with_done_plan(tmp_path)
    run_next_plan._reset_pr_closes_cache()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["gh", "pr", "view"]:
            return type("R", (), {
                "returncode": 0,
                "stdout": '{"body": "See token ghp_AAAABBBBCCCCDDDD in logs.\\n"}',
            })()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    with patch.object(run_next_plan.subprocess, "run", side_effect=fake_run):
        run_next_plan.sync_pr_closes(prd_path, plans_dir, "integration/x")

    edit = next(c for c in calls if c[:3] == ["gh", "pr", "edit"])
    body = edit[edit.index("--body") + 1]
    assert "ghp_AAAABBBBCCCCDDDD" not in body
    assert "[REDACTED]" in body


def test_sync_pr_closes_writes_again_once_a_new_plan_completes(tmp_path):
    prd_path, plans_dir = _prd_with_done_plan(tmp_path)
    run_next_plan._reset_pr_closes_cache()
    edits = []

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["gh", "pr", "view"]:
            return type("R", (), {"returncode": 0, "stdout": '{"body": ""}'})()
        if cmd[:3] == ["gh", "pr", "edit"]:
            edits.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": ""})()

    with patch.object(run_next_plan.subprocess, "run", side_effect=fake_run):
        run_next_plan.sync_pr_closes(prd_path, plans_dir, "integration/x")

        (plans_dir / "b.md").write_text("**Issues:** #8\n")
        data = run_next_plan.load_prd(prd_path)
        data["plans"].append({"file": "b.md", "status": "done", "attempts": 0, "blocked_by": []})
        run_next_plan.save_prd(prd_path, data)

        run_next_plan.sync_pr_closes(prd_path, plans_dir, "integration/x")

    assert len(edits) == 2
