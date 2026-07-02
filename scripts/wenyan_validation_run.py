#!/usr/bin/env python3
"""Offline validation runner for the wenyan-ultra sdlc-review handoff protocol.

Produces a ship/no-ship recommendation by running the full sdlc review
pipeline twice (baseline vs. wenyan-ultra-enabled) across a 5-PR corpus
(claude-tools + bible-flashcards) and diffing findings for drift.

This script is standalone and is not invoked by any plan/test in this repo
during normal CI — it makes real `gh`/`claude` subprocess calls, temporarily
edits the user's global ~/.claude/CLAUDE.md, and costs real time/tokens
(~80 sub-agent invocations for a 5-PR x 2-mode x 8-agent run).

Usage:
    python3 scripts/wenyan_validation_run.py [--prs REPO#NUM ...] [--resume]

Requirements:
    - `gh` authenticated read access to both claude-tools and bible-flashcards
      (read-only; this script never posts comments/labels back to either repo)
    - `claude` CLI on PATH
    - Runtime: expect on the order of hours for the full 5-PR x 2-mode run;
      the script checkpoints progress to --checkpoint-file (default under
      meta/plans/implementation-logs/, gitignored) and resumes with --resume
      instead of restarting completed passes.
    - Temporarily disables the global `/caveman` directive in
      ~/.claude/CLAUDE.md during baseline passes and always restores it
      afterward, including on error/interrupt.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_CLAUDE_CONFIG = Path.home() / ".claude" / "CLAUDE.md"
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


def mark_pass_complete(state, pr_key, mode, metrics):
    state.setdefault("passes", {}).setdefault(pr_key, {})[mode] = metrics


def is_pass_complete(state, pr_key, mode):
    return mode in state.get("passes", {}).get(pr_key, {})


# --- /caveman directive disable/restore --------------------------------------

_CAVEMAN_LINE_RE = re.compile(r"^[ \t]*/caveman[ \t]*\n?", re.MULTILINE)


@contextmanager
def caveman_directive_disabled(config_path=DEFAULT_CLAUDE_CONFIG):
    """Temporarily strip the /caveman directive from the global CLAUDE.md.

    Always restores the original file content, including when the wrapped
    pass raises partway through — the global config must never be left
    modified by an interrupted run.
    """
    config_path = Path(config_path)
    original = config_path.read_text()
    try:
        stripped = _CAVEMAN_LINE_RE.sub("", original)
        if stripped != original:
            config_path.write_text(stripped)
        yield
    finally:
        config_path.write_text(original)


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


def run_pipeline_pass(pr, mode, runner=subprocess.run):
    """Run the full sdlc review pipeline once for `pr` in `mode` ('baseline' | 'wenyan').

    Never interpolates PR title/branch strings into a shell string — always
    invokes via an argument array. `runner` is injectable for testing.
    """
    args = [
        "claude",
        "-p",
        "--output-format",
        "text",
        f"/sdlc review {pr['repo']}#{pr['number']}",
    ]
    start = time.monotonic()
    result = runner(args, capture_output=True, text=True)
    latency_s = time.monotonic() - start

    if getattr(result, "returncode", 0) != 0:
        raise PipelineError(
            f"pipeline pass failed for {pr['repo']}#{pr['number']} ({mode}): "
            f"exit {result.returncode}"
        )

    stdout = getattr(result, "stdout", "") or ""
    return {
        "tokens": len(stdout.split()),
        "latency_s": round(latency_s, 3),
        "findings": _parse_findings(stdout),
    }


# --- Report generation --------------------------------------------------------


def generate_report(corpus, per_pr_metrics, per_pr_drift, verdict, path=DEFAULT_REPORT_PATH):
    path = Path(path)
    lines = [
        "# wenyan-ultra handoff validation report",
        "",
        "Token/latency/drift comparison of baseline vs. wenyan-ultra-enabled sdlc "
        "review runs across a 5-PR corpus (claude-tools + bible-flashcards, both "
        "public repos). No raw diff content or PII/secret values are reproduced "
        "below — findings are summarized by category/count and referenced by "
        "PR number/URL/commit SHA only.",
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
            m = metrics.get(mode, {})
            lines.append(f"- {mode}: tokens={m.get('tokens', 'n/a')}, latency_s={m.get('latency_s', 'n/a')}")
        lines.append(f"- drift mismatches: {len(drift.get('mismatches', []))}")
        lines.append(f"- ship (this PR independently): {drift.get('ship')}")
        lines.append("")
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


# --- CLI ----------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prs",
        nargs="*",
        default=None,
        help="Explicit PR corpus as REPO#NUM (e.g. claude-tools#28), overrides auto-selection",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from the checkpoint file")
    parser.add_argument("--checkpoint-file", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--report-file", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--claude-config", default=str(DEFAULT_CLAUDE_CONFIG))
    args = parser.parse_args(argv)

    if not args.prs:
        parser.error(
            "no PR corpus given — pass --prs REPO#NUM ... (5 PRs, at least one "
            f"{REQUIRED_CROSS_REPO} PR) to run a live validation pass. Automatic "
            "corpus selection from `gh` requires an authenticated, human-run "
            "invocation and is intentionally not wired to run unattended."
        )

    corpus = [
        {**_parse_pr_ref(ref), "rationale": "user-specified via --prs"} for ref in args.prs
    ]
    if not any(pr["repo"] == REQUIRED_CROSS_REPO for pr in corpus):
        parser.error(f"corpus must include at least one {REQUIRED_CROSS_REPO} PR")

    checkpoint_path = Path(args.checkpoint_file)
    state = load_checkpoint(checkpoint_path) if args.resume else {"passes": {}}

    per_pr_metrics = {}
    for pr in corpus:
        key = f"{pr['repo']}#{pr['number']}"
        per_pr_metrics[key] = {}
        for mode in ("baseline", "wenyan"):
            if is_pass_complete(state, key, mode):
                per_pr_metrics[key][mode] = state["passes"][key][mode]
                continue
            if mode == "baseline":
                with caveman_directive_disabled(Path(args.claude_config)):
                    metrics = run_pipeline_pass(pr, mode)
            else:
                metrics = run_pipeline_pass(pr, mode)
            mark_pass_complete(state, key, mode, metrics)
            save_checkpoint(checkpoint_path, state)
            per_pr_metrics[key][mode] = metrics

    per_pr_drift = {}
    for pr in corpus:
        key = f"{pr['repo']}#{pr['number']}"
        baseline_findings = per_pr_metrics[key]["baseline"].get("findings", [])
        wenyan_findings = per_pr_metrics[key]["wenyan"].get("findings", [])
        per_pr_drift[key] = compute_drift(baseline_findings, wenyan_findings)

    verdict = evaluate_corpus_verdict(per_pr_drift)
    report_path = generate_report(
        corpus, per_pr_metrics, per_pr_drift, verdict, path=Path(args.report_file)
    )
    print(f"Report written to {report_path}. Verdict: {'SHIP' if verdict['ship'] else 'NO-SHIP'}")
    return 0 if verdict["ship"] else 1


if __name__ == "__main__":
    main()
