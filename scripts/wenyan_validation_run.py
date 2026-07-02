#!/usr/bin/env python3
"""Offline cost/token/drift validation runner for the wenyan-ultra sdlc-review
handoff protocol.

Runs the full sdlc review pipeline in two conditions — baseline (plain-prose
Phase 3/4, via a disposable git worktree with a hand-authored SKILL.md
variant, never mutating the real repo) vs. wenyan-ultra (current HEAD,
unmodified) — across a 10-PR corpus (claude-tools + bible-flashcards),
2 reps per (PR, mode) to estimate run-to-run noise. Reports real billed API
usage/cost (`--output-format json`), not a word count, plus a paired sign
test across per-PR cost deltas and the original 0-drift-mismatch ship gate.

This script is standalone and is not invoked by any plan/test in this repo
during normal CI — it makes real `claude`/`git worktree` subprocess calls,
temporarily disables the SessionStart caveman-mode hook in
~/.claude/settings.json (restored afterward, including on error/interrupt),
and costs real money (default ceiling: $30, see --max-cost-usd).

Usage:
    python3 scripts/wenyan_validation_run.py [--prs REPO#NUM ...] [--reps N]
        [--max-cost-usd N] [--resume]

Requirements:
    - `claude` CLI on PATH, `git` CLI on PATH (for worktree add/remove)
    - Runtime: expect this to run for a long time (40 sequential passes by
      default); the script checkpoints progress to --checkpoint-file (default
      under meta/plans/implementation-logs/, gitignored) after every pass and
      resumes with --resume instead of restarting completed passes. It also
      aborts (checkpoint intact) if cumulative spend crosses --max-cost-usd.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DEFAULT_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
DEFAULT_CHECKPOINT_PATH = (
    Path(__file__).resolve().parent.parent
    / "meta"
    / "plans"
    / "implementation-logs"
    / "wenyan_validation_checkpoint.json"
)
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parent.parent / "meta" / "wenyan-handoff-validation-report.md"
)

REQUIRED_CROSS_REPO = "bible-flashcards"

_SECRET_PATTERNS = [
    # Authorization header: consume the whole value (optional scheme + token),
    # not just the first whitespace-delimited word — otherwise a scheme prefix
    # like "Bearer" gets redacted while the token after it leaks untouched.
    re.compile(r"(?i)authorization\s*:\s*(?:\S+\s+)?\S+"),
    re.compile(r"(?i)\bbearer\s+\S+"),
    re.compile(r"(?i)\b(?:sk|ghp|gho|ghu|ghs|ghr|xox[baprs]|AKIA)[A-Za-z0-9_-]{6,}\b"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
]


class PipelineError(RuntimeError):
    """Raised when a baseline or wenyan-ultra pipeline pass fails."""


class CostCeilingExceeded(RuntimeError):
    """Raised when cumulative spend crosses --max-cost-usd; run should abort but checkpoint stays valid."""


def check_cost_ceiling(cumulative_cost_usd, max_cost_usd):
    if cumulative_cost_usd > max_cost_usd:
        raise CostCeilingExceeded(
            f"cumulative spend ${cumulative_cost_usd:.2f} exceeds ceiling ${max_cost_usd:.2f} "
            "— checkpoint saved, resume with --resume after raising --max-cost-usd or reviewing spend"
        )


# --- Redaction -------------------------------------------------------------


def redact_secrets(text):
    """Replace secret/PII-shaped substrings with REDACTED. Never reproduce verbatim."""
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub("REDACTED", result)
    return result


def _redact_value(value):
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


# --- PR corpus selection ----------------------------------------------------


def select_pr_corpus(candidates, corpus_size=5, required_repo=REQUIRED_CROSS_REPO):
    """Select `corpus_size` PRs, requiring at least one from `required_repo`.

    Prefers candidates with recorded sdlc findings (drift ground truth).
    Each returned PR gets a `rationale` string describing why it was chosen.
    """
    required_candidates = [c for c in candidates if c["repo"] == required_repo]
    if not required_candidates:
        raise ValueError(
            f"no candidate from required repo '{required_repo}' — corpus must "
            f"include at least one {required_repo} PR"
        )
    if len(candidates) < corpus_size:
        raise ValueError(
            f"not enough candidates ({len(candidates)}) to fill a corpus of {corpus_size}"
        )

    # Guarantee the required cross-repo slot first (preferring one with
    # recorded findings as ground truth), then fill the rest by preference.
    required_pick = next(
        (c for c in required_candidates if c.get("has_recorded_findings")),
        required_candidates[0],
    )
    remaining_pool = [c for c in candidates if c is not required_pick]
    recorded = [c for c in remaining_pool if c.get("has_recorded_findings")]
    rest = [c for c in remaining_pool if not c.get("has_recorded_findings")]
    selected = [required_pick] + (recorded + rest)[: corpus_size - 1]

    corpus = []
    for c in selected[:corpus_size]:
        rationale = (
            f"{c['size_type']}"
            + (", prior recorded sdlc findings used as drift ground truth" if c.get("has_recorded_findings") else "")
            + (f", required cross-repo ({required_repo}) sample" if c["repo"] == required_repo else "")
        )
        corpus.append({**c, "rationale": rationale})
    return corpus


# --- Drift computation -------------------------------------------------------


def compute_drift(baseline_findings, wenyan_findings):
    """Diff findings between two runs of the same PR. Ship bar is 0 mismatches.

    Within each file, findings are paired by matching `substance` (greedily,
    first-available), not by list position — two runs can legitimately return
    the same findings in a different order (LLM output order isn't stable
    across independent invocations), and that must not count as drift. A
    substance match whose `line` differs is reported as one "changed"
    mismatch; a substance with no match on the other side is missing/added.
    """
    by_file_baseline = {}
    for f in baseline_findings:
        by_file_baseline.setdefault(f["file"], []).append(f)
    by_file_wenyan = {}
    for f in wenyan_findings:
        by_file_wenyan.setdefault(f["file"], []).append(f)

    mismatches = []
    for file in sorted(set(by_file_baseline) | set(by_file_wenyan)):
        base_list = by_file_baseline.get(file, [])
        wenyan_list = list(by_file_wenyan.get(file, []))
        matched_wenyan_idx = set()

        for base in base_list:
            match_idx = next(
                (
                    idx
                    for idx, w in enumerate(wenyan_list)
                    if idx not in matched_wenyan_idx and w["substance"] == base["substance"]
                ),
                None,
            )
            if match_idx is None:
                mismatches.append({"kind": "missing_in_wenyan", "finding": base})
                continue
            matched_wenyan_idx.add(match_idx)
            wenyan = wenyan_list[match_idx]
            if wenyan["line"] != base["line"]:
                mismatches.append({"kind": "changed", "baseline": base, "wenyan": wenyan})

        for idx, wenyan in enumerate(wenyan_list):
            if idx not in matched_wenyan_idx:
                mismatches.append({"kind": "added_in_wenyan", "finding": wenyan})

    return {"mismatches": mismatches, "ship": len(mismatches) == 0}


def evaluate_corpus_verdict(per_pr_drift):
    """Ship/no-ship gate: every PR must independently have 0 drift (never averaged)."""
    failed = sorted(pr for pr, result in per_pr_drift.items() if not result["ship"])
    return {"ship": len(failed) == 0, "failed_prs": failed}


# --- Checkpoint / resume -----------------------------------------------------


def load_checkpoint(path):
    path = Path(path)
    if not path.exists():
        return {"passes": {}}
    return json.loads(path.read_text())


def save_checkpoint(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    redacted = _redact_value(state)
    path.write_text(json.dumps(redacted, indent=2, sort_keys=True))


def mark_pass_complete(state, pr_key, mode, rep, metrics):
    state.setdefault("passes", {}).setdefault(pr_key, {}).setdefault(mode, {})[str(rep)] = metrics


def is_pass_complete(state, pr_key, mode, rep):
    return str(rep) in state.get("passes", {}).get(pr_key, {}).get(mode, {})


@contextmanager
def session_start_hook_disabled(settings_path=DEFAULT_CLAUDE_SETTINGS):
    """Temporarily strip the SessionStart hook block from settings.json.

    This is the actual source of the always-on caveman-mode session context
    (unrelated to the /caveman line in CLAUDE.md) — it must be neutralized for
    the whole experiment so orchestrator-level chat style doesn't confound the
    SDLC handoff-protocol comparison. Always restores the original file
    byte-for-byte, including when the wrapped pass raises partway through.
    """
    settings_path = Path(settings_path)
    original = settings_path.read_text()
    try:
        data = json.loads(original)
        if "SessionStart" in data.get("hooks", {}):
            del data["hooks"]["SessionStart"]
            if not data["hooks"]:
                del data["hooks"]
            settings_path.write_text(json.dumps(data, indent=2))
        yield
    finally:
        settings_path.write_text(original)


DEFAULT_WORKTREE_PARENT = (
    Path(__file__).resolve().parent.parent / "meta" / "plans" / "implementation-logs" / "wenyan-worktrees"
)


@contextmanager
def baseline_worktree(
    repo_root,
    baseline_skill_content,
    worktree_parent=DEFAULT_WORKTREE_PARENT,
    runner=subprocess.run,
):
    """Check out a disposable git worktree and swap in the plain-prose baseline SKILL.md.

    The real repo checkout is never mutated — baseline passes run entirely
    against files inside this worktree, which is deleted on exit (including
    on exception) via `git worktree remove`.
    """
    repo_root = Path(repo_root)
    worktree_parent = Path(worktree_parent)
    worktree_parent.mkdir(parents=True, exist_ok=True)
    worktree_path = worktree_parent / f"baseline-{uuid.uuid4()}"

    runner(
        ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(worktree_path), "HEAD"],
        capture_output=True,
        text=True,
    )
    try:
        skill_path = worktree_path / "skills" / "sdlc" / "SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(baseline_skill_content)
        yield worktree_path
    finally:
        runner(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(worktree_path)],
            capture_output=True,
            text=True,
        )


# --- Pipeline pass invocation -------------------------------------------------

_FINDING_LINE_RE = re.compile(r"^FINDING:\s*(?P<file>\S+):(?P<line>\d+)\s+(?P<substance>.+)$")


def _parse_findings(stdout):
    findings = []
    for line in stdout.splitlines():
        m = _FINDING_LINE_RE.match(line.strip())
        if m:
            findings.append(
                {"file": m.group("file"), "line": int(m.group("line")), "substance": m.group("substance")}
            )
    return findings


def _parse_pr_ref(ref):
    repo, sep, num = ref.partition("#")
    if not sep or not repo or not num.isdigit():
        raise ValueError(f"invalid PR reference '{ref}', expected REPO#NUM")
    return {"repo": repo, "number": int(num)}


def run_pipeline_pass(pr, mode, runner=subprocess.run, cwd=None):
    """Run the full sdlc review pipeline once for `pr` in `mode` ('baseline' | 'wenyan').

    Never interpolates PR title/branch strings into a shell string — always
    invokes via an argument array. `runner` is injectable for testing.
    """
    args = [
        "claude",
        "-p",
        "--output-format",
        "json",
        f"/sdlc review {pr['repo']}#{pr['number']}",
    ]
    start = time.monotonic()
    result = runner(args, capture_output=True, text=True, cwd=cwd)
    latency_s = time.monotonic() - start

    if getattr(result, "returncode", 0) != 0:
        raise PipelineError(
            f"pipeline pass failed for {pr['repo']}#{pr['number']} ({mode}): "
            f"exit {result.returncode}"
        )

    stdout = getattr(result, "stdout", "") or ""
    payload = json.loads(stdout)
    usage = payload.get("usage", {})
    return {
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
        "total_cost_usd": payload.get("total_cost_usd", 0.0),
        "latency_s": round(latency_s, 3),
        "findings": _parse_findings(payload.get("result", "")),
    }


# --- Cost/token analysis -------------------------------------------------------


def sign_test(deltas):
    """Two-sided exact sign test on a list of paired deltas (stdlib-only, no scipy).

    Zero deltas are dropped (standard sign-test convention — a tie carries no
    directional evidence). p-value = 2 * P(X <= min(n_pos, n_neg)) for
    X ~ Binomial(n, 0.5), capped at 1.0.
    """
    nonzero = [d for d in deltas if d != 0]
    n = len(nonzero)
    n_positive = sum(1 for d in nonzero if d > 0)
    n_negative = n - n_positive
    if n == 0:
        return {"n": 0, "n_positive": 0, "n_negative": 0, "p_value": 1.0}
    k = min(n_positive, n_negative)
    p_value = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2**n))
    return {"n": n, "n_positive": n_positive, "n_negative": n_negative, "p_value": p_value}


def per_pr_cost_deltas(per_pr_metrics):
    """Per-PR mean(wenyan reps) vs mean(baseline reps) cost, absolute and ratio."""
    deltas = []
    for pr_key, by_mode in per_pr_metrics.items():
        baseline_costs = [m["total_cost_usd"] for m in by_mode.get("baseline", {}).values()]
        wenyan_costs = [m["total_cost_usd"] for m in by_mode.get("wenyan", {}).values()]
        if not baseline_costs or not wenyan_costs:
            continue
        baseline_mean = statistics.mean(baseline_costs)
        wenyan_mean = statistics.mean(wenyan_costs)
        deltas.append(
            {
                "pr": pr_key,
                "baseline_mean_usd": baseline_mean,
                "wenyan_mean_usd": wenyan_mean,
                "delta_usd": wenyan_mean - baseline_mean,
                "ratio": wenyan_mean / baseline_mean if baseline_mean else float("inf"),
            }
        )
    return deltas


def noise_floor(per_pr_metrics):
    """Within-condition (same PR, same mode, across reps) stdev of cost — the noise baseline."""
    floor = {}
    for pr_key, by_mode in per_pr_metrics.items():
        floor[pr_key] = {}
        for mode, by_rep in by_mode.items():
            costs = [m["total_cost_usd"] for m in by_rep.values()]
            floor[pr_key][mode] = statistics.pstdev(costs) if len(costs) > 1 else 0.0
    return floor


_CSV_FIELDS = [
    "pr",
    "mode",
    "rep",
    "total_cost_usd",
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "latency_s",
]


def write_csv(per_pr_metrics, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for pr_key, by_mode in per_pr_metrics.items():
            for mode, by_rep in by_mode.items():
                for rep, metrics in by_rep.items():
                    usage = metrics.get("usage", {})
                    writer.writerow(
                        {
                            "pr": pr_key,
                            "mode": mode,
                            "rep": rep,
                            "total_cost_usd": metrics.get("total_cost_usd", ""),
                            "input_tokens": usage.get("input_tokens", ""),
                            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", ""),
                            "cache_read_input_tokens": usage.get("cache_read_input_tokens", ""),
                            "output_tokens": usage.get("output_tokens", ""),
                            "latency_s": metrics.get("latency_s", ""),
                        }
                    )
    return path


# --- Report generation --------------------------------------------------------


def generate_report(corpus, per_pr_metrics, per_pr_drift, verdict, path=DEFAULT_REPORT_PATH, reps=1):
    path = Path(path)
    lines = [
        "# wenyan-ultra handoff validation report",
        "",
        f"Cost/token/latency/drift comparison of baseline (plain-prose Phase 3/4) vs. "
        f"wenyan-ultra-enabled sdlc review runs across a {len(corpus)}-PR corpus "
        "(claude-tools + bible-flashcards, both public repos), each (PR, mode) pair "
        f"run {reps}x to estimate run-to-run noise. Baseline runs execute against a "
        "disposable git worktree with a plain-prose Phase 3/4 SKILL.md variant — the "
        "real repo checkout is never mutated. Metrics are real billed API usage "
        "(`--output-format json`), not a word count. No raw diff content or "
        "PII/secret values are reproduced below.",
        "",
        "---",
        "",
        "## PR corpus",
        "",
    ]
    for pr in corpus:
        lines.append(f"- `{pr['repo']}#{pr['number']}` — {pr['rationale']}")
    lines += ["", "---", "", "## Per-PR results", ""]
    for pr in corpus:
        key = f"{pr['repo']}#{pr['number']}"
        metrics = per_pr_metrics.get(key, {})
        drift = per_pr_drift.get(key, {})
        lines.append(f"### `{key}`")
        lines.append("")
        for mode in ("baseline", "wenyan"):
            by_rep = metrics.get(mode, {})
            for rep in sorted(by_rep):
                m = by_rep[rep]
                usage = m.get("usage", {})
                lines.append(
                    f"- {mode} rep {rep}: cost_usd={m.get('total_cost_usd', 'n/a')}, "
                    f"input={usage.get('input_tokens', 'n/a')}, "
                    f"cache_read={usage.get('cache_read_input_tokens', 'n/a')}, "
                    f"cache_write={usage.get('cache_creation_input_tokens', 'n/a')}, "
                    f"output={usage.get('output_tokens', 'n/a')}, "
                    f"latency_s={m.get('latency_s', 'n/a')}"
                )
        lines.append(f"- drift mismatches: {len(drift.get('mismatches', []))}")
        lines.append(f"- ship (this PR independently): {drift.get('ship')}")
        lines.append("")
    lines += ["---", "", "## Cost & Token Analysis", ""]
    deltas = per_pr_cost_deltas(per_pr_metrics)
    floor = noise_floor(per_pr_metrics)
    for d in deltas:
        pr_floor = floor.get(d["pr"], {})
        lines.append(
            f"- `{d['pr']}`: baseline_mean=${d['baseline_mean_usd']:.4f}, "
            f"wenyan_mean=${d['wenyan_mean_usd']:.4f}, ratio={d['ratio']:.2f}, "
            f"noise_floor(stdev)_baseline=${pr_floor.get('baseline', 0):.4f}, "
            f"noise_floor(stdev)_wenyan=${pr_floor.get('wenyan', 0):.4f}"
        )
    test_result = sign_test([d["delta_usd"] for d in deltas])
    lines += [
        "",
        f"**Sign test** on the {test_result['n']} paired per-PR cost deltas "
        f"(wenyan vs. baseline, ties dropped): {test_result['n_positive']} PRs more "
        f"expensive under wenyan, {test_result['n_negative']} cheaper, "
        f"two-sided p={test_result['p_value']:.4f}.",
        "",
    ]
    lines += [
        "---",
        "",
        "## Verdict",
        "",
        f"**{'SHIP' if verdict['ship'] else 'NO-SHIP'}** — bar is 0 substantive drift "
        "mismatches on every PR independently (not corpus-averaged).",
    ]
    if verdict["failed_prs"]:
        lines.append("")
        lines.append("Failed PRs: " + ", ".join(verdict["failed_prs"]))
    lines += [
        "",
        "---",
        "",
        "## Privacy note",
        "",
        "Sourced from claude-tools and bible-flashcards (both public). No "
        "third-party production user data is reproduced verbatim in this report; "
        "any secret- or PII-shaped string surfaced during either run was redacted.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path


# --- Default 10-PR corpus (stratified by size, 5/5 repo split, excludes the ---
# --- wenyan-implementing PR itself and anything over ~800 changed lines)    ---

DEFAULT_CORPUS = [
    {"repo": "claude-tools", "number": 14, "rationale": "small"},
    {"repo": "claude-tools", "number": 15, "rationale": "small"},
    {"repo": "bible-flashcards", "number": 52, "rationale": "small"},
    {"repo": "bible-flashcards", "number": 57, "rationale": "small"},
    {"repo": "claude-tools", "number": 12, "rationale": "medium"},
    {"repo": "bible-flashcards", "number": 62, "rationale": "medium"},
    {"repo": "bible-flashcards", "number": 33, "rationale": "medium"},
    {"repo": "claude-tools", "number": 7, "rationale": "large"},
    {"repo": "claude-tools", "number": 8, "rationale": "large"},
    {"repo": "bible-flashcards", "number": 35, "rationale": "large"},
]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = DEFAULT_REPORT_PATH.with_suffix(".csv")


# --- run_experiment: full orchestration -----------------------------------------


def _cumulative_cost(state):
    return sum(
        rep_metrics.get("total_cost_usd", 0.0)
        for by_mode in state.get("passes", {}).values()
        for by_rep in by_mode.values()
        for rep_metrics in by_rep.values()
    )


def run_experiment(
    corpus,
    reps,
    checkpoint_path,
    report_path,
    csv_path,
    baseline_skill_content,
    repo_root=DEFAULT_REPO_ROOT,
    worktree_parent=DEFAULT_WORKTREE_PARENT,
    claude_settings=DEFAULT_CLAUDE_SETTINGS,
    max_cost_usd=30.0,
    resume=False,
    pipeline_runner=subprocess.run,
    worktree_runner=subprocess.run,
):
    """Run the full baseline-vs-wenyan cost/token/drift experiment.

    Sequential, one pass at a time (never parallel — a parallel-in-flight batch
    could blow past `max_cost_usd` before the ceiling check fires). Every
    completed pass is checkpointed immediately, so a CostCeilingExceeded abort
    (or any crash) leaves a resumable state. The SessionStart caveman-mode hook
    is disabled for the whole run so it can't confound the orchestrator-level
    token counts; it's always restored, including on abort.
    """
    checkpoint_path = Path(checkpoint_path)
    state = load_checkpoint(checkpoint_path) if resume else {"passes": {}}
    cumulative_cost = _cumulative_cost(state)

    with session_start_hook_disabled(claude_settings):
        for pr in corpus:
            key = f"{pr['repo']}#{pr['number']}"
            for mode in ("baseline", "wenyan"):
                for rep in range(1, reps + 1):
                    if is_pass_complete(state, key, mode, rep):
                        continue
                    if mode == "baseline":
                        with baseline_worktree(
                            repo_root=repo_root,
                            baseline_skill_content=baseline_skill_content,
                            worktree_parent=worktree_parent,
                            runner=worktree_runner,
                        ) as worktree_path:
                            metrics = run_pipeline_pass(
                                pr, mode, runner=pipeline_runner, cwd=worktree_path
                            )
                    else:
                        metrics = run_pipeline_pass(pr, mode, runner=pipeline_runner, cwd=repo_root)

                    mark_pass_complete(state, key, mode, rep, metrics)
                    save_checkpoint(checkpoint_path, state)
                    cumulative_cost += metrics.get("total_cost_usd", 0.0)
                    check_cost_ceiling(cumulative_cost, max_cost_usd)

    per_pr_metrics = state["passes"]
    per_pr_drift = {}
    for pr in corpus:
        key = f"{pr['repo']}#{pr['number']}"
        baseline_findings = per_pr_metrics.get(key, {}).get("baseline", {}).get("1", {}).get("findings", [])
        wenyan_findings = per_pr_metrics.get(key, {}).get("wenyan", {}).get("1", {}).get("findings", [])
        per_pr_drift[key] = compute_drift(baseline_findings, wenyan_findings)

    verdict = evaluate_corpus_verdict(per_pr_drift)
    generate_report(corpus, per_pr_metrics, per_pr_drift, verdict, path=report_path, reps=reps)
    write_csv(per_pr_metrics, csv_path)

    return {
        "cumulative_cost_usd": cumulative_cost,
        "verdict": verdict,
    }


# --- CLI ----------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prs",
        nargs="*",
        default=None,
        help="Explicit PR corpus as REPO#NUM (e.g. claude-tools#28), overrides the default 10-PR corpus",
    )
    parser.add_argument("--reps", type=int, default=2, help="Runs per (PR, mode) pair (default: 2)")
    parser.add_argument("--max-cost-usd", type=float, default=30.0, help="Abort ceiling on cumulative spend")
    parser.add_argument("--resume", action="store_true", help="Resume from the checkpoint file")
    parser.add_argument("--checkpoint-file", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--report-file", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--csv-file", default=str(DEFAULT_CSV_PATH))
    parser.add_argument("--claude-settings", default=str(DEFAULT_CLAUDE_SETTINGS))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument(
        "--baseline-skill-file",
        default=str(DEFAULT_REPO_ROOT / "scripts" / "fixtures" / "sdlc_skill_baseline_variant.md"),
        help="Plain-prose Phase 3/4 SKILL.md variant used for baseline passes",
    )
    args = parser.parse_args(argv)

    if args.prs:
        corpus = [{**_parse_pr_ref(ref), "rationale": "user-specified via --prs"} for ref in args.prs]
        if not any(pr["repo"] == REQUIRED_CROSS_REPO for pr in corpus):
            parser.error(f"corpus must include at least one {REQUIRED_CROSS_REPO} PR")
    else:
        corpus = DEFAULT_CORPUS

    baseline_skill_content = Path(args.baseline_skill_file).read_text()

    try:
        summary = run_experiment(
            corpus=corpus,
            reps=args.reps,
            checkpoint_path=Path(args.checkpoint_file),
            report_path=Path(args.report_file),
            csv_path=Path(args.csv_file),
            baseline_skill_content=baseline_skill_content,
            repo_root=Path(args.repo_root),
            claude_settings=Path(args.claude_settings),
            max_cost_usd=args.max_cost_usd,
            resume=args.resume,
        )
    except CostCeilingExceeded as exc:
        print(f"ABORTED: {exc}")
        return 2

    print(
        f"Report written to {args.report_file}, raw data to {args.csv_file}. "
        f"Cumulative spend: ${summary['cumulative_cost_usd']:.2f}. "
        f"Verdict: {'SHIP' if summary['verdict']['ship'] else 'NO-SHIP'}"
    )
    return 0 if summary["verdict"]["ship"] else 1


if __name__ == "__main__":
    main()
