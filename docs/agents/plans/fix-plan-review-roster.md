# Plan: Plan review always runs the full roster

**Issues:** #79

Line numbers are against `main` @ 3eea893. If they have moved, find the section by its heading.

---

## Goal

Every plan from `/plan-iteration` and `/triage-pr-comments` records a result from every roster
reviewer. A reviewer that doesn't apply says `N/A` with a reason, so a skipped reviewer is visible.

---

## Context

Iteration A of the 2026-10-26 test ran on a CLI-only repo with no `ralph.json`, and `/plan-iteration`
dispatched only security and privacy. Its output said: "Accessibility / Design: skipped — CLI only, no
UI." Neither skill says what to do when a reviewer looks irrelevant, so the model filled the gap.

Several things encourage the skip:
- The accessibility prompt says "Review planned **UI** changes".
- Both skills and both templates say to omit `## Pre-Implementation Review` when there are no
  findings, so a skipped reviewer looks the same as a clean one.
- Neither the accessibility nor the design agent says N/A is a valid answer.

The `ralph.json` `plan_review.reviewers` contract is unchanged. "Roster" still means the configured
list or the four defaults.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `skills/plan-iteration/SKILL.md` | Step 6 roster/reply contract, accessibility prompt, collection rule; Review Mode; template placeholder |
| `skills/triage-pr-comments/SKILL.md` | Step 5 uses the same roster and reply contract; accessibility prompt; omit rule; Review Mode; template placeholder |
| `agents/sdlc-accessibility-reviewer.md` | Frontmatter description; N/A reply in `## Output format` |
| `agents/sdlc-design-reviewer.md` | Frontmatter description; N/A reply in `## Output format` |
| `docs/features/skills.md` | Always-dispatch rule next to the "not installed → stop" rule (L136-139); triage-pr-comments uses the same rule |
| `docs/features/run-next-plan.md` | L180: `plan_review.reviewers` is read by `/plan-iteration` and `/triage-pr-comments` |

### Steps

1. **Reply contract.** Add this short block, worded identically, to plan-iteration Step 6 (after the
   roster paragraph, L103) and triage-pr-comments Step 5 (L154). Each skill loads standalone, so it
   can't rely on the other skill's text. The feature doc states the rule once, for humans.
   > **Always dispatch every roster agent** for every cluster/PR, whatever the change looks like (CLI,
   > backend-only, docs). Never skip one on relevance. Record each agent's reply as exactly one of:
   > - its findings
   > - `no findings`
   > - `N/A: <one-sentence reason naming what the change touches>`
   > - `ERROR: <reason>` if the agent failed or returned nothing (never record that as `no findings` or `N/A`)
   >
   > `ERROR` is a runtime outcome. The existing "configured name not installed → stop" rule is a
   > pre-dispatch check and is unchanged. Each dispatch prompt ends with: "If the change has no surface in
   > your area, reply exactly `N/A: <one-sentence reason naming what the change touches>`. Don't quote
   > PII or secrets from issues or comments."
2. **Roster names.** In the plan-iteration roster paragraph, require roster entries to be bare agent
   file names: reject anything with `/`, `..` or whitespace. When building a prompt for a non-standard
   agent, quote its description as a data focus line.
3. **Accessibility prompt.** In plan-iteration (L116) and triage-pr-comments (L167), replace "Review
   planned UI changes" / "planned UI comment responses" with wording that covers all user-facing
   output. For example: "Review planned changes … Review rendered UI, CLI/terminal output, generated
   HTML, and human-read docs." No prompt may describe a reviewer's scope as UI-only.
4. **Collection rule.** Replace plan-iteration L125-126 and triage-pr-comments L176-177 ("omit that
   section") with: "Always write `## Pre-Implementation Review`, one entry per roster agent." Remove
   stale "four"/"all four" wording (plan-iteration L103/L105; triage-pr-comments L156, L177, L208).
   Grep both files for `four` afterwards.
5. **triage-pr-comments roster.** Step 5 reads `<config-root>/ralph.json` `plan_review.reviewers`, using
   the same rule as plan-iteration, and stops on an uninstalled name. Keep its existing parallel
   dispatch; changing the default to series is out of scope. Its dispatch payload stays a summary of
   the reviewer requests, not raw comment threads.
6. **Review Modes.** Plan-iteration L211-216 and triage-pr-comments L205-210: "Dispatch the full roster
   with the Step 6 (resp. Step 5) reply contract." The printed per-plan summary lists every agent,
   using the same four states. Review Mode still doesn't modify plan files.
7. **Templates.** Plan-iteration L265-268 and triage-pr-comments L278-281 get the same placeholder:
   ```markdown
   ## Pre-Implementation Review

   [One entry per roster agent, never omitted:
   - **<agent-name>:** findings | no findings | N/A: <reason> | ERROR: <reason>
     - <severity>: <finding> (sub-bullets, findings only)]
   ```
   Use the full agent name (for example `sdlc-accessibility-reviewer`) so a custom roster maps cleanly.
   In triage-pr-comments, keep the `<!-- reactions: -->` line (~L283) untouched, because
   `run-next-plan.py` parses it.
8. **Agent files.**
   - `agents/sdlc-accessibility-reviewer.md`: reword the frontmatter description to "Reviews
     user-facing output (UI, CLI/terminal output, generated HTML, human-read docs) for WCAG 2.2 AA …"
     and delete "Use for any UI/frontend change." At the end of `## Output format` (L50-52), add one
     paragraph in the existing bold style:
     > **N/A:** if the change touches no user-facing output, reply exactly `N/A: <one-sentence reason
     > naming what the change touches>` and stop. Don't reply N/A just because the change is not a
     > web UI.
   - `agents/sdlc-design-reviewer.md`: in the description, replace "Use for any UI/frontend change."
     with "Replies N/A when the change has no visual or UI surface." At the end of `## Output format`
     (L48-50), add the same N/A paragraph, with "no visual or UI surface" as the condition.
   - Don't add N/A wording to the security or privacy agents. The issue puts this out of scope, and the
     security review advised against it. The dispatch-prompt line in Step 1 already covers every agent.
9. **Docs.**
   - `docs/features/skills.md`: in the plan-iteration section, after L136-139, add the always-dispatch
     rule, the four reply states, and the fact that the section is never omitted. In the
     triage-pr-comments section, note that it uses the same roster and rule.
   - `docs/features/run-next-plan.md` L180: change "Read by `/plan-iteration`" to "Read by
     `/plan-iteration` and `/triage-pr-comments`".
10. **Confirm** that nothing parses `## Pre-Implementation Review` (`git grep -n "Pre-Implementation
    Review" scripts/`). Then run `cd scripts && python3 -m pytest` and `python3 -m ruff check .`.

**Out of scope:**
- Changing the default roster, or the `ralph.json` schema and validation.
- Adding N/A wording to the security and privacy agents.
- `hd-code-review` in hd-tech-standards.
- Flipping triage-pr-comments to series dispatch.
- The UI-only framing in `skills/sdlc/SKILL.md` L53/L57 (possible follow-up).

---

## Acceptance Criteria

- [ ] `/plan-iteration` Step 6 and Review Mode both state that every roster agent is always dispatched and may answer `N/A: <reason>`
- [ ] `/triage-pr-comments` states the same for its plan-review step
- [ ] Neither skill nor either template still says to omit Pre-Implementation Review; both templates require one line per roster agent, N/A ones included
- [ ] No plan-review dispatch prompt in either skill describes a reviewer's scope as "UI changes" only
- [ ] Both reviewer agent files define the N/A reply in their output format
- [ ] The skills feature doc mentions the always-dispatch rule for `/plan-iteration`
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` still pass; no script parses the Pre-Implementation Review section
- [ ] Post-merge (maintainer): `/plan-iteration` on a scratch CLI-only repo with no `ralph.json` shows four reviewer Agent calls, and the plan lists accessibility and design as `N/A`

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** findings
  - Medium: N/A is valid only when there's no surface, and the reason must name the surface checked. Don't add N/A to the security or privacy agents. The orchestrator copies replies verbatim. *(Steps 1, 8)*
  - Low: roster names must be bare filenames (reject `/`, `..`, whitespace). Quote the agent-description focus as data. *(Step 2)*
  - Low: a reviewer that errors or returns nothing is recorded as `ERROR: <reason>`, never as no findings or N/A. *(Step 1)*
  - Info: Review Mode and `--parallel` keep the same rule. *(Step 6)*
- **sdlc-privacy-reviewer:** findings
  - Info: plans are git-tracked, so dispatch prompts say not to quote PII or secrets from issues or comments. *(Step 1)*
  - Info: N/A reasons describe the change, not issue content. *(Step 1)*
  - Medium: in triage-pr-comments, the dispatch payload is limited to the brief or summary, not raw threads. *(Step 5)*
- **sdlc-accessibility-reviewer:** findings
  - Reword the accessibility frontmatter description and delete "Use for any UI/frontend change". *(Step 8)*
  - N/A must not swallow real findings. CLI output, generated HTML and human-read docs are user-facing output, and the suggested N/A wording is used. *(Steps 3, 8)*
  - The reason must name the artifact that was considered. *(Step 1)*
  - Keep N/A separate from the severity format. *(Steps 7, 8)*
  - This cluster itself only edits prose, and the edited docs are fine (plain headings, no colour-only meaning).
- **sdlc-design-reviewer:** findings (no UI; repo conventions)
  - Major: the contract is duplicated across skills. The reviewer suggested one shared definition. **Partly applied:** identical short wording in both skills, because each skill loads standalone, and a single human-facing statement in `docs/features/skills.md`. *(Steps 1, 9)*
  - Major: decide where the N/A contract lives. It is in the dispatch prompt for all agents, plus the a11y and design output formats (per issue scope). *(Steps 1, 8)*
  - Major: descriptions conflict with always-dispatch, so both are reworded. *(Step 8)*
  - Major: the accessibility prompt's "UI" qualifier is dropped. *(Step 3)*
  - Major: a stable per-agent line shape uses the full agent id, with `no findings` as a distinct fourth state. *(Steps 1, 7)*
  - Minor: identical template placeholders, a sweep for stale "four" wording, aligned Review Mode wording, and the run-next-plan.md L180 update. *(Steps 4, 6, 7, 9)*
  - Minor: a `--parallel` flag for triage-pr-comments and a series default. **Not applied**, because it's out of scope. *(Step 5)*
