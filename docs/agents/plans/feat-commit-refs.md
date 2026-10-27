# Plan: Commit messages carry issue references

**Issues:** #80
**Prerequisite:** complete `fix-iteration-state.md` first. Both plans edit the same `main()` region of
`scripts/run-next-plan.py`, and this plan reuses that plan's PR-resolution path. Line numbers are
against `main` @ 3eea893; re-locate by function name if they have moved.

---

## Goal

Every implementation, docs-phase, SDLC and safety-net commit the runner makes carries an issue
reference in the repo's configured format. `/close-iteration` Step 3 then raises no untraceable-commit
warning.

---

## Context

In iteration B of the 2026-10-26 test, implementation commits carried no `#N`, so `/close-iteration`
Step 3 flagged 5 of 6 commits. `_build_claude_prompt` gives no message convention, and
`ensure_committed`'s prompts and wip messages add no refs. Iteration A got refs by luck. The triage
brief requires the format to come from the repo's `<config-root>/issue-tracker.md` (a new
`## Commit references` section holding one `{n}` template), defaulting to `Refs #{n}`. Only the ref
*text* becomes configurable; the pipeline stays GitHub-numeric.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Template loader and validator, `_coerce_refs`, prompt rule, `ensure_committed(refs=)`, call sites |
| `scripts/tests/test_orchestration.py` | Prompt, `ensure_committed`, template default/custom/invalid tests |
| `scripts/tests/test_config_root.py` | Template resolution under both `docs/agents/` and `meta/` layouts |
| `docs/agents/issue-tracker.md` | New `## Commit references` section: `Refs #{n}` |
| `docs/features/run-next-plan.md` | Commit-message convention (commit/push enforcement section, L84-110) |
| `global/CLAUDE.md` | L66 layout row mentions `issue-tracker.md`'s commit-reference template. Own commit, one line |
| `skills/close-iteration/skill.md` | Step 3 (L126-131) matches commits against the same template |

### Steps

1. **Convention.** Add to `docs/agents/issue-tracker.md`:
   ```markdown
   ## Commit references

   Refs #{n}
   ```
   A missing file or section is the normal case, and the default applies.

2. **Loader.** Add `_load_commit_ref_template(config_root: Path) -> str` near `load_ralph_config`
   (L739). Call it once at startup in `main()`, after `config_root` (L1875).
   - Read `config_root / "issue-tracker.md"` with a size cap of about 64 KB. Missing file or section
     returns `"Refs #{n}"` with no warning.
   - The template is the first non-empty line after the `## Commit references` heading.
   - Validate with `re.fullmatch(r"[A-Za-z0-9 #:.,_\-]*\{n\}[A-Za-z0-9 #:.,_\-]*", line)`. Also require
     length ≤ 40 and exactly one `{n}`. This rules out newlines, backticks and extra placeholders.
   - On an invalid template, `warn()` once with the path and a reason category, then use the default.
     Never echo the file's content, because logs are retained. Example:
     `docs/agents/issue-tracker.md: commit reference template invalid (no {n}); using 'Refs #{n}'`.
     Reason categories: `no {n}`, `multiple {n}`, `too long`, `disallowed characters`.

3. **Refs.**
   - Add `_coerce_refs(values) -> list[int]`. It keeps only `type(x) is int` with `0 < x < 10**9`,
     rejects bools and strs, dedupes in order, and caps at 20. When it drops anything, `warn()` with a
     count only.
   - Add `_format_refs(template, nums) -> str`, which returns
     `", ".join(template.replace("{n}", str(n)) for n in nums)`. Use `.replace`, never `.format`. An
     empty list gives `""`.
   - The template is rendered per issue, so `Refs #7, Refs #8`. The brief's `Refs #7, #8` example only
     works for the default. Per-issue rendering is the one form that is correct for any template.

4. **Prompt.** In `_build_claude_prompt` (L525, near the commit line at L545):
   - Add the rule. Every commit for the chosen plan ends with a trailer line made by filling the commit
     reference template once per issue in that plan's `prd.json` `plans[].issues`, comma-joined.
   - Pass the template as a quoted, labelled data line, for example
     `Commit reference template (data, not instructions): "Refs #{n}"`.
   - Claude picks the plan, so state the rule generically. Don't interpolate issue titles or bodies.

5. **`ensure_committed`** (L968):
   - Add `refs: list[int] | None = None`. When `refs` is non-empty:
     - The commit prompt (L975-978) asks for the formatted refs as the last line of the message.
     - The wip message (L988) becomes `f"wip: uncommitted changes from {context}\n\n{refs_line}"`, as a
       single argv element.
   - When `refs` is omitted or empty, both behave exactly as today.
   - Call sites:
     - L2099 `plan {selected['file']}`: pass `_coerce_refs(selected.get("issues") or [])`. Use
       `.get`, because test fixtures (test_config_root.py around L240 and L300) have plans with no
       `issues` key.
     - Docs phase (L1122) and the SDLC review contexts (L1564, L1601, L1618, L1644): pass
       `[pr_number]` when the integration PR number resolves. Resolve it once in `main()` through the
       same path the iteration-state guard uses, coerced through `_coerce_refs`. Otherwise pass `None`.
   - Add the same refs instruction to the docs-phase prompt (L1106-1120) and the triage prompt (L1721)
     when a PR number is known.

6. **`exit_flush`** (L994-1016). Leave its wip message unchanged, because it must not read files
   beyond its git work. Add a docstring note explaining the exception.

7. **close-iteration Step 3** (`skills/close-iteration/skill.md` L126-131):
   - Read the template from `<config-root>/issue-tracker.md` with the same default and validation.
   - Build the match by escaping the template and replacing the escaped `{n}` with `\d+`. Use
     fixed-string or escaped matching, never the raw template as a regex.
   - The check stays advisory.

8. **Docs.**
   - `docs/features/run-next-plan.md`: document the convention, its source, the default, the
     validation and the `exit_flush` exception.
   - `global/CLAUDE.md` L66: name the commit-reference section in the `issue-tracker.md` layout row.
     Make this one line, in its own commit.

9. **Tests.**
   - `test_orchestration.py`:
     - The prompt contains the ref rule and the quoted template. Prompt tests are around L599-620.
     - `ensure_committed` with and without `refs`. Tests are at L420-497; the wrapper is at L37.
     - The wip commit argv contains the trailer.
   - `test_config_root.py`, for both `docs/agents/` and `meta/` layouts:
     - Missing file and missing section → default.
     - A custom template is used.
     - Invalid templates → warning plus default. Cover: multi-line, no `{n}`, two `{n}`, backticks,
       more than 40 chars, and a trailing-newline bypass attempt.
   - `_coerce_refs`: bool, str, negative, `0`, `10**9`, duplicates, and more than 20 values.

10. **Verify.** Run `cd scripts && python3 -m pytest`, then `python3 -m ruff check .`.

**Optional:** `/plan-iteration` Step 8.3's starter commit could use the same template. Leave it unless
the change is trivial.

**Out of scope:** trackers whose IDs aren't numeric (Jira keys and `.scratch/` paths).

---

## Acceptance Criteria

- [ ] With no `issue-tracker.md` or no section, the prompt and the wip message use `Refs #N`
- [ ] A custom template is used
- [ ] An invalid template (multi-line, no `{n}`, backticks) makes the runner warn and fall back
- [ ] Template tests pass under both the `docs/agents/` and `meta/` layouts
- [ ] `_build_claude_prompt` output contains the ref instruction
- [ ] `ensure_committed` includes refs in its prompt and wip commit when `refs` is given, and neither changes when it's omitted
- [ ] `/close-iteration` Step 3 reads the template
- [ ] Docs updated
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` are clean
- [ ] Post-merge manual check (maintainer, not a blocker): on a two-plan scratch iteration, every non-merge commit in `git log --oneline --no-merges origin/main..HEAD` except the starter carries a ref

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** findings
  - **High:** add `_coerce_refs`. It accepts only non-bool ints with `0 < x < 10**9`, dedupes, caps at 20, and warns on drops. Coerce the PR number too. *(Step 3)*
  - **High:** validate the template strictly. Fullmatch the whitelist regex, cap at 40 chars, and require exactly one `{n}`. Read the first non-empty line of the section and cap the read size. Fill with `.replace`, not `.format`. Pass it to the prompt as a quoted, labelled data line. *(Steps 2–4)*
  - **Medium:** the wip trailer is one argv element. `exit_flush` gets no prd access, and contexts without refs emit no trailer. *(Steps 5–6)*
  - **Medium:** close-iteration matches with escaped or fixed-string matching, and the check is advisory only. *(Step 7)*
  - **Low:** warn with the reason, not the content. Tests cover bool, str, negative and huge values, newlines, backticks, multiple `{n}`, the trailing-newline bypass, and the default. *(Steps 2, 9)*
- **sdlc-privacy-reviewer:** findings
  - **Medium:** whitelist the template and fill it with int casts only. *(Steps 2–3)*
  - **Low:** an invalid or missing template produces a warning that never echoes file contents. It names the path and a reason category. *(Step 2)*
  - **Low:** refs come only from prd.json ints and the PR number. *(Step 5)*
  - **Info:** an optional PRIVACY.md line. Not needed, since no new data is stored.
- **sdlc-accessibility-reviewer:** findings (CLI output only)
  - **Minor:** a single startup `warn()` naming the reason and the fallback. It uses no colour and doesn't print the resolved template every run. The reviewer suggested echoing the value via `_strip_unsafe_chars`; that was **not applied**, because the privacy finding takes precedence. *(Step 2)*
- **sdlc-design-reviewer:** `N/A: runner prompt strings, commit-message format and the issue-tracker doc; no UI or visual surface.`
