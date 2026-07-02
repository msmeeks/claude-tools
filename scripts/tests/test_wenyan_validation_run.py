import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "wenyan_validation_run.py"
_spec = importlib.util.spec_from_file_location("wenyan_validation_run", _MODULE_PATH)
wvr = importlib.util.module_from_spec(_spec)
sys.modules["wenyan_validation_run"] = wvr
_spec.loader.exec_module(wvr)

select_pr_corpus = wvr.select_pr_corpus
redact_secrets = wvr.redact_secrets
compute_drift = wvr.compute_drift
evaluate_corpus_verdict = wvr.evaluate_corpus_verdict
load_checkpoint = wvr.load_checkpoint
save_checkpoint = wvr.save_checkpoint
mark_pass_complete = wvr.mark_pass_complete
is_pass_complete = wvr.is_pass_complete
caveman_directive_disabled = wvr.caveman_directive_disabled


# --- PR corpus selection ---


def _candidate(repo, number, size_type, has_recorded_findings=False):
    return {
        "repo": repo,
        "number": number,
        "size_type": size_type,
        "has_recorded_findings": has_recorded_findings,
    }


def test_select_pr_corpus_requires_at_least_one_bible_flashcards_pr():
    candidates = [
        _candidate("claude-tools", 1, "small fix"),
        _candidate("claude-tools", 2, "medium feature"),
        _candidate("claude-tools", 3, "large refactor"),
        _candidate("claude-tools", 4, "security-touching"),
        _candidate("claude-tools", 5, "UI-touching"),
    ]

    with pytest.raises(ValueError, match="bible-flashcards"):
        select_pr_corpus(candidates, corpus_size=5)


def test_select_pr_corpus_selects_five_with_rationale_and_prefers_recorded_findings():
    candidates = [
        _candidate("claude-tools", 1, "small fix", has_recorded_findings=True),
        _candidate("claude-tools", 2, "medium feature", has_recorded_findings=True),
        _candidate("claude-tools", 3, "large refactor"),
        _candidate("claude-tools", 4, "security-touching"),
        _candidate("bible-flashcards", 10, "UI-touching", has_recorded_findings=True),
        _candidate("claude-tools", 5, "small fix"),
    ]

    corpus = select_pr_corpus(candidates, corpus_size=5)

    assert len(corpus) == 5
    assert any(pr["repo"] == "bible-flashcards" for pr in corpus)
    assert all("rationale" in pr and pr["rationale"] for pr in corpus)
    # PRs with recorded findings are preferred ground truth and should be included first
    recorded = [c for c in candidates if c["has_recorded_findings"]]
    selected_numbers = {(pr["repo"], pr["number"]) for pr in corpus}
    for c in recorded:
        assert (c["repo"], c["number"]) in selected_numbers


def test_select_pr_corpus_raises_when_fewer_than_corpus_size_candidates():
    candidates = [_candidate("bible-flashcards", 10, "small fix")]

    with pytest.raises(ValueError, match="not enough"):
        select_pr_corpus(candidates, corpus_size=5)


# --- Redaction ---


def test_redact_secrets_redacts_authorization_header():
    text = "failing request sent Authorization: Bearer sk-abc123def456"
    assert "sk-abc123def456" not in redact_secrets(text)
    assert "REDACTED" in redact_secrets(text)


def test_redact_secrets_redacts_email_shaped_substrings():
    text = "contact person is jane.doe@example.com about this"
    result = redact_secrets(text)
    assert "jane.doe@example.com" not in result
    assert "REDACTED" in result


def test_redact_secrets_leaves_unrelated_text_untouched():
    text = "file.py:42 missing null check on user input"
    assert redact_secrets(text) == text


def test_redact_secrets_redacts_full_token_after_bearer_scheme():
    text = "failing request sent Authorization: Bearer ghp_abc123def456"
    result = redact_secrets(text)
    assert "ghp_abc123def456" not in result
    assert "Bearer" not in result


# --- Drift computation ---


def test_compute_drift_reports_zero_mismatches_for_identical_findings():
    findings = [{"file": "a.py", "line": 10, "substance": "missing null check"}]

    result = compute_drift(findings, findings)

    assert result["mismatches"] == []
    assert result["ship"] is True


def test_compute_drift_reports_mismatch_for_differing_line():
    baseline = [{"file": "a.py", "line": 10, "substance": "missing null check"}]
    wenyan = [{"file": "a.py", "line": 11, "substance": "missing null check"}]

    result = compute_drift(baseline, wenyan)

    assert len(result["mismatches"]) == 1
    assert result["ship"] is False


def test_compute_drift_reports_mismatch_for_missing_finding():
    baseline = [
        {"file": "a.py", "line": 10, "substance": "missing null check"},
        {"file": "b.py", "line": 5, "substance": "sql injection risk"},
    ]
    wenyan = [{"file": "a.py", "line": 10, "substance": "missing null check"}]

    result = compute_drift(baseline, wenyan)

    assert len(result["mismatches"]) == 1
    assert result["ship"] is False


def test_compute_drift_is_order_independent_for_identical_findings():
    baseline = [
        {"file": "a.py", "line": 10, "substance": "missing null check"},
        {"file": "a.py", "line": 50, "substance": "sql injection risk"},
    ]
    wenyan = [
        {"file": "a.py", "line": 50, "substance": "sql injection risk"},
        {"file": "a.py", "line": 10, "substance": "missing null check"},
    ]

    result = compute_drift(baseline, wenyan)

    assert result["mismatches"] == []
    assert result["ship"] is True


def test_evaluate_corpus_verdict_ships_only_when_every_pr_independently_zero_drift():
    per_pr = {
        "claude-tools#1": {"mismatches": [], "ship": True},
        "claude-tools#2": {"mismatches": [], "ship": True},
        "bible-flashcards#10": {"mismatches": [{"file": "x"}], "ship": False},
    }

    verdict = evaluate_corpus_verdict(per_pr)

    assert verdict["ship"] is False
    assert verdict["failed_prs"] == ["bible-flashcards#10"]


def test_evaluate_corpus_verdict_ships_when_all_prs_pass():
    per_pr = {
        "claude-tools#1": {"mismatches": [], "ship": True},
        "claude-tools#2": {"mismatches": [], "ship": True},
    }

    verdict = evaluate_corpus_verdict(per_pr)

    assert verdict["ship"] is True
    assert verdict["failed_prs"] == []


# --- Checkpoint / resume ---


def test_save_and_load_checkpoint_round_trips(tmp_path):
    path = tmp_path / "checkpoint.json"
    state = {"passes": {}}

    save_checkpoint(path, state)
    loaded = load_checkpoint(path)

    assert loaded == state


def test_load_checkpoint_returns_empty_state_when_file_absent(tmp_path):
    path = tmp_path / "does-not-exist.json"

    loaded = load_checkpoint(path)

    assert loaded == {"passes": {}}


def test_mark_pass_complete_then_is_pass_complete_reports_true(tmp_path):
    state = load_checkpoint(tmp_path / "nope.json")

    assert is_pass_complete(state, "claude-tools#1", "baseline") is False

    mark_pass_complete(state, "claude-tools#1", "baseline", {"tokens": 100, "latency_s": 5})

    assert is_pass_complete(state, "claude-tools#1", "baseline") is True
    assert is_pass_complete(state, "claude-tools#1", "wenyan") is False


def test_checkpoint_redacts_secret_like_values_before_persisting(tmp_path):
    state = load_checkpoint(tmp_path / "nope.json")
    mark_pass_complete(
        state,
        "claude-tools#1",
        "baseline",
        {"tokens": 100, "latency_s": 5, "notes": "Authorization: Bearer sk-abc123"},
    )

    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, state)
    reloaded = load_checkpoint(path)

    notes = reloaded["passes"]["claude-tools#1"]["baseline"]["notes"]
    assert "sk-abc123" not in notes
    assert "REDACTED" in notes


# --- /caveman directive disable/restore ---


def test_caveman_directive_disabled_removes_and_restores_directive(tmp_path):
    config_path = tmp_path / "CLAUDE.md"
    original = "# Global Development Standards\n\n/caveman\n\nOther content.\n"
    config_path.write_text(original)

    with caveman_directive_disabled(config_path):
        during = config_path.read_text()
        assert "/caveman" not in during

    assert config_path.read_text() == original


def test_caveman_directive_disabled_restores_on_exception(tmp_path):
    config_path = tmp_path / "CLAUDE.md"
    original = "# Global Development Standards\n\n/caveman\n\nOther content.\n"
    config_path.write_text(original)

    with pytest.raises(RuntimeError), caveman_directive_disabled(config_path):
        assert "/caveman" not in config_path.read_text()
        raise RuntimeError("simulated pass failure partway through")

    assert config_path.read_text() == original


def test_caveman_directive_disabled_is_noop_when_directive_absent(tmp_path):
    config_path = tmp_path / "CLAUDE.md"
    original = "# Global Development Standards\n\nOther content.\n"
    config_path.write_text(original)

    with caveman_directive_disabled(config_path):
        pass

    assert config_path.read_text() == original


# --- pipeline pass invocation: never shells out with interpolated strings ---


def test_run_pipeline_pass_invokes_subprocess_with_argument_array(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        assert isinstance(args, list)
        result = MagicMock()
        result.returncode = 0
        result.stdout = "ISSUE: #1\n"
        return result

    monkeypatch.setattr(wvr.subprocess, "run", fake_run)

    metrics = wvr.run_pipeline_pass(
        {"repo": "claude-tools", "number": 1}, mode="baseline", runner=fake_run
    )

    assert calls, "expected subprocess.run-style runner to be invoked"
    assert "tokens" in metrics
    assert "latency_s" in metrics


def test_run_pipeline_pass_raises_pipeline_error_on_nonzero_exit():
    def fake_run(args, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "boom"
        return result

    with pytest.raises(wvr.PipelineError):
        wvr.run_pipeline_pass(
            {"repo": "claude-tools", "number": 1}, mode="wenyan", runner=fake_run
        )
