import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "run-next-plan.py"
_spec = importlib.util.spec_from_file_location("run_next_plan", _MODULE_PATH)
run_next_plan = importlib.util.module_from_spec(_spec)
sys.modules["run_next_plan"] = run_next_plan
_spec.loader.exec_module(run_next_plan)

select_next_plan = run_next_plan.select_next_plan
scan_output = run_next_plan.scan_output


def _plan(file, status="pending", blocked_by=None, attempts=0):
    return {
        "file": file,
        "status": status,
        "attempts": attempts,
        "blocked_by": blocked_by or [],
    }


def test_select_next_plan_returns_none_when_all_done():
    plans = [_plan("a.md", status="done"), _plan("b.md", status="done")]
    assert select_next_plan(plans) is None


def test_select_next_plan_returns_none_when_all_stalled():
    plans = [_plan("a.md", status="stalled"), _plan("b.md", status="stalled")]
    assert select_next_plan(plans) is None


def test_select_next_plan_skips_done_and_stalled_entries():
    plans = [
        _plan("a.md", status="done"),
        _plan("b.md", status="stalled"),
        _plan("c.md", status="pending"),
    ]
    result = select_next_plan(plans)
    assert result["file"] == "c.md"


def test_select_next_plan_returns_none_on_circular_blocked_by():
    plans = [
        _plan("a.md", status="pending", blocked_by=["b.md"]),
        _plan("b.md", status="pending", blocked_by=["a.md"]),
    ]
    assert select_next_plan(plans) is None


def test_select_next_plan_returns_first_eligible_plan_with_no_blockers():
    plans = [
        _plan("a.md", status="pending"),
        _plan("b.md", status="pending"),
    ]
    result = select_next_plan(plans)
    assert result["file"] == "a.md"


def test_scan_output_detects_standalone_complete_sigil():
    text = "some output\n<promise>COMPLETE</promise>\nmore text\n"
    assert scan_output(text, 0) == "complete"


def test_scan_output_does_not_fire_on_embedded_mid_line_sigil():
    text = "blah blah <promise>COMPLETE</promise> trailing text\n"
    assert scan_output(text, 0) != "complete"


def test_scan_output_detects_rate_limit_pattern():
    text = "Error: usage limit reached, please try again later"
    assert scan_output(text, 1) == "rate_limit"


def test_scan_output_returns_error_on_nonzero_exit_without_rate_limit_text():
    text = "Some unrelated failure occurred"
    assert scan_output(text, 1) == "error"


def test_scan_output_returns_ok_on_zero_exit_with_no_sigil():
    text = "Did some work, nothing special happened"
    assert scan_output(text, 0) == "ok"
