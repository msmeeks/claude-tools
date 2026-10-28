# Plan: /close-iteration leaves a clean checkout

**Issues:** #102, #90, #93

---

## Goal

After `/close-iteration` merges the integration PR, none of the gitignored runner artifacts
remain, so the next iteration can't read last iteration's findings or PR summary.

---

## Context

`skills/close-iteration/skill.md` Step 4 tells the agent to leave the gitignored runtime
artifacts (`implementation-logs/`, `prd.json.lock`) and never mentions
`sdlc-review-findings.md` or `pr-summary.md`; they are deleted only on the archive fallback.
Stale copies sit beside the next iteration's and Step 5 could read an old findings file. The
canonical list is `_artifact_ignore_paths()` in `scripts/run-next-plan.py` (L1059-1072). This
plan also renames the skill file to `SKILL.md` (#90; the only lowercase one, which breaks
`setup-symlinks-desktop.sh` on case-sensitive filesystems), fixes the unconditional Step 6
lookup block (#93), and corrects `global/CLAUDE.md` L72, which puts the findings file and PR
summary under `plans/` when they live at the config root.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `skills/close-iteration/skill.md` → `SKILL.md` | Rename; frontmatter + intro; Step 4 pointer; new Step 9e; Step 6 code block; Step 10 report line |
| `scripts/clean-iteration-artifacts.py` | New helper: the 9e removal logic, reusing the runner's path list and lock |
| `scripts/tests/test_clean_iteration_artifacts.py` | New: pytest for the helper against a real temp git repo |
| `global/CLAUDE.md` | L72 location of findings file and PR summary |
| `docs/features/skills.md` | L34 path reference; close-iteration section (~L99) gains a 9e sentence |
| `docs/features/run-next-plan.md` | L41 path reference; L207 cleanup now removes the artifacts |
| `docs/agents/PRIVACY.md` | Retention: close-iteration removes the four artifacts after merge; 30-day log rule is the fallback |
| `scripts/CONTEXT.md` | One line naming the new helper, if the area lists its scripts |
| `skills/CONTEXT.md` | Only if it already describes close-iteration's cleanup (it doesn't today — skip) |

### Steps

1. **Rename first, in its own commit.** `git mv skills/close-iteration/skill.md
   skills/close-iteration/SKILL.md`. macOS is case-insensitive: if git refuses, go via a
   temp name (`skill.md` → `skill.tmp.md` → `SKILL.md`). Confirm `git ls-files
   skills/close-iteration` shows `SKILL.md`. Update the two path references
   (`docs/features/skills.md` L34, `docs/features/run-next-plan.md` L41). Afterwards grep
   the repo (including `setup-symlinks-desktop.sh` and other scripts) for
   `close-iteration/skill.md` and any other lowercase `skill.md` mention — zero hits. The
   `~/.claude/skills` symlink points at the directory, so no relink is needed.
2. **Frontmatter, intro, Step 4.** `description` (L3) and the intro (L8-10) list only
   `<config-root>/plans/` removal — add "and the gitignored runtime artifacts". Step 4
   (L169-171): replace "leave them and report `removed: yes`" with "they are removed after
   the merge in Step 9e", and reword the "on their own are not a trigger" sentence so it
   still reads correctly and points at 9e. The archive fallback (L168-182) is unchanged.
3. **Helper `scripts/clean-iteration-artifacts.py`** (TDD; precedent for a helper the skill
   calls: `skills/pr-image-upload/pr-image-upload.sh`, but put this one in `scripts/` so
   pytest covers it). Stdlib only. Reuse the runner rather than re-listing paths: load
   `run-next-plan.py` the way the tests do and take `resolve_config_root`,
   `_artifact_ignore_paths()` (L1059-1072, the source of truth for the four paths) and the
   lock path `_prd_lock` uses (L332-340). Flag `--findings-filed` (Step 5 filed or
   explicitly dismissed every finding); without it the findings file is kept. Logic:
   - `top = git rev-parse --show-toplevel`; build absolute paths from it.
   - If `<config-root>` or `<config-root>/plans/` is a symlink → skip all four, reason
     `symlink`.
   - Per artifact: absent → reason `absent` (not reported as removed); leaf is a symlink,
     or `realpath` of its **parent** is neither `top` nor under `top + "/"` (trailing
     slash, so `/repo-evil` doesn't match `/repo`) → `symlink`; `git check-ignore -q --`
     fails → `not ignored`; `git ls-files --` prints anything → `tracked` (`check-ignore`
     on a directory doesn't prove a force-added tracked file isn't inside it); findings file
     without `--findings-filed` → `findings unfiled`.
   - Lock and logs: `flock` is not installed on macOS, so in this one process open the lock
     file, take `fcntl.flock(f, LOCK_EX | LOCK_NB)`, `shutil.rmtree` `implementation-logs/`,
     then unlink the lock while still holding it. Any error (held, missing, permission) →
     reason `locked` for both; still process the two config-root files. A runner started
     after the unlink creates a fresh lock; that residual window is accepted — the user is
     closing the iteration, so no runner should be running.
   - Then `rmdir` `<config-root>/plans/` if empty. Never touch `plans/archive/`.
   - Output: one line per artifact, `removed: <relpath>` or `skipped: <relpath> (<reason>)`.
     Reason set is exactly `absent`, `symlink`, `not ignored`, `tracked`, `locked`,
     `findings unfiled`. Names and reasons only — never file contents or log lines. Exit 0
     even when something is skipped (skips are reported, not errors).
   - Tests (real temp git repo + bare origin, as `test_orchestration.py` builds them): all
     four removed and empty `plans/` removed; `plans/archive/` survives; a tracked file and
     a force-added tracked file inside `implementation-logs/` survive (`tracked`); a
     non-ignored file survives; `plans/` symlinked outside the repo → nothing outside
     touched (`symlink`); a held lock (second fd holding `LOCK_EX`) → logs and lock kept
     (`locked`), config-root files still removed; findings kept without `--findings-filed`;
     absent artifacts reported `absent`.
4. **New Step 9e — remove runtime artifacts** (after 9d, L329-336), short like 9a-9d with one
   code block: run only after Step 8's merge succeeded, on the default branch after 9c (so
   ignore rules come from that checkout):
   `python3 ~/.claude/scripts/clean-iteration-artifacts.py [--findings-filed]`.
   `setup-symlinks.sh` (L67-71) links each `scripts/*` file individually, so re-run it after
   adding the helper; the helper finds `run-next-plan.py` via `Path(__file__).resolve()`
   so the symlink resolves to the repo copy. Pass `--findings-filed` only if Step 5 filed or explicitly
   dismissed every finding. Say one sentence on why (it is the only local copy of unfiled
   findings) and point at the helper for the safety rules rather than restating them.
5. **Step 6** (L227-234): split the code block so the `gh issue list --label prd …` command
   sits in its own block introduced by "Only if `prd_issue` is absent:", matching Step 2c's
   one-command-per-block shape. (Not a `#` comment — an agent runs the block anyway.)
6. **Step 10 report** (L342-364): add `Runtime artifacts:  removed: a, b` in the aligned
   `Key:  value` shape, then one indented `skipped: <path> (<reason>)` line per skip,
   matching `Spec issues skipped: #N (reason: <gap>)`. Echo the helper's reason strings
   verbatim. Omit `absent` artifacts from both lists, and never list as removed an artifact
   the Step 4 fallback moved into the archive. Each skip of `implementation-logs/` or the
   findings file adds a one-line manual-delete hint — they stay on disk and are the most
   sensitive artifacts (PRIVACY.md). Add this rule beside the existing "never 'removed:
   no'" note.
7. **`global/CLAUDE.md` L72**: one clause saying `sdlc-review-findings.md` and
   `pr-summary.md` sit at the config root, not under `plans/`. The file must stay under 100
   lines (83 today). It is symlinked machine-wide — change nothing else; confirm with
   `git diff global/CLAUDE.md` that only L72 changed.
8. **Docs**: `docs/features/run-next-plan.md` L207 — close-iteration now removes the four
   artifacts after merge. `docs/features/skills.md` close-iteration section — one sentence
   on 9e and the helper. `docs/agents/PRIVACY.md` Retention — `/close-iteration` removes all
   four artifacts after merge; the 30-day log-pruning rule is the fallback for an iteration
   that is never closed. `scripts/CONTEXT.md` — name the helper if the area lists scripts.
9. Commits: `Refs #102` for the cleanup, `Refs #90` for the rename, `Refs #93` for Step 6.

---

## Acceptance Criteria

- [ ] After Steps 4-9e (tracked-plans case) none of the four artifacts and no `<config-root>/plans/` remain; the untracked-plans archive case still archives and `plans/archive/` survives.
- [ ] A tracked file at one of those paths, or a force-added tracked file inside `implementation-logs/`, is not deleted.
- [ ] With `<config-root>/plans/` symlinked outside the repo, nothing outside the repo is touched.
- [ ] With another process holding `prd.json.lock`, the lock and logs are kept and reported `locked`.
- [ ] The findings file is kept unless Step 5 filed or dismissed every finding.
- [ ] Step 10 reports removed and skipped artifacts with the helper's reason strings, names only.
- [ ] The skill file is `skills/close-iteration/SKILL.md`; no reference to `skill.md` remains.
- [ ] Step 6 runs the `prd` label lookup only when `prd_issue` is absent.
- [ ] `global/CLAUDE.md` L72 is accurate and the file is under 100 lines.
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass.

### How to verify

The helper's pytest cases cover the safety rules. Then one scratch-repo walk-through: create
`docs/agents/plans/{prd.json,implementation-logs/x.log,prd.json.lock}`,
`docs/agents/sdlc-review-findings.md`, `docs/agents/pr-summary.md`, all gitignored; follow
Steps 4 and 9e; `git status --ignored docs/agents` shows nothing iteration-related.

---

## Pre-Implementation Review
All findings below are folded into the steps above.

- **sdlc-security-reviewer:** findings
  - medium (Step 3): symlink handling:
    - check the leaf and that the realpath parent is under the top level (prefix with a trailing slash);
    - the config root and `plans/` must not be symlinks;
    - build absolute paths from the top level.
  - medium (Step 3): `check-ignore` on a directory doesn't prove its contents are untracked; require empty `git ls-files`.
  - low (Step 3): there is a lock-probe TOCTOU. One process holds the lock while removing; the residual window is accepted explicitly.
  - low (Step 4): it runs on the default branch, whose ignore rules may differ; report `not ignored`.
  - info: gate on Step 5 and on merge success; `rmtree` only the logs dir; the `global/CLAUDE.md` diff is L72 only.
- **sdlc-privacy-reviewer:** findings
  - low: PRIVACY.md Retention must say `/close-iteration` removes all four artifacts; the 30-day rule is the fallback.
  - low: keep the findings file unless Step 5 filed or dismissed every finding (`findings unfiled`).
  - low: a skip report adds a manual-delete hint for logs and findings.
  - info: report names and reasons only, never contents. The step is net-positive for storage limitation, and removing `pr-summary.md` is correct.
- **sdlc-accessibility-reviewer:** no findings
- **sdlc-design-reviewer:** findings (no design brief; reviewed against conventions)
  - major: one skip-reason set shared by the helper and Step 10.
  - major: the Step 10 shape is `Key:  value` plus indented `skipped:` lines. Absent and archived artifacts are never reported as removed.
  - major: the removal logic is too dense for prose, so it moves to a pytest-covered helper in `scripts/`.
  - minor: reuse `_artifact_ignore_paths()`, the lock path and the config root.
  - minor: update the Step 4 "not a trigger" sentence, the frontmatter and the intro.
  - minor: Step 6 gets a separate block.
  - minor: a skills.md 9e sentence.
  - minor: grep `setup-symlinks-desktop.sh`.
  - minor: the `global/CLAUDE.md` change stays one clause.
