# Skills

Slash-command definitions for the Claude Code CLI. Each subdirectory holds a `SKILL.md`
(frontmatter + prose) that the CLI loads when the user types `/<name>`. `setup-symlinks.sh`
symlinks this directory into `~/.claude/skills/`, alongside the upstream engineering skills,
which are installed separately and not managed here.

Detail per skill lives in [../docs/features/skills.md](../docs/features/skills.md); the
upstream siblings are covered in
[../docs/features/third-party-skills.md](../docs/features/third-party-skills.md).

## Language

**Skill**:
A named, user-invocable procedure the CLI loads on `/<name>`. Prose instructions, not code.
_Avoid_: command, macro, prompt template

**Iteration**:
One pass of the plan-then-run cycle: `/plan-iteration` grooms the backlog into plans, the
Ralph loop implements them on a single integration branch and PR, `/close-iteration` merges
and tears down. Bounded by one integration branch.
_Avoid_: sprint, cycle, batch

**Plan**:
A single `<slug>.md` file under the config root's `plans/` directory describing one cluster of
issues to implement. The unit of work the Ralph loop selects and drives to `done`.
_Avoid_: task, ticket, story

**Cluster**:
The grouping step: several `ready-for-agent` issues that share a seam, folded into one plan.
_Avoid_: epic, group, bundle

**Gate check**:
A hard stop a skill performs before doing anything irreversible — `/close-iteration` refuses
to merge unless every plan is terminal and the SDLC review is complete.
_Avoid_: precondition, guard

**Finding**:
One defect a review agent reports. Findings are filed as GitHub issues labelled
`sdlc-finding`, then triaged like any other issue.
_Avoid_: comment, remark, issue (a finding *becomes* an issue; the words are not interchangeable)

## Boundaries

- Skills describe *what to do*; they do not contain the implementation. `scripts/` and
  `demo-gen/` are where real code lives.
- A skill may dispatch agents from `agents/`, but agent definitions never reference skills —
  the dependency runs one way.
- Skills that read a repo's project-scoped config must accept **both** layouts
  (`docs/agents/` and `meta/`). See
  [ADR 0001](../docs/adr/0001-scaffolding-layout-with-dual-read-fallback.md); the three
  skills with a hard-stop on a missing context index are `/plan-iteration`,
  `/close-iteration`, and `/triage-pr-comments`.
