# Plan: Catch up to current mattpocock/skills

**Issues:** #81
**Prerequisite:** complete `fix-iteration-state.md` and `feat-commit-refs.md` first. This plan edits the
same `/plan-iteration` and `/close-iteration` steps and the same `_build_claude_prompt` lines. Line
numbers are against `main` @ 3eea893; if they have moved, re-locate them by heading or function.

---

## Goal

This repo works with both the June skills.sh install and the current upstream plugin. It no longer
depends on a `prd` label, and it documents how to install upstream skills safely.

---

## Context

Our Matt Pocock skills were installed 2026-06-23 via skills.sh into `~/.agents/skills`; `qa`, `review`
and `resolving-merge-conflicts` are symlinked into `~/.claude/skills/` from there too, and none of them
are local to this repo. Upstream (main 5beb35b, plugin v1.3.1) has since changed in four ways:
- It now ships as a plugin: `claude plugin install mattpocock-skills@claude-plugins-official`.
- It renamed `to-prd`→`to-spec` (no `prd` label, applies `ready-for-agent`),
  `to-issues`→`to-tickets` (writes `## Parent`), and `CONTEXT`→`GLOSSARY`.
- It removed `qa`, `review` (now `code-review`) and `resolving-merge-conflicts`.
- It added `implement`, `implement-spec`, `wayfinder`, `code-review`, `pr`, `research`, `retro` and
  `wizard`.

Here, `/plan-iteration` Step 8.6 and `/close-iteration` Step 6 find the parent spec by the `prd` label,
which `to-spec` no longer applies. The runner prompt says "Use /qa", which won't exist on the plugin
path. A plugin update would also silently undo the local `/to-prd` mod.

Other machines may still have the June install, so every reference must accept both names. Installing
the plugin on anyone's machine is a human step, listed in the PR. Downstream repos must be checked
for stale references, and problems found there are filed in those repos.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `docs/features/third-party-skills.md` | Install (two methods), supply-chain review note, single rename table, skill table refresh, drop the `/to-prd` local mod, GLOSSARY note |
| `README.md` | L233-240: link to the doc, name both install methods |
| `CONTEXT-MAP.md` | Dual-name any `to-prd`/`to-issues` mention |
| `skills/plan-iteration/SKILL.md` | Step 8.6 parent-spec lookup via `## Parent` |
| `skills/close-iteration/skill.md` | Step 6 checks `prd_issue` (label as legacy fallback), Step 9a closure allow-list; `PRD`→`prd` label case |
| `scripts/run-next-plan.py` | `_build_claude_prompt` L552-553: static `/qa` → `sdlc-qa-engineer` fallback |
| `scripts/tests/test_orchestration.py` | Prompt tests (~L599-620): fallback text, no issue-derived text |
| `global/CLAUDE.md` | L15 tdd name, L80-81 `/qa`; own commit, under 100 lines |
| `docs/features/skills.md` | Parent-spec terminology and lookup |
| `docs/features/run-next-plan.md` | One line on the `/qa` fallback; "the PRD it implements" (L221) terminology |
| `docs/agents/PRIVACY.md` | `prd_issue` is a bare int from `## Parent`; fix stale `/triage-issues` ref (L118-119) if renamed |

### Steps

1. **Diff upstream.** Compare `~/.agents/skills/*` against `mattpocock/skills` main using
   `gh api repos/mattpocock/skills/...`. Record the reviewed upstream commit SHA. List each skill that
   was renamed, removed or added, and each behaviour change our skills or `run-next-plan.py` rely on.
   Verify two things against the installed plugin or upstream docs rather than assuming them:
   - the exact `claude plugin install` syntax;
   - whether plugin skills resolve bare (`/tdd`) or namespaced (`/mattpocock-skills:tdd`).
2. **`docs/features/third-party-skills.md`:**
   - **Install** (L13-22): under the existing H3 "Installation", add `#### Plugin (current)` and
     `#### skills.sh (June install)`. Use one command per fenced block with no `$` prompt, and say
     where each runs: tag `bash` for shell commands and `text` for slash commands. Mark the install
     as a human step. Drop `-y` from the legacy command, or label it as only for people who have
     already reviewed the source.
   - **Supply chain:** before the first install and on each update, review the plugin source,
     including `hooks/`, `.mcp.json`, scripts and `allowed-tools`. Check for network or
     `curl | sh` calls. Verify the marketplace entry resolves to `github.com/mattpocock/skills`
     without claiming the marketplace is vetted. Pin a version if the marketplace allows it. Plugin
     skills run with the session's full permissions; the runner uses `bypassPermissions`. If both
     installs are present, recommend removing one, and say which wins.
   - **Links** (L21-22): replace the bare URLs with a list that uses descriptive link text.
   - **`#### Renamed upstream`:** a new table that is the single source of truth for the rename map,
     with columns `June name (skills.sh) | Current name (plugin) | Notes`. Never leave a cell empty;
     write "Removed upstream" or "Same behaviour". Cover `to-prd`→`to-spec`, `to-issues`→`to-tickets`,
     `CONTEXT.md`→`GLOSSARY.md`, and `qa`/`review`/`resolving-merge-conflicts`→removed upstream
     (`review` → `code-review`).
   - **Skill table** (L51-83): keep `Skill | Description`. Use the new name first with the old name
     in parentheses (L76-77). Mark `qa`, `review` and `resolving-merge-conflicts` as "skills.sh install
     only; removed upstream". Add the new upstream skills.
   - **Workflow block** (L41-43): tag it ```text and update it to
     `/grill-with-docs → /to-spec → /to-tickets → …`, then mention the old names once.
   - **Local modifications** (L85-91, row L89): remove the `/to-prd` `prd`-label mod, since nothing
     needs it once steps 5–6 land. A mod would be overwritten by plugin updates anyway.
   - **GLOSSARY** (L33, L64, L79): add one sentence. Upstream renamed this to `GLOSSARY.md`; this repo
     keeps `CONTEXT.md` per `docs/agents/domain.md`. Cite follow-up #N. Before opening the PR, file
     that follow-up (`enhancement`, `ready-for-human`) for a possible migration.
   - **Keeping up to date** (L95-101): give an update instruction for each method.
3. **Dual-name convention.** Put the new name first and the old one in parentheses, matching
   `global/CLAUDE.md` L55: "`/to-spec` then `/to-tickets` (`/to-prd`, `/to-issues` on older installs)".
   Other files link to the rename table rather than restating it. `README.md` L233-240 becomes a short
   pointer to `[third-party skills reference](docs/features/third-party-skills.md)` that names both
   methods. Then run `git grep -nE "to-prd|to-issues|CONTEXT\.md"`. Every hit must either work with
   both names or be intentional; note each intentional one in the PR.
4. **Terminology.** Use "spec" in new prose, and say once that the identifiers `prd_issue` and
   `prd.json` keep their names. Also update `docs/features/skills.md` L103/L126 and
   `docs/features/run-next-plan.md` L221.
5. **`/plan-iteration` Step 8.6** (`skills/plan-iteration/SKILL.md` ~L198-200). Write the parent-spec
   lookup as a numbered fallback list:
   1. In each pool issue's `## Parent` section, take the first same-repo `#N` or `…/issues/N` URL and
      ignore cross-repo refs (`owner/repo#N`). If pool issues name different parents, omit
      `prd_issue` and warn.
   2. Verify the candidate with `gh issue view N --json number,state,labels`. It must be open, must not
      be a pull request (use `gh api repos/{owner}/{repo}/issues/N` and check for no `pull_request`
      key), and must carry `ready-for-agent` or the legacy `prd` label.
   3. Legacy fallback: `gh issue list --label prd --state open --json number`.
   4. Otherwise omit `prd_issue`.

   Store only the int, which `_validate_prd_schema` already enforces at L197-200. Request
   `--json number` (plus `state,labels` for verification) only. Never copy the parent's title or body.
6. **`/close-iteration` Step 6** (`skills/close-iteration/skill.md` L187-203) and **Step 9a**
   (L252-257):
   - Check `prd.json.prd_issue` first, re-derived from prd.json rather than from issue text.
   - Keep `gh issue list --label prd` (lowercase; fix `PRD`) only as a legacy fallback. Don't widen it
     to all open `ready-for-agent` issues.
   - Don't widen the existing `--json number,title,body` call.
   - Closure allow-list: Step 9a closes only `prd_issue` or legacy `prd`-labelled issues, and only
     after Step 6's three-check gate passes. Child `#N` refs in a spec body are read as state checks
     and are never closed.
   - Use the same lookup sentence as Step 8.6.
7. **Runner prompt** (`scripts/run-next-plan.py` L552-553). Keep both lines static literals, with no
   filesystem probing and no interpolation:
   - L553 becomes "Run automated tests, lint and smoke checks: use /qa if that skill is installed,
     otherwise dispatch the sdlc-qa-engineer agent."
   - L552 `/tdd` is unchanged if step 1 shows the plugin resolves bare `tdd`. Otherwise use
     "Use /tdd (or the plugin's namespaced tdd skill)".
   - Update the prompt tests, and add one asserting the prompt contains no issue-derived text.
8. **`global/CLAUDE.md`** (own commit, stays under 100 lines):
   - L15: keep `skill='tdd'` as primary. Add "(or the plugin's namespaced `tdd`)" only if step 1 shows
     namespacing.
   - L80-81: `/qa` → "`/qa` (skills.sh install only; otherwise the `sdlc-qa-engineer` agent)".
   - Add no new rules, and nothing that widens permissions or installs anything.
9. **`docs/agents/PRIVACY.md`.** In the `prd.json` section (~L50-57), add: "`prd_issue` is a bare
   integer from a pool issue's `## Parent` section. No issue title, body or author is copied into
   `prd.json`, logs or prompts." Fix the `/triage-issues` reference (L118-119) if the name is stale.
   Optionally add one line noting that third-party skills are a supply-chain surface, cross-referencing
   the indirect-prompt-injection residual risk.
10. **Labels.** `needs-triage`, `needs-info` and `ready-for-human` already exist
    (`gh label list`, 2026-10-26). Verify this and note it in the PR; no action is needed.
11. **Downstream check.** Grep `Hospitality-Delivered/hd-tech-standards` (`plugins/hd-standards/skills/*`,
    `tools/defaults/CLAUDE.md`, `docs/agents/`) and `Hospitality-Delivered/repo-template` (`CLAUDE.md`,
    `CONTEXT-MAP.md`, `docs/agents/`, `docs/features/ralph-review.md`). Look for `to-prd`, `to-issues`,
    `/triage` invocation, triage label strings, `run-next-plan.py` behaviour and `plan-iteration` step
    references. Read access is via `GH_CONFIG_DIR=~/.config/gh-bnb gh api …`.
    - An exploration on 2026-10-26 found no stale skill-name hits. Re-verify.
    - File each new stale reference as an issue in its own repo, and link it from the PR.
    - Already filed: hd-tech-standards#76, repo-template#27, hd-chrome-extension#5, and a comment on
      hd-tech-standards#71.
12. **Verify.** Run `cd scripts && python3 -m pytest` and `python3 -m ruff check .`.
13. **PR description.** List these human steps:
    - install the plugin on each machine after reviewing its source;
    - remove the skills.sh copies or choose which wins;
    - merge the GLOSSARY follow-up decision.

**Out of scope:**
- the `/triage` call sites in `/plan-iteration` and `run-next-plan.py`, tracked separately;
- migrating this repo to `GLOSSARY.md` (that is the follow-up);
- changing any machine's install.

---

## Acceptance Criteria

- [ ] No reference in the repo works only with the June skill names; each place accepts the old name or the new one (`git grep -nE "to-prd|to-issues|CONTEXT\.md"` hits are all dual-name or intentional)
- [ ] `/plan-iteration` finds the parent spec issue without relying on a `prd` label
- [ ] `third-party-skills.md` describes the current upstream skill set and both install methods, and lists no local modifications that an update would silently undo
- [ ] Labels `needs-triage`, `needs-info` and `ready-for-human` exist in this repo
- [ ] Each downstream location was grepped; each stale reference is fixed here or filed in its repo and linked from the PR
- [ ] The runner prompt falls back to `sdlc-qa-engineer` when `/qa` is absent and contains no issue-derived text (tested)
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** findings (no Critical/High)
  - Medium: plugin supply chain. The install is a human step, with a source review of hooks, `.mcp.json` and scripts on install and on update. Verify the marketplace entry, don't claim it is vetted, pin if possible, drop `-y`, and verify the command syntax. (Steps 1, 2)
  - Low: `## Parent` parsing. Same-repo first `#N` only, all pool issues must agree, and the issue must exist, be open, carry the label, and not be a PR. Store an int. (Step 5)
  - Low: close-iteration scope. Check `prd_issue` plus the legacy label only, keep a closure allow-list, and gate closing on the three checks. (Step 6)
  - Low: `global/CLAUDE.md`. Keep `skill='tdd'` as primary, add the namespaced form only if verified, and add nothing that widens permissions. (Step 8)
  - Info: keep the prompt lines static literals, with no probing or interpolation, and add a no-issue-text test. (Step 7)
  - Info: say which install wins when both are present. (Step 2)
- **sdlc-privacy-reviewer:** findings (no Critical/High)
  - Medium: add a PRIVACY.md line saying `prd_issue` is a bare int from `## Parent`. (Step 9)
  - Medium: Step 8.6 extracts only the integer and requests `--json number`-level fields. close-iteration's existing body fetch is not widened. (Steps 5, 6)
  - Info: a plugin egress and permissions note goes in the install docs. Mark the skills.sh install as legacy and unpinned. (Step 2)
  - Info: the QA fallback is a static string with no data-flow change. (Step 7)
  - Info: the `/triage-issues` reference in PRIVACY.md may be stale. (Step 9)
- **sdlc-accessibility-reviewer:** findings (markdown docs only, no terminal output change)
  - Major: put renames in a separate small table and leave no empty cells. (Step 2)
  - Major: remove stale old-name content and the local-mod row. (Steps 2, 3)
  - Major: replace bare URLs and the fragile hard break with descriptive links. (Step 2)
  - Major: use H4 per install method, one command per fenced block, language tags, and say where each command runs. (Step 2)
  - Minor: the README links to the doc and names both methods. (Step 3)
  - Minor: don't mark removed names with bold or colour alone. (Step 2)
  - Minor: the parent lookup is a numbered fallback list. (Step 5)
- **sdlc-design-reviewer:** findings (no UI; repo conventions)
  - Critical: `qa`, `review` and `resolving-merge-conflicts` are skills.sh symlinks, not local skills. Document them as legacy-only. The runner prompt and `global/CLAUDE.md` need the fallback. (Steps 2, 7, 8)
  - Critical: the fallback is an agent, not a slash command, so use single-line conditional wording. (Step 7)
  - Major: keep a single rename table, and use new-first dual naming that matches `global/CLAUDE.md` L55. (Steps 2, 3)
  - Major: the local mod is undone by plugin updates. Drop it. (Step 2)
  - Major: unify the parent-spec lookup wording across both skills, have close-iteration read `prd_issue` first, fix the `PRD`/`prd` case, and use "spec" terminology. (Steps 4, 5, 6)
  - Minor: provide two install paths and an update command for each method. (Step 2)
  - Minor: verify plugin namespacing. (Step 1)
  - Minor: add the GLOSSARY follow-up note with an issue number. (Step 2)
  - Minor: limit edits to `skills.md` and `run-next-plan.md` to the terminology and the `/qa` line. (Step 4)
  - Info, out of scope: the lowercase filename of `close-iteration/skill.md`.
