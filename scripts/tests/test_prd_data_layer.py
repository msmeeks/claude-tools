import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

load_prd = run_next_plan.load_prd
save_prd = run_next_plan.save_prd
increment_attempts = run_next_plan.increment_attempts
set_status = run_next_plan.set_status
mark_stalled = run_next_plan.mark_stalled
resolve_integration_branch = run_next_plan.resolve_integration_branch


def _valid_prd():
    return {
        "integration_branch": "integration/batch",
        "plans": [
            {
                "file": "issue-1.md",
                "status": "pending",
                "attempts": 0,
                "blocked_by": [],
            }
        ],
    }


def test_save_then_load_round_trips_without_data_loss(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()

    save_prd(prd_path, data)
    loaded = load_prd(prd_path)

    assert loaded == data


def test_save_prd_uses_atomic_tempfile_then_replaces_target(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    # No leftover .prd-*.tmp files after a successful save.
    leftovers = list(tmp_path.glob(".prd-*.tmp"))
    assert leftovers == []
    assert prd_path.exists()


def test_save_prd_leaves_existing_file_untouched_if_write_fails(tmp_path, monkeypatch):
    prd_path = tmp_path / "prd.json"
    original = _valid_prd()
    save_prd(prd_path, original)

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", boom)
    with pytest.raises(OSError):
        save_prd(prd_path, {"integration_branch": "x", "plans": []})

    # Original file is untouched; no stray tmp files remain.
    assert load_prd(prd_path) == original
    assert list(tmp_path.glob(".prd-*.tmp")) == []


def test_increment_attempts_modifies_only_targeted_entry(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["plans"].append(
        {"file": "issue-2.md", "status": "pending", "attempts": 5, "blocked_by": []}
    )
    save_prd(prd_path, data)

    increment_attempts(prd_path, "issue-1.md")

    loaded = load_prd(prd_path)
    by_file = {p["file"]: p for p in loaded["plans"]}
    assert by_file["issue-1.md"]["attempts"] == 1
    assert by_file["issue-2.md"]["attempts"] == 5


def test_increment_attempts_is_idempotent_when_called_twice(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    increment_attempts(prd_path, "issue-1.md")
    increment_attempts(prd_path, "issue-1.md")

    loaded = load_prd(prd_path)
    assert loaded["plans"][0]["attempts"] == 2


def test_set_status_modifies_only_targeted_entry(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["plans"].append(
        {"file": "issue-2.md", "status": "pending", "attempts": 0, "blocked_by": []}
    )
    save_prd(prd_path, data)

    set_status(prd_path, "issue-1.md", "done")

    loaded = load_prd(prd_path)
    by_file = {p["file"]: p for p in loaded["plans"]}
    assert by_file["issue-1.md"]["status"] == "done"
    assert by_file["issue-2.md"]["status"] == "pending"


def test_set_status_is_idempotent(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    set_status(prd_path, "issue-1.md", "in-progress")
    set_status(prd_path, "issue-1.md", "in-progress")

    loaded = load_prd(prd_path)
    assert loaded["plans"][0]["status"] == "in-progress"


def test_set_status_rejects_invalid_status_literal(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    with pytest.raises(SystemExit):
        set_status(prd_path, "issue-1.md", "not-a-real-status")


def test_mark_stalled_sets_status_and_emits_stderr_warning(tmp_path, capsys):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    mark_stalled(prd_path, "issue-1.md")

    loaded = load_prd(prd_path)
    assert loaded["plans"][0]["status"] == "stalled"
    captured = capsys.readouterr()
    assert "issue-1.md" in captured.err
    assert "stalled" in captured.err.lower()


def test_mark_stalled_writes_warning_to_open_log_file(tmp_path, capsys):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    log_path = tmp_path / "run.log"
    with open(log_path, "w") as log_fh:
        run_next_plan._log_fh = log_fh
        try:
            mark_stalled(prd_path, "issue-1.md")
        finally:
            run_next_plan._log_fh = None

    log_contents = log_path.read_text()
    assert "issue-1.md" in log_contents
    assert "stalled" in log_contents.lower()


def test_strip_unsafe_chars_removes_ansi_escapes_and_control_chars():
    poisoned = "issue-1.md\x1b[31m\x07"

    cleaned = run_next_plan._strip_unsafe_chars(poisoned)

    assert "\x1b" not in cleaned
    assert "\x07" not in cleaned
    assert cleaned == "issue-1.md"


def test_increment_attempts_rejects_path_traversal_in_plan_file(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    with pytest.raises(SystemExit):
        increment_attempts(prd_path, "../../.env")


def test_set_status_rejects_path_traversal_in_plan_file(tmp_path):
    prd_path = tmp_path / "prd.json"
    save_prd(prd_path, _valid_prd())

    with pytest.raises(SystemExit):
        set_status(prd_path, "../../.env", "done")


def test_load_prd_raises_systemexit_on_missing_required_keys(tmp_path):
    prd_path = tmp_path / "prd.json"
    prd_path.write_text(json.dumps({"plans": []}))

    with pytest.raises(SystemExit):
        load_prd(prd_path)


def test_load_prd_raises_systemexit_on_invalid_status_literal(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["plans"][0]["status"] = "bogus"
    prd_path.write_text(json.dumps(data))

    with pytest.raises(SystemExit):
        load_prd(prd_path)


def test_load_prd_raises_systemexit_on_non_integer_attempts(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["plans"][0]["attempts"] = "three"
    prd_path.write_text(json.dumps(data))

    with pytest.raises(SystemExit):
        load_prd(prd_path)


def test_load_prd_raises_systemexit_on_path_traversal_in_file_field(tmp_path):
    prd_path = tmp_path / "prd.json"
    data = _valid_prd()
    data["plans"][0]["file"] = "../../.env"
    prd_path.write_text(json.dumps(data))

    with pytest.raises(SystemExit):
        load_prd(prd_path)


def test_load_prd_raises_systemexit_not_typeerror_on_malformed_json(tmp_path):
    prd_path = tmp_path / "prd.json"
    prd_path.write_text("{not valid json")

    with pytest.raises(SystemExit):
        load_prd(prd_path)


def test_resolve_integration_branch_uses_prd_json_value_when_no_cli_override():
    data = _valid_prd()
    data["integration_branch"] = "integration/2026-06-26-esv"

    assert resolve_integration_branch(data, cli_override=None) == "integration/2026-06-26-esv"


def test_resolve_integration_branch_cli_override_wins_over_prd_json():
    data = _valid_prd()
    data["integration_branch"] = "integration/2026-06-26-esv"

    assert resolve_integration_branch(data, cli_override="integration/explicit") == "integration/explicit"
