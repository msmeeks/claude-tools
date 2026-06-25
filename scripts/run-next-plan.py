#!/usr/bin/env python3
"""
Partner to /triage-issues and /triage-pr-comments. Finds the next unfinished plan in
meta/plans/README.md and runs a non-interactive Claude session to implement it.

Usage (run from inside any git repo with meta/plans/):
    python3 ~/.claude/scripts/run-next-plan.py [options]

Options:
    --restart           Reset in-progress plan to pending and re-run
    --skip-in-progress  Skip in-progress plan; pick next pending
    --dry-run           Print selected plan and prompt; do not invoke Claude
    --issues            Only run issue workstream plans (skip PR-comment plans)
    --pr-comments       Only run PR comment response plans (skip issue plans)
                        Default (neither flag): run both, PR-comment plans first
    --integration-branch BRANCH
                        Shared branch all plan PRs in this batch target and merge into.
                        Created from the default branch if missing. Default: integration/batch
                        Each plan branches off the latest integration branch (pulled before
                        every plan), merges back into it on QA pass, then its PR branch and
                        worktree are deleted. Merge conflicts are resolved per-PR as needed.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import IO

MAX_RETRIES = 20
RETRY_WAIT_DEFAULT = 60

PR_COMMENT_PLAN_RE = re.compile(r"^pr-\d+-comments\.md$")

RATE_LIMIT_RE = re.compile(
    r"session.?limit|rate.?limit|usage.?limit|too many requests|overloaded|429|quota.?exceed|slowdown",
    re.IGNORECASE,
)

_log_fh: "IO[str] | None" = None


def _log(line: str) -> None:
    if _log_fh is not None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _log_fh.write(f"[{ts}] {line}\n")
        _log_fh.flush()


def is_pr_comment_plan(filename: str) -> bool:
    return bool(PR_COMMENT_PLAN_RE.match(filename))


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    _log(f"ERROR: {msg}")
    sys.exit(1)


def info(msg: str) -> None:
    print(f"==> {msg}")
    _log(f"==> {msg}")


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)
    _log(f"WARN: {msg}")


def bootstrap_readme(readme: Path) -> None:
    text = readme.read_text()
    if re.search(r"^\| Plan.*Status", text, re.MULTILINE):
        return
    info("Bootstrapping Status column in README.md...")
    lines = []
    for line in text.splitlines(keepends=True):
        if re.match(r"^\| Plan.*\| Size \|", line):
            lines.append(line.rstrip("\n") + " Status |\n")
        elif re.match(r"^\|[-]+\|[-]+\|[-]+\|[-]+\|\s*$", line):
            lines.append(line.rstrip("\n") + "--------|\n")
        elif re.match(r"^\| \[", line):
            lines.append(re.sub(r" \|\s*$", " | pending |", line.rstrip("\n")) + "\n")
        else:
            lines.append(line)
    readme.write_text("".join(lines))


def bootstrap_plan_file(planfile: Path) -> None:
    text = planfile.read_text()
    if re.search(r"^\*\*Status\*\*:", text, re.MULTILINE):
        return
    lines = []
    for line in text.splitlines(keepends=True):
        lines.append(line)
        if re.match(r"^\*\*Base:\*\*", line):
            lines.append("**Status:** pending\n")
    planfile.write_text("".join(lines))


def get_plan_status(planfile: Path) -> str:
    for line in planfile.read_text().splitlines():
        m = re.match(r"^\*\*Status\*\*:\s*(\S+)", line)
        if m:
            return m.group(1)
    return "pending"


def set_plan_status(planfile: Path, status: str) -> None:
    text = planfile.read_text()
    text = re.sub(r"^\*\*Status\*\*:.*", f"**Status:** {status}", text, flags=re.MULTILINE)
    planfile.write_text(text)


def set_readme_status(readme: Path, plan_filename: str, new_status: str) -> None:
    escaped = re.escape(plan_filename)

    def replacer(m: re.Match) -> str:
        row = m.group(0)
        row = re.sub(r"\| pending \|$", f"| {new_status} |", row)
        row = re.sub(r"\| in-progress \|$", f"| {new_status} |", row)
        row = re.sub(r"\| done \|$", f"| {new_status} |", row)
        return row

    text = re.sub(rf"^.*\({escaped}\).*$", replacer, readme.read_text(), flags=re.MULTILINE)
    readme.write_text(text)


def get_plan_branch(planfile: Path) -> str:
    for line in planfile.read_text().splitlines():
        m = re.match(r"^\*\*Branch:\*\*\s*`([^`]+)`", line)
        if m:
            return m.group(1)
    return ""


def list_plan_files(
    readme: Path, exclude_done: bool = False, kind: str = "both"
) -> list[str]:
    all_files = []
    for line in readme.read_text().splitlines():
        if not re.match(r"^\| \[", line):
            continue
        if exclude_done and "| done |" in line:
            continue
        m = re.search(r"\(([^)]*\.md)\)", line)
        if m:
            all_files.append(m.group(1))

    if kind == "pr-comments":
        return [f for f in all_files if is_pr_comment_plan(f)]
    if kind == "issues":
        return [f for f in all_files if not is_pr_comment_plan(f)]
    # "both": PR-comment plans first (unblock review cycles), then issue plans
    pr = [f for f in all_files if is_pr_comment_plan(f)]
    issues = [f for f in all_files if not is_pr_comment_plan(f)]
    return pr + issues


def parse_reaction_metadata(planfile: Path) -> dict[str, list[str]]:
    """Parse <!-- reactions: rocket=ID,ID +1=ID --> from the plan file."""
    m = re.search(r"<!-- reactions: (.+?) -->", planfile.read_text())
    if not m:
        return {}
    result: dict[str, list[str]] = {}
    for part in m.group(1).split():
        key, _, raw_ids = part.partition("=")
        if raw_ids:
            result[key] = [i.strip() for i in raw_ids.split(",") if i.strip()]
    return result


def get_default_branch() -> str:
    r = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return r.stdout.strip().rsplit("/", 1)[-1]
    return "main"


def ensure_integration_branch(integration_branch: str) -> None:
    """Make sure the integration branch exists locally and on origin, and is up to date."""
    subprocess.run(["git", "fetch", "origin"], check=False)

    remote_exists = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/remotes/origin/{integration_branch}"],
        capture_output=True,
    ).returncode == 0
    local_exists = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{integration_branch}"],
        capture_output=True,
    ).returncode == 0

    if not remote_exists and not local_exists:
        default_branch = get_default_branch()
        info(f"Creating integration branch '{integration_branch}' from origin/{default_branch}")
        subprocess.run(
            ["git", "branch", integration_branch, f"origin/{default_branch}"], check=True
        )
        subprocess.run(
            ["git", "push", "-u", "origin", integration_branch], check=True
        )
    elif not local_exists:
        info(f"Checking out existing remote integration branch '{integration_branch}'")
        subprocess.run(
            ["git", "branch", integration_branch, f"origin/{integration_branch}"], check=True
        )
    refresh_integration_branch(integration_branch)


def refresh_integration_branch(integration_branch: str) -> None:
    """Pull the latest integration branch into the main checkout (not a worktree)."""
    subprocess.run(["git", "fetch", "origin", integration_branch], check=False)
    current = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if current == integration_branch:
        subprocess.run(["git", "pull", "--ff-only", "origin", integration_branch], check=False)
    else:
        # Update the local ref without disturbing the current checkout.
        subprocess.run(
            [
                "git",
                "fetch",
                "origin",
                f"{integration_branch}:{integration_branch}",
            ],
            check=False,
        )


def get_repo_slug() -> str:
    r = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def post_reactions(planfile: Path, repo: str) -> None:
    reactions = parse_reaction_metadata(planfile)
    if not reactions:
        return
    for emoji, ids in reactions.items():
        for comment_id in ids:
            subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/pulls/comments/{comment_id}/reactions",
                    "-f",
                    f"content={emoji}",
                ],
                capture_output=True,
            )
            info(f"Reacted :{emoji}: to comment {comment_id}")


def _parse_retry_after_text(text: str) -> int:
    m = re.search(r"(?:retry[- ]after[: ]+(\d+)|try again in (\d+))", text, re.IGNORECASE)
    if m:
        return int(m.group(1) or m.group(2))

    m2 = re.search(r"resets (\d+:\d+(?:am|pm))", text, re.IGNORECASE)
    if m2:
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo("America/New_York")
            now = datetime.now(tz)
            reset_time = datetime.strptime(m2.group(1).upper(), "%I:%M%p")
            target = now.replace(
                hour=reset_time.hour, minute=reset_time.minute, second=0, microsecond=0
            )
            diff = int((target - now).total_seconds())
            if diff < 0:
                diff += 86400
            return diff
        except Exception:
            pass

    return RETRY_WAIT_DEFAULT


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run next unfinished plan in meta/plans/README.md"
    )
    parser.add_argument(
        "--restart", action="store_true", help="Reset in-progress plan to pending and re-run"
    )
    parser.add_argument(
        "--skip-in-progress", action="store_true", help="Skip in-progress plan; pick next pending"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print selected plan and prompt; do not invoke Claude",
    )
    kind_group = parser.add_mutually_exclusive_group()
    kind_group.add_argument(
        "--issues",
        dest="kind",
        action="store_const",
        const="issues",
        help="Only run issue workstream plans (skip PR-comment plans)",
    )
    kind_group.add_argument(
        "--pr-comments",
        dest="kind",
        action="store_const",
        const="pr-comments",
        help="Only run PR comment response plans (skip issue plans)",
    )
    parser.set_defaults(kind="both")
    parser.add_argument(
        "--integration-branch",
        default="integration/batch",
        help="Branch that all plan PRs in this batch target and merge into "
        "(created from the default branch if it doesn't exist). Default: integration/batch",
    )
    args = parser.parse_args()

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if result.returncode != 0:
        die("Not inside a git repository.")
    repo_root = Path(result.stdout.strip())

    plans_dir = repo_root / "meta" / "plans"
    readme = plans_dir / "README.md"
    logs_dir = plans_dir / "implementation-logs"

    if not plans_dir.is_dir():
        die(f"Plans directory not found: {plans_dir} (run /triage-issues or /triage-pr-comments first)")
    if not readme.is_file():
        die(f"README not found: {readme} (run /triage-issues or /triage-pr-comments first)")
    if not shutil.which("claude"):
        die("Required command not found: claude")

    os.chdir(repo_root)

    # Open the single per-invocation log file before anything else so info/warn/die tee into it.
    global _log_fh
    if not args.dry_run:
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y_%m_%d_T%H_%M_%S")
        log_file = logs_dir / f"run-next-plan-{timestamp}.log"
        _log_fh = open(log_file, "w")  # noqa: SIM115
        info(f"Log: {log_file}")

    integration_branch = args.integration_branch
    if not args.dry_run:
        ensure_integration_branch(integration_branch)
    info(f"Integration branch: {integration_branch}")

    bootstrap_readme(readme)
    for plan_file in list_plan_files(readme, kind=args.kind):
        local_path = plans_dir / plan_file
        if local_path.is_file():
            bootstrap_plan_file(local_path)
        else:
            warn(f"Plan file referenced in README not found: {plan_file}")

    while True:
        if not args.dry_run:
            info(f"Pulling latest from integration branch '{integration_branch}'...")
            refresh_integration_branch(integration_branch)

        selected_file = None
        selected_status = None

        for plan_file in list_plan_files(readme, exclude_done=True, kind=args.kind):
            planfile_path = plans_dir / plan_file
            if not planfile_path.is_file():
                warn(f"Skipping missing plan file: {plan_file}")
                continue

            status = get_plan_status(planfile_path)

            if status == "in-progress" and args.restart:
                info(f"Resetting in-progress plan to pending: {plan_file}")
                set_plan_status(planfile_path, "pending")
                set_readme_status(readme, plan_file, "pending")
                status = "pending"

            if status == "done":
                info(f"Skipping done: {plan_file}")
                continue
            elif status == "in-progress":
                if args.skip_in_progress:
                    info(f"Skipping in-progress: {plan_file}")
                    continue
                info(f"Resuming in-progress: {plan_file}")
                selected_file = plan_file
                selected_status = "in-progress"
                break
            else:
                info(f"Selected: {plan_file}")
                selected_file = plan_file
                selected_status = "pending"
                break

        if not selected_file:
            info("All plans done. Nothing to do.")
            sys.exit(0)

        plan_abs_path = plans_dir / selected_file
        branch = get_plan_branch(plan_abs_path)

        info(f"Plan:   {selected_file}")
        info(f"Branch: {branch}")

        set_plan_status(plan_abs_path, "in-progress")
        set_readme_status(readme, selected_file, "in-progress")

        if is_pr_comment_plan(selected_file):
            claude_prompt = f"""You are implementing a pre-written PR comment response plan as part of a
batch of plans that all target the shared integration branch `{integration_branch}`.

1. Read docs/llms.md for project context
2. Read the full plan file: meta/plans/{selected_file}
3. Check the plan's Worktree section — only run `git worktree add` if that path does not already exist.
   The worktree's branch must be based on the latest `{integration_branch}` (already pulled to
   latest in the repo root), NOT the plan's stated Base — fetch and reset/rebase onto
   `origin/{integration_branch}` if the existing branch is behind it.
4. All code changes must be made inside the worktree working directory
5. Execute ALL Implementation Steps in order. Use the /tdd skill to drive implementation
   (write failing test, implement, refactor). Do NOT run /sdlc reviews during implementation —
   they are skipped for this batch.
6. Post all Conversation Responses to GitHub review threads exactly as specified in the plan
7. Address every item in the Pre-Implementation Review section (security, privacy, a11y, design)
8. Push the branch and open (or update) the PR with `--base {integration_branch}` (not the plan's
   stated base). Resolve any merge conflicts against `{integration_branch}` before proceeding —
   fetch, merge/rebase, and fix conflicts as needed.
9. Run QA (automated tests, lint, smoke checks — use the /qa skill in its "after code changes"
   mode). If QA fails, fix the issues and re-run QA before continuing — do not merge a failing PR.
10. Once QA passes, merge the PR into `{integration_branch}` (e.g. `gh pr merge --squash`), then:
    - delete the remote PR branch (`git push origin --delete <branch>`)
    - remove the worktree (`git worktree remove <path>`)
11. After the merge and cleanup above succeed:
    - In meta/plans/{selected_file}: change '**Status:** in-progress' to '**Status:** done'
    - In meta/plans/README.md: change the Status cell for {selected_file} from 'in-progress' to 'done'

SUBAGENTS: When spawning any Agent or sub-claude invocation, include in its prompt:
"Use ultra-compressed caveman speech for all prose responses. Keep full technical accuracy."

Branch: {branch}
Integration branch: {integration_branch}
Repo root: {repo_root}"""
        else:
            claude_prompt = f"""You are implementing a pre-written, self-contained plan as part of a
batch of plans that all target the shared integration branch `{integration_branch}`.

1. Read docs/llms.md for project context
2. Read the full plan file: meta/plans/{selected_file}
3. Execute the plan's Worktree Setup section, but base the new branch on the latest
   `{integration_branch}` (already pulled to latest in the repo root) instead of the plan's
   stated Base — e.g. `git worktree add <path> -b {branch} {integration_branch}`.
4. All code changes must be made inside the worktree working directory
5. Execute ALL Implementation Steps in the plan, in order. Use the /tdd skill to drive
   implementation (write failing test, implement, refactor). Do NOT run /sdlc reviews during
   implementation — they are skipped for this batch.
6. Address every item in the Pre-Implementation Review section (security, privacy, a11y, design)
7. Push the branch and open the PR with `--base {integration_branch}` (not the plan's stated
   base). Resolve any merge conflicts against `{integration_branch}` before proceeding — fetch,
   merge/rebase, and fix conflicts as needed. Skip /sdlc; follow the rest of the plan's Review &
   Testing Workflow (Playwright, /pr-image-upload, etc.) as written.
8. Run QA (automated tests, lint, smoke checks — use the /qa skill in its "after code changes"
   mode). If QA fails, fix the issues and re-run QA before continuing — do not merge a failing PR.
9. Once QA passes, merge the PR into `{integration_branch}` (e.g. `gh pr merge --squash`), then:
   - delete the remote PR branch (`git push origin --delete {branch}`)
   - remove the worktree (`git worktree remove <path>`)
10. After the merge and cleanup above succeed:
    - In meta/plans/{selected_file}: change '**Status:** in-progress' to '**Status:** done'
    - In meta/plans/README.md: change the Status cell for {selected_file} from 'in-progress' to 'done'

SUBAGENTS: When spawning any Agent or sub-claude invocation, include in its prompt:
"Use ultra-compressed caveman speech for all prose responses. Keep full technical accuracy."

Branch: {branch}
Integration branch: {integration_branch}
Repo root: {repo_root}"""

        if args.dry_run:
            print()
            print("=== DRY RUN ===")
            print(f"Selected plan:       {selected_file}")
            print(f"Branch:              {branch}")
            print(f"Integration branch:  {integration_branch}")
            print()
            print("Command:")
            print("  claude -p <prompt> --permission-mode bypassPermissions --output-format text")
            print()
            print("=== PROMPT ===")
            print(claude_prompt)
            print("===============")
            set_plan_status(plan_abs_path, selected_status)
            set_readme_status(readme, selected_file, selected_status)
            sys.exit(0)

        info("Invoking Claude...")
        print()

        os.chdir(repo_root)

        impl_start = time.time()
        info(f"Implementation started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        attempt = 0
        claude_exit = 0
        while True:
            attempt += 1
            info(f"Claude session attempt {attempt} starting...")

            output_buf: list[str] = []
            proc = subprocess.Popen(
                [
                    "claude",
                    "-p",
                    claude_prompt,
                    "--permission-mode",
                    "bypassPermissions",
                    "--output-format",
                    "text",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
                if _log_fh is not None:
                    _log_fh.write(line)
                    _log_fh.flush()
                output_buf.append(line)
            proc.wait()
            claude_exit = proc.returncode
            output_text = "".join(output_buf)

            if claude_exit == 0:
                print()
                info(f"Session complete (attempt {attempt}).")
                if is_pr_comment_plan(selected_file):
                    repo = get_repo_slug()
                    if repo:
                        post_reactions(plan_abs_path, repo)
                break

            if RATE_LIMIT_RE.search(output_text):
                if attempt >= MAX_RETRIES:
                    print()
                    warn(
                        f"Rate-limited {MAX_RETRIES} times in a row — giving up. Plan stays in-progress."
                    )
                    break
                wait_secs = _parse_retry_after_text(output_text) + 60
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                resume_str = (datetime.now() + timedelta(seconds=wait_secs)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                print()
                warn(
                    f"Usage limit hit (attempt {attempt}/{MAX_RETRIES}). "
                    f"Now: {now_str} | Delay: {wait_secs}s | Resume: {resume_str}"
                )
                time.sleep(wait_secs)
                info("Retrying...")
                print()
                continue

            print()
            warn(f"Claude exited with code {claude_exit}. Plan stays in-progress — re-run to resume.")
            break

        impl_duration_secs = int(time.time() - impl_start)
        print()
        info(f"Implementation ended:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        info(
            f"Duration:              {impl_duration_secs // 60}m "
            f"{impl_duration_secs % 60}s ({impl_duration_secs}s total)"
        )

        if claude_exit != 0:
            sys.exit(claude_exit)

        info("Plan complete. Looking for next plan...")
        print()


if __name__ == "__main__":
    main()
