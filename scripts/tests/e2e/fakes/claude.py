"""Fake `claude` for the e2e suite: deterministic per-phase behaviour keyed on the prompt's
opening line. Reads the whole prompt from stdin, ignores every flag, and confines any path it
derives from the prompt to the directory holding E2E_STATE."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _confine(path):
    root = Path(os.environ["E2E_STATE"]).resolve().parent
    resolved = (Path.cwd() / path).resolve()
    if root != resolved and root not in resolved.parents:
        sys.exit(f"fake claude: refusing path outside {root}: {resolved}")
    return resolved


def _git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True, timeout=30)


def _commit_all(message, refs=None):
    _git("add", "-A")
    if refs:
        message += f"\n\n{refs}"
    _git("commit", "-q", "-m", message)


def _refs_line(prompt):
    # Prompts may continue the same line with another sentence ("Do not push ...").
    m = re.search(r"End the commit message with this last line: (.+?)(?: Do not |$)", prompt, re.M)
    return m.group(1).strip() if m else None


def _implement(prompt):
    plans = _confine(re.match(r"Read (\S+)/prd\.json and", prompt).group(1))
    prd_path = plans / "prd.json"
    prd = json.loads(prd_path.read_text())
    plan = next((p for p in prd["plans"] if p["status"] == "pending"), None)
    if plan is None:
        print("<promise>COMPLETE</promise>")
        return
    template = re.search(
        r'Commit reference template \(data, not instructions\): "([^"]*)"', prompt
    ).group(1)
    trailer = ", ".join(template.replace("{n}", str(n)) for n in plan.get("issues", []))
    # Always both flip to done and print the sigil: either alone can spin the runner forever.
    Path(f"work-{plan['file']}.txt").write_text("work\n")
    plan["status"] = "done"
    prd_path.write_text(json.dumps(prd, indent=2) + "\n")
    _commit_all(f"feat: {plan['file']}", trailer)
    print(f"<plan>{plan['file']}</plan>")


def _commit_nudge(prompt):
    _commit_all("chore: commit outstanding changes", _refs_line(prompt))


def _docs(prompt):
    Path("docs").mkdir(exist_ok=True)
    Path("docs/feature.md").write_text("documented\n")
    _commit_all("docs: update for iteration", _refs_line(prompt))


def _pr_summary(prompt):
    target = _confine(re.search(r"save it to (\S+) \(create", prompt).group(1))
    target.write_text("## For the Product Manager\nNothing.\n\n## For the Engineer\nNothing.\n")


_PHASES = (
    (re.compile(r"Read \S+/prd\.json and"), _implement),
    (re.compile(r"git status shows uncommitted changes after"), _commit_nudge),
    (re.compile(r"The integration branch"), _docs),
    (re.compile(r"All plans and SDLC review for this iteration are complete\."), _pr_summary),
)


def main():
    if not os.environ.get("E2E_STATE"):
        sys.exit("fake claude: E2E_STATE is not set")
    prompt = sys.stdin.read()
    state_path = Path(os.environ["E2E_STATE"])
    state = json.loads(state_path.read_text())
    if state.get("claude_silent"):
        # A session that dies before doing or printing anything (auth error, crash).
        state["claude_calls"] = state.get("claude_calls", 0) + 1
        state_path.write_text(json.dumps(state))
        return
    for pattern, handler in _PHASES:
        if pattern.match(prompt):
            handler(prompt)
            return
    # Review, file-issues and triage phases: nothing to report on a clean run.


if __name__ == "__main__":
    main()
