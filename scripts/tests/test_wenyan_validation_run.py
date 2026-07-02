import importlib.util
import json
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
CostCeilingExceeded = wvr.CostCeilingExceeded


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

    assert is_pass_complete(state, "claude-tools#1", "baseline", rep=1) is False

    mark_pass_complete(state, "claude-tools#1", "baseline", rep=1, metrics={"tokens": 100, "latency_s": 5})

    assert is_pass_complete(state, "claude-tools#1", "baseline", rep=1) is True
    assert is_pass_complete(state, "claude-tools#1", "wenyan", rep=1) is False
    # a second rep of the same (pr, mode) is tracked independently
    assert is_pass_complete(state, "claude-tools#1", "baseline", rep=2) is False


def test_checkpoint_redacts_secret_like_values_before_persisting(tmp_path):
    state = load_checkpoint(tmp_path / "nope.json")
    mark_pass_complete(
        state,
        "claude-tools#1",
        "baseline",
        rep=1,
        metrics={"tokens": 100, "latency_s": 5, "notes": "Authorization: Bearer sk-abc123"},
    )

    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, state)
    reloaded = load_checkpoint(path)

    notes = reloaded["passes"]["claude-tools#1"]["baseline"]["1"]["notes"]
    assert "sk-abc123" not in notes
    assert "REDACTED" in notes


# --- Cost ceiling ---


def test_check_cost_ceiling_raises_when_cumulative_spend_exceeds_max():
    with pytest.raises(wvr.CostCeilingExceeded, match=r"\$31\.00.*\$30"):
        wvr.check_cost_ceiling(cumulative_cost_usd=31.0, max_cost_usd=30.0)


def test_check_cost_ceiling_allows_spend_under_max():
    wvr.check_cost_ceiling(cumulative_cost_usd=29.99, max_cost_usd=30.0)


# --- SessionStart hook disable/restore (the actual caveman-mode source, per settings.json) ---


def test_session_start_hook_disabled_removes_and_restores_hook(tmp_path):
    settings_path = tmp_path / "settings.json"
    original = json.dumps(
        {
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo caveman"}]}]},
            "theme": "dark",
        }
    )
    settings_path.write_text(original)

    with wvr.session_start_hook_disabled(settings_path):
        during = json.loads(settings_path.read_text())
        assert "SessionStart" not in during.get("hooks", {})
        assert during["theme"] == "dark"

    assert settings_path.read_text() == original


def test_session_start_hook_disabled_restores_on_exception(tmp_path):
    settings_path = tmp_path / "settings.json"
    original = json.dumps({"hooks": {"SessionStart": [{"hooks": []}]}})
    settings_path.write_text(original)

    with pytest.raises(RuntimeError), wvr.session_start_hook_disabled(settings_path):
        raise RuntimeError("simulated failure mid-pass")

    assert settings_path.read_text() == original


def test_session_start_hook_disabled_is_noop_when_hook_absent(tmp_path):
    settings_path = tmp_path / "settings.json"
    original = json.dumps({"theme": "dark"})
    settings_path.write_text(original)

    with wvr.session_start_hook_disabled(settings_path):
        pass

    assert settings_path.read_text() == original


# --- Baseline worktree: isolates the plain-prose SKILL.md variant from the real repo ---


def test_baseline_worktree_adds_and_removes_via_git_and_writes_variant(tmp_path):
    calls = []

    def fake_runner(args, **kwargs):
        calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    repo_root = tmp_path / "repo"
    (repo_root / "skills" / "sdlc").mkdir(parents=True)
    (repo_root / "skills" / "sdlc" / "SKILL.md").write_text("wenyan variant content")
    worktree_root = tmp_path / "worktrees"

    with wvr.baseline_worktree(
        repo_root=repo_root,
        worktree_parent=worktree_root,
        baseline_skill_content="plain-prose baseline variant",
        runner=fake_runner,
    ) as worktree_path:
        assert (worktree_path / "skills" / "sdlc" / "SKILL.md").read_text() == "plain-prose baseline variant"
        # the real repo's SKILL.md must never be touched
        assert (repo_root / "skills" / "sdlc" / "SKILL.md").read_text() == "wenyan variant content"

    add_calls = [c for c in calls if "add" in c]
    remove_calls = [c for c in calls if "remove" in c]
    assert add_calls, "expected `git worktree add` to be invoked"
    assert remove_calls, "expected `git worktree remove` to be invoked for teardown"


def test_baseline_worktree_removes_worktree_even_on_exception(tmp_path):
    calls = []

    def fake_runner(args, **kwargs):
        calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    repo_root = tmp_path / "repo"
    (repo_root / "skills" / "sdlc").mkdir(parents=True)
    (repo_root / "skills" / "sdlc" / "SKILL.md").write_text("wenyan variant content")

    with pytest.raises(RuntimeError), wvr.baseline_worktree(
        repo_root=repo_root,
        worktree_parent=tmp_path / "worktrees",
        baseline_skill_content="plain-prose baseline variant",
        runner=fake_runner,
    ):
        raise RuntimeError("simulated pass failure")

    assert any("remove" in c for c in calls), "worktree must be torn down even on exception"


# --- Paired significance test (stdlib-only sign test) + noise floor ---


def test_sign_test_all_positive_deltas_gives_exact_binomial_p_value():
    result = wvr.sign_test([1, 2, 3, 0.5])

    assert result["n"] == 4
    assert result["n_positive"] == 4
    assert result["n_negative"] == 0
    assert result["p_value"] == pytest.approx(0.125)


def test_sign_test_balanced_deltas_gives_high_p_value():
    result = wvr.sign_test([1, -1, 1, -1, 1, -1])

    assert result["n"] == 6
    assert result["p_value"] == pytest.approx(1.0)


def test_sign_test_ignores_zero_deltas():
    result = wvr.sign_test([1, 1, 1, 0])

    assert result["n"] == 3
    assert result["n_positive"] == 3


def test_per_pr_cost_deltas_pairs_mean_baseline_vs_mean_wenyan_by_pr():
    per_pr_metrics = {
        "claude-tools#7": {
            "baseline": {"1": {"total_cost_usd": 0.10}, "2": {"total_cost_usd": 0.20}},
            "wenyan": {"1": {"total_cost_usd": 0.05}, "2": {"total_cost_usd": 0.07}},
        }
    }

    deltas = wvr.per_pr_cost_deltas(per_pr_metrics)

    assert len(deltas) == 1
    d = deltas[0]
    assert d["pr"] == "claude-tools#7"
    assert d["baseline_mean_usd"] == pytest.approx(0.15)
    assert d["wenyan_mean_usd"] == pytest.approx(0.06)
    assert d["delta_usd"] == pytest.approx(0.06 - 0.15)
    assert d["ratio"] == pytest.approx(0.06 / 0.15)


def test_noise_floor_reports_within_condition_spread_across_reps():
    per_pr_metrics = {
        "claude-tools#7": {
            "baseline": {"1": {"total_cost_usd": 0.10}, "2": {"total_cost_usd": 0.20}},
            "wenyan": {"1": {"total_cost_usd": 0.05}, "2": {"total_cost_usd": 0.05}},
        }
    }

    floor = wvr.noise_floor(per_pr_metrics)

    assert floor["claude-tools#7"]["baseline"] == pytest.approx(0.05)  # stdev of [0.10, 0.20]
    assert floor["claude-tools#7"]["wenyan"] == pytest.approx(0.0)


# --- Raw-data CSV export ---


def test_write_csv_emits_one_row_per_pr_mode_rep(tmp_path):
    per_pr_metrics = {
        "claude-tools#7": {
            "baseline": {
                "1": {
                    "usage": {
                        "input_tokens": 100,
                        "cache_creation_input_tokens": 50,
                        "cache_read_input_tokens": 25,
                        "output_tokens": 10,
                    },
                    "total_cost_usd": 0.12,
                    "latency_s": 5.0,
                },
                "2": {
                    "usage": {
                        "input_tokens": 90,
                        "cache_creation_input_tokens": 40,
                        "cache_read_input_tokens": 20,
                        "output_tokens": 8,
                    },
                    "total_cost_usd": 0.10,
                    "latency_s": 4.5,
                },
            },
            "wenyan": {
                "1": {
                    "usage": {
                        "input_tokens": 80,
                        "cache_creation_input_tokens": 30,
                        "cache_read_input_tokens": 15,
                        "output_tokens": 6,
                    },
                    "total_cost_usd": 0.08,
                    "latency_s": 4.0,
                },
                "2": {
                    "usage": {
                        "input_tokens": 85,
                        "cache_creation_input_tokens": 32,
                        "cache_read_input_tokens": 18,
                        "output_tokens": 7,
                    },
                    "total_cost_usd": 0.09,
                    "latency_s": 4.2,
                },
            },
        }
    }

    csv_path = tmp_path / "raw.csv"
    wvr.write_csv(per_pr_metrics, csv_path)

    import csv as _csv

    with csv_path.open() as f:
        rows = list(_csv.DictReader(f))

    assert len(rows) == 4
    row = next(r for r in rows if r["pr"] == "claude-tools#7" and r["mode"] == "wenyan" and r["rep"] == "1")
    assert row["total_cost_usd"] == "0.08"
    assert row["input_tokens"] == "80"
    assert row["cache_read_input_tokens"] == "15"
    assert row["latency_s"] == "4.0"


# --- pipeline pass invocation: never shells out with interpolated strings ---


def _fake_json_result(**usage_overrides):
    import json as _json

    usage = {
        "input_tokens": 100,
        "cache_creation_input_tokens": 50,
        "cache_read_input_tokens": 25,
        "output_tokens": 10,
    }
    usage.update(usage_overrides)
    payload = {
        "result": "ISSUE: #1\n",
        "usage": usage,
        "total_cost_usd": 0.1234,
    }
    result = MagicMock()
    result.returncode = 0
    result.stdout = _json.dumps(payload)
    return result


def test_run_pipeline_pass_invokes_subprocess_with_argument_array(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        assert isinstance(args, list)
        return _fake_json_result()

    monkeypatch.setattr(wvr.subprocess, "run", fake_run)

    metrics = wvr.run_pipeline_pass(
        {"repo": "claude-tools", "number": 1}, mode="baseline", runner=fake_run
    )

    assert calls, "expected subprocess.run-style runner to be invoked"
    assert "--output-format" in calls[0] and "json" in calls[0]
    assert "latency_s" in metrics


def test_run_pipeline_pass_reports_real_usage_and_cost_not_word_count(monkeypatch):
    def fake_run(args, **kwargs):
        return _fake_json_result(
            input_tokens=100, cache_creation_input_tokens=50, cache_read_input_tokens=25, output_tokens=10
        )

    metrics = wvr.run_pipeline_pass(
        {"repo": "claude-tools", "number": 1}, mode="wenyan", runner=fake_run
    )

    assert metrics["usage"] == {
        "input_tokens": 100,
        "cache_creation_input_tokens": 50,
        "cache_read_input_tokens": 25,
        "output_tokens": 10,
    }
    assert metrics["total_cost_usd"] == 0.1234
    # must not fall back to a word-count of the result text
    assert "tokens" not in metrics or metrics.get("tokens") != len(["ISSUE:", "#1"])


def test_run_pipeline_pass_forwards_cwd_to_runner_for_baseline_worktree_isolation(tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(kwargs.get("cwd"))
        return _fake_json_result()

    wvr.run_pipeline_pass(
        {"repo": "claude-tools", "number": 1}, mode="baseline", runner=fake_run, cwd=tmp_path
    )

    assert calls[0] == tmp_path


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


# --- run_experiment: full orchestration wiring ---


def test_run_experiment_runs_every_pr_mode_rep_and_writes_report_and_csv(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "skills" / "sdlc").mkdir(parents=True)
    (repo_root / "skills" / "sdlc" / "SKILL.md").write_text("wenyan HEAD content")
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": []}]}}))

    pipeline_calls = []

    def fake_pipeline_runner(args, **kwargs):
        pipeline_calls.append((args, kwargs.get("cwd")))
        return _fake_json_result()

    def fake_worktree_runner(args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    corpus = [{"repo": "claude-tools", "number": 7, "rationale": "test"}]

    summary = wvr.run_experiment(
        corpus=corpus,
        reps=2,
        checkpoint_path=tmp_path / "checkpoint.json",
        report_path=tmp_path / "report.md",
        csv_path=tmp_path / "raw.csv",
        claude_settings=settings_path,
        repo_root=repo_root,
        worktree_parent=tmp_path / "worktrees",
        baseline_skill_content="plain-prose baseline",
        max_cost_usd=1000.0,
        resume=False,
        pipeline_runner=fake_pipeline_runner,
        worktree_runner=fake_worktree_runner,
    )

    # 1 PR x 2 modes x 2 reps = 4 pipeline invocations
    assert len(pipeline_calls) == 4
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "raw.csv").exists()
    assert summary["cumulative_cost_usd"] == pytest.approx(0.1234 * 4)
    # settings.json restored after the run
    assert json.loads(settings_path.read_text())["hooks"]["SessionStart"] == [{"hooks": []}]


def test_run_experiment_aborts_and_checkpoints_when_cost_ceiling_exceeded(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "skills" / "sdlc").mkdir(parents=True)
    (repo_root / "skills" / "sdlc" / "SKILL.md").write_text("wenyan HEAD content")
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({}))

    def fake_pipeline_runner(args, **kwargs):
        return _fake_json_result()  # each pass costs 0.1234

    def fake_worktree_runner(args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    corpus = [
        {"repo": "claude-tools", "number": 7, "rationale": "test"},
        {"repo": "claude-tools", "number": 8, "rationale": "test"},
    ]
    checkpoint_path = tmp_path / "checkpoint.json"

    with pytest.raises(wvr.CostCeilingExceeded):
        wvr.run_experiment(
            corpus=corpus,
            reps=2,
            checkpoint_path=checkpoint_path,
            report_path=tmp_path / "report.md",
            csv_path=tmp_path / "raw.csv",
            claude_settings=settings_path,
            repo_root=repo_root,
            worktree_parent=tmp_path / "worktrees",
            baseline_skill_content="plain-prose baseline",
            max_cost_usd=0.3,  # crosses after ~3 passes at 0.1234 each
            resume=False,
            pipeline_runner=fake_pipeline_runner,
            worktree_runner=fake_worktree_runner,
        )

    # partial progress persisted so --resume can pick up
    state = wvr.load_checkpoint(checkpoint_path)
    completed = sum(
        1
        for by_mode in state["passes"].values()
        for by_rep in by_mode.values()
        for _ in by_rep.values()
    )
    assert 0 < completed < 4
    # settings.json restored even though the run aborted
    assert settings_path.read_text() == "{}"
