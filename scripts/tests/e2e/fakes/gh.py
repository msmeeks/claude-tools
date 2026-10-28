"""Fake `gh` for the e2e suite: serves PR and issue state from the JSON file named by
E2E_STATE and records every argv. Models only what run-next-plan.py calls; anything else
exits non-zero naming its argv so a new runner `gh` call fails loudly."""

import json
import os
import sys


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _save(path, state):
    with open(path, "w") as fh:
        json.dump(state, fh)


def _flag(argv, name):
    return argv[argv.index(name) + 1] if name in argv else None


def _project(obj, fields):
    return {k: obj.get(k) for k in fields}


def _pr_list(argv, state):
    prs = state.get("prs", [])
    head = _flag(argv, "--head")
    if head is not None:
        prs = [p for p in prs if p.get("headRefName") == head]
    if _flag(argv, "--state") != "all":
        prs = [p for p in prs if p.get("state") == "OPEN"]
    limit = _flag(argv, "--limit")
    if limit is not None:
        prs = prs[: int(limit)]
    fields = (_flag(argv, "--json") or "number").split(",")
    print(json.dumps([_project(p, fields) for p in prs]))


def _find_pr(state, number):
    for pr in state.get("prs", []):
        if str(pr["number"]) == number:
            return pr
    sys.exit(f"fake gh: no PR #{number}")


def main():
    path = os.environ.get("E2E_STATE")
    if not path:
        sys.exit("fake gh: E2E_STATE is not set")
    argv = sys.argv[1:]
    state = _load(path)
    state.setdefault("calls", []).append(argv)
    _save(path, state)

    sub = " ".join(argv[:2])
    if state.get("fail", {}).get(sub):
        print(f"fake gh: {sub} forced to fail", file=sys.stderr)
        sys.exit(1)

    if sub == "auth status":
        return
    if sub == "pr list":
        _pr_list(argv, state)
        return
    if sub == "pr view":
        pr = _find_pr(state, argv[2])
        fields = (_flag(argv, "--json") or "number").split(",")
        print(json.dumps(_project(pr, fields)))
        return
    if sub == "pr edit":
        pr = _find_pr(state, argv[2])
        pr["body"] = _flag(argv, "--body") or ""
        _save(path, state)
        return
    if sub == "issue view" and _flag(argv, "--jq") == ".labels[].name":
        issue = state.get("issues", {}).get(argv[2], {})
        for label in issue.get("labels", []):
            print(label)
        return
    sys.exit(f"fake gh: unmodelled command: {argv}")


if __name__ == "__main__":
    main()
