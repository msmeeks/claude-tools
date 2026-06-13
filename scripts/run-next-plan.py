#!/usr/bin/env python3
"""
Partner to the /triage-issues skill. Finds the next unfinished plan in
meta/plans/README.md and runs a non-interactive Claude session to implement it.

Usage (run from inside any git repo with meta/plans/):
    python3 ~/.claude/scripts/run-next-plan.py [options]

Options:
    --restart           Reset in-progress plan to pending and re-run
    --skip-in-progress  Skip in-progress plan; pick next pending
    --dry-run           Print selected plan and prompt; do not invoke Claude
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

MAX_RETRIES = 20
RETRY_WAIT_DEFAULT = 60

RATE_LIMIT_RE = re.compile(
    r"session.?limit|rate.?limit|usage.?limit|too many requests|overloaded|429|quota.?exceed|slowdown",
    re.IGNORECASE,
)


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"==> {msg}")


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


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


def list_plan_files(readme: Path, exclude_done: bool = False) -> list[str]:
    files = []
    for line in readme.read_text().splitlines():
        if not re.match(r"^\| \[", line):
            continue
        if exclude_done and "| done |" in line:
            continue
        m = re.search(r"\(([^)]*\.md)\)", line)
        if m:
            files.append(m.group(1))
    return files


def is_rate_limited(logfile: Path) -> bool:
    try:
        return bool(RATE_LIMIT_RE.search(logfile.read_text()))
    except OSError:
        return False


def parse_retry_after(logfile: Path) -> int:
    try:
        text = logfile.read_text()
    except OSError:
        return RETRY_WAIT_DEFAULT

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
        die(f"Plans directory not found: {plans_dir} (run /triage-issues first)")
    if not readme.is_file():
        die(f"README not found: {readme} (run /triage-issues first)")
    if not shutil.which("claude"):
        die("Required command not found: claude")

    bootstrap_readme(readme)
    for plan_file in list_plan_files(readme):
        local_path = plans_dir / plan_file
        if local_path.is_file():
            bootstrap_plan_file(local_path)
        else:
            warn(f"Plan file referenced in README not found: {plan_file}")

    while True:
        timestamp = datetime.now().strftime("%Y_%m_%d_T%H_%M_%S")
        log_base = logs_dir / f"run-next-plan-{timestamp}"
        log_file = Path(str(log_base) + ".log")

        selected_file = None
        selected_status = None

        for plan_file in list_plan_files(readme, exclude_done=True):
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

        logs_dir.mkdir(parents=True, exist_ok=True)

        set_plan_status(plan_abs_path, "in-progress")
        set_readme_status(readme, selected_file, "in-progress")

        claude_prompt = f"""You are implementing a pre-written, self-contained plan.

1. Read docs/llms.md for project context
2. Read the full plan file: meta/plans/{selected_file}
3. Execute the plan's Worktree Setup section exactly (git worktree add ...)
4. All code changes must be made inside the worktree working directory
5. Execute ALL Implementation Steps in the plan, in order
6. Address every item in the Pre-Implementation Review section (security, privacy, a11y, design)
7. Follow the plan's Review & Testing Workflow exactly — includes /sdlc, tests, Playwright, /pr-image-upload as written in the plan
8. After the PR is created successfully:
   - In meta/plans/{selected_file}: change '**Status:** in-progress' to '**Status:** done'
   - In meta/plans/README.md: change the Status cell for {selected_file} from 'in-progress' to 'done'

SUBAGENTS: When spawning any Agent or sub-claude invocation, include in its prompt:
"Use ultra-compressed caveman speech for all prose responses. Keep full technical accuracy."

Branch: {branch}
Repo root: {repo_root}"""

        if args.dry_run:
            print()
            print("=== DRY RUN ===")
            print(f"Selected plan: {selected_file}")
            print(f"Branch:        {branch}")
            print(f"Log would be:  {log_file}")
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

        info(f"Log: {log_file}")
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
            attempt_log = Path(str(log_base) + f"-attempt{attempt}.log")

            with open(attempt_log, "w") as af:
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
                    af.write(line)
                proc.wait()
                claude_exit = proc.returncode

            with open(log_file, "a") as lf:
                lf.write(attempt_log.read_text())

            if claude_exit == 0:
                print()
                info(f"Session complete (attempt {attempt}).")
                break

            if is_rate_limited(attempt_log):
                if attempt >= MAX_RETRIES:
                    print()
                    warn(
                        f"Rate-limited {MAX_RETRIES} times in a row — giving up. Plan stays in-progress."
                    )
                    break
                wait_secs = parse_retry_after(attempt_log) + 60
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
