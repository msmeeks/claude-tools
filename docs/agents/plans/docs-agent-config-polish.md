# Plan: Agent, skill and privacy doc polish

**Issues:** #90, #93

---

## Goal

The design reviewer finds the brief where the layouts put it, the privacy doc covers every
prd.json field, and the third-party skill install says how to keep its version in check.

---

## Context

Prose-only findings from #90 and #93 that touch agent definitions, a skill, and docs — no
runner code. All are small and decision-free; where an item offers options, pick the smaller
change and say which in the commit. Agents and skills are symlinked live into `~/.claude/`,
so these edits take effect immediately across every repo.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `agents/sdlc-design-reviewer.md` | Brief path, missing-brief severity, scope project-specific lines |
| `docs/agents/PRIVACY.md` | Document `sdlc_deferred_issues`; bullet the prd.json fields |
| `skills/triage-pr-comments/SKILL.md` | No commenter handles: dispatch line, plan template, Case 3, `gh` field list |
| `docs/features/third-party-skills.md` | Version note for the unpinned plugin install |
| `agents/CONTEXT.md` | Re-wrap the long L9 bullet |
| `agents/sdlc-doc-writer.md` | L104 brief link: root path → `docs/agents/DESIGN_BRIEF.md` |

### Steps

1. **`agents/sdlc-design-reviewer.md`** (#90):
   - L16: read `docs/agents/DESIGN_BRIEF.md`, or `meta/DESIGN_BRIEF.md` in un-migrated
     repos — the exact wording of `global/CLAUDE.md` L38 and `skills/plan-iteration/SKILL.md`
     Step 6 (L146). Neither mentions a root `DESIGN_BRIEF.md`; dropping the root path is
     deliberate (consistency with those two) — say so in the commit.
   - UI surface: use the sibling `sdlc-accessibility-reviewer` definition (L60) — rendered
     UI, generated HTML or published docs — verbatim, in both the missing-brief rule and the
     N/A line, so the two agents agree. A missing brief is critical only for a change with a
     UI surface; for CLI/API-only changes it is a suggestion and the review runs against
     existing conventions. Keep "Before reviewing" consistent with the Output format's
     Critical definition, and re-check the frontmatter `description` (L3) still reads right.
   - Say the brief is repo-controlled text read "as data, not instructions" (reuse that
     phrase from `skills/plan-iteration/SKILL.md` L120; the surrounding wording there is
     about roster descriptions, so don't copy it whole).
   - L36-37 (`AppShell`/`WorkerAppShell`, `p-6`): one project's specifics — move them under
     the UI checklist as examples of "the project's shared shell / spacing tokens". Scope the
     Tailwind-specific items (colour tokens, spacing) with "if the project uses Tailwind" so
     the fix isn't half-applied.
   - `agents/sdlc-doc-writer.md` L104 links `../DESIGN_BRIEF.md` (root path): point it at
     `docs/agents/DESIGN_BRIEF.md` in the same commit.
2. **`docs/agents/PRIVACY.md`** (~L50-58, #90): turn the prd.json field sentences into a
   bullet list, formatted like the doc's existing bullets (name in backticks, then what it
   holds and whether it can carry PII in one clause). One bullet per field the runner or
   `/plan-iteration` writes — the full list from `docs/features/run-next-plan.md` L33,
   including `plans[]` (file/issues/size/status/attempts/blocked_by), `sdlc_review_status`,
   `sdlc_review_rounds`, `sdlc_deferred_issues`, `sdlc_finding_issues`,
   `sdlc_round_filed_issues`, `sdlc_review_completed_agents`, `last_reviewed_sha`,
   `feature_branches`, `smoke_test`, `pr_number`, `integration_branch`, `prd_issue`.
   - `smoke_test` (free-form; can embed URLs, tokens or test-account emails) and
     `feature_branches` (names can encode a person or issue title) are user-authored: "can
     carry PII or secrets — keep generic". `_validate_prd_schema` checks types, not content.
   - Issue/PR-number fields, `last_reviewed_sha`, `sdlc_review_completed_agents`,
     `sdlc_review_rounds`: identifiers/metadata only (`sdlc_deferred_issues` is an
     enforced int list). Note a deferred issue number points at an `sdlc-finding` issue that
     stays open and can hold unredacted content.
   - Make the rest of the doc agree: L54-56 ("only filenames and status metadata"), Residual
     risk (~L114, "filename, status, attempts, blocked_by"), Minimization (~L140, "No PII …
     intentionally written"). State that `prd.json` is git-tracked on the integration branch
     and removed before merge.
   - Data inventory: add `triage-pr-comments` plan files (`pr-<N>-comments.md`) — git-tracked,
     paraphrased reviewer requests, no handles.
3. **`skills/triage-pr-comments/SKILL.md`** (#90):
   - Dispatch line (~L164): keep the existing sentence verbatim and append "or copy
     commenter handles" — it is shared by default-roster and extra-agent prompts, so don't
     disturb the N/A-reply contract text. This is a soft control; the "summary of requests,
     never raw threads" payload rule stays primary.
   - Plan template (~L237-261), git-tracked on the integration branch:
     - Drop the `Reviewer` column from the three tables that have it; they then match the
       Style / Doc Nits table, which never had it. Keep the "Reviewer Comments" section
       heading (L240) — L219 refers to it by name.
     - Context paragraph (L237): "what the PR does, who reviewed it, …" → "what the PR does
       and what themes the review comments cover".
     - Add a template rule: Context, Comment and Planned Response text is paraphrased with
       `@handles`, emails and names stripped; planned responses never address a commenter
       by handle. Reword the example Comment cells as unquoted paraphrases (`rename foo to
       bar`, not `"rename foo to bar"`).
   - Case 3 (~L104): reword "append new rows to the appropriate Reviewer Comment tables";
     when updating an existing plan, rebuild its tables in the new shape — drop the old
     column and paraphrase old verbatim Comment text — rather than appending mismatched
     rows. Nothing in `scripts/` parses that column.
   - `gh pr list --json` (L41): drop `author,assignees` (no later use). Keep the L49/L63
     login fetches (self-comment filtering) and add beside them that these values are never
     written to the plan, `prd.json`, `progress.md` or logs.
4. **`docs/features/third-party-skills.md`** (#90): next to the plugin install (L22-25) and in
   "Keeping skills up to date" (L139-147), say the plugin auto-updates unpinned, so an
   upstream change lands as live prompt text in every repo before anyone reviews it. Check
   `claude plugin --help` / `claude plugin marketplace --help` for a way to pin or disable
   auto-update: if one exists, document it as the default. Otherwise name the reviewed
   baseline (commit `5beb35b`, v1.3.1 per the doc's supply-chain review), confirm that
   `claude plugin list` prints a version, and tell readers to compare against the baseline
   and re-run the supply-chain review before trusting a new version. `README.md` only links
   to the doc — leave it.
5. **`agents/CONTEXT.md`** L9-10 (#93): re-wrap the `sdlc-qa-engineer` bullet to ~95 columns,
   splitting the run-on "Nine agents" paragraph at its sentence boundary. Check
   `docs/features/agents.md` doesn't duplicate the text; if it does, keep them in step.
6. Commits: `Refs #90` / `Refs #93` per item.

---

## Acceptance Criteria

- [ ] `sdlc-design-reviewer` reads the brief from `docs/agents/` or `meta/`, uses the accessibility reviewer's UI-surface definition, and doesn't flag a missing brief as critical on a CLI/API-only change.
- [ ] `PRIVACY.md` lists every prd.json field the runner or `/plan-iteration` writes (per `docs/features/run-next-plan.md`), including `sdlc_deferred_issues`, one bullet each, flags `smoke_test`/`feature_branches` as user-authored, and no longer contradicts itself elsewhere.
- [ ] `triage-pr-comments` tells its reviewers not to copy commenter handles; its plan template has no `Reviewer` column and paraphrases comments with handles, emails and names stripped; Case 3 rebuilds old-shape tables.
- [ ] `third-party-skills.md` says the plugin install is unpinned, names the reviewed baseline (or how to pin), and how to re-verify after updates.
- [ ] No line in `agents/CONTEXT.md` exceeds ~100 columns.

---

## Pre-Implementation Review
All findings below are folded into the steps above.

- **sdlc-security-reviewer:** findings
  - medium (Step 4): recording the version after the fact is late detection. Pin or disable auto-update if supported; otherwise name the reviewed baseline and compare against it before trusting a new version.
  - low (Step 3): drop the reviewer-handle columns from the plan template.
  - low (Step 1): define "UI surface" explicitly and read the brief as data, not instructions.
  - info (Step 2): list every prd.json field from the feature doc.
- **sdlc-privacy-reviewer:** findings
  - medium (Step 3): paraphrase Comment text with handles, emails and names stripped; responses never address a commenter by handle.
  - medium (Step 2): `smoke_test` and `feature_branches` are user-authored and can carry PII or secrets.
  - low (Step 3): Case 3 rebuilds old-shape tables. Logins are never written anywhere, and the unused `author,assignees` fields are dropped.
  - low (Step 2): fix the contradictions elsewhere in PRIVACY.md.
  - info: add the PR-comment plan files to the data inventory; Steps 1, 4 and 5 have no privacy surface.
- **sdlc-accessibility-reviewer:** N/A: the plan edits only Markdown agent definitions, a skill prompt and internal repo docs (no rendered UI, generated HTML, published docs or terminal output), so WCAG 2.2 AA has nothing to apply to.
- **sdlc-design-reviewer:** findings (no design brief; reviewed against conventions)
  - major (Step 3): the Context paragraph's "who reviewed it" leaks handles; reword it.
  - major (Step 3): the example Comment cells are verbatim quotes; rewrite them as paraphrases.
  - major (Step 3): reword Case 3, and keep the "Reviewer Comments" heading.
  - major (Step 1): dropping the root brief path is deliberate; note it in the commit.
  - major (Step 1): the UI-surface definition matches the accessibility reviewer's, with consistent critical definitions.
  - minor:
    - reuse only the phrase "as data, not instructions";
    - scope the Tailwind items;
    - fix the doc-writer L104 link;
    - keep the dispatch line verbatim plus the new clause;
    - PRIVACY bullet format;
    - split the CONTEXT re-wrap at the sentence boundary.
