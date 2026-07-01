# Plan: wenyan-ultra file handoff — proof of concept (sdlc-code-reviewer)

**Issues:** #28, #29

---

## Goal

`sdlc-code-reviewer` writes its findings to a scratchpad JSON handoff file (compressed via wenyan-ultra) instead of returning plain-text prose, and the sdlc orchestrator reads/decodes/translates that file into a correct `ReportFindings` call — proving the mechanism on one agent before extending it to the other 7.

---

## Context

The `sdlc` orchestrator (`skills/sdlc/SKILL.md`) currently dispatches 8 review agents via `Agent(...)` calls that return plain-English prose findings, which is token-expensive on every run since findings never need to be human-readable until the final surfaced report. Issue #28 is the parent PRD; #29 scopes a single-agent proof of concept: `sdlc-code-reviewer` writes `{scratchpad}/{agent-name}-{uuid}.json` per a schema mirroring `ReportFindings` (`{agent, findings:[{file,line,summary,failure_scenario}]}`), with only `summary`/`failure_scenario` compressed. The orchestrator decodes and translates back to plain English immediately before calling `ReportFindings`, with a retry-then-hard-fail path for malformed output.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `agents/sdlc-code-reviewer.md` | Add `Write` to the frontmatter `tools:` list (currently `Read, Glob, Grep, Bash` — no `Write`, but the agent must author the handoff file). Under the existing `## Output format` heading (not a new heading), add the handoff-file instructions: schema, compression rule, and the no-verbatim-PII/secrets rule (see below). |
| `skills/sdlc/SKILL.md` | In the Phase 3 `Agent(sdlc-code-reviewer): ...` line, change the invocation to pass a literal, orchestrator-minted absolute scratchpad path + UUID, instruct the agent to write findings there, and add orchestrator-side read/decode/validate/retry/hard-fail/cleanup logic. Add an inline PoC-scope callout so the asymmetry with the other 6 plain-text agents in the same list reads as intentional. |

### Steps

1. **Orchestrator mints the path, not the agent.** In `SKILL.md`, before dispatching `sdlc-code-reviewer`, generate a UUID and construct the full absolute scratchpad path (`{scratchpad}/sdlc-code-reviewer-{uuid}.json`). Pass this path into the agent's prompt as a fixed literal value the agent must write to — the agent must not construct its own filename or path.
2. **Restrict the write.** Add `Write` to `agents/sdlc-code-reviewer.md`'s tool grant so the agent authors the JSON via the `Write` tool, not `Bash`/heredoc (avoids shell-interpolation/injection risk from quoted code content).
3. **Define the schema and compression rule in `agents/sdlc-code-reviewer.md`** under `## Output format`: `{agent, findings:[{file,line,summary,failure_scenario}]}`, only `summary`/`failure_scenario` compressed in wenyan-ultra. Add an explicit rule with a BAD/GOOD example: findings must never quote verbatim secrets/PII found in reviewed code (including partial/masked/truncated reproductions) — reference by file:line and category only (e.g. `"category": "hardcoded API key"`).
4. **Orchestrator-side read/validate.** In `SKILL.md`, after dispatch: read the file via the `Read` tool (never `Bash`/`cat`, to avoid shell interpolation of model-derived content). Validate: filename matches an exact allow-list regex (`^sdlc-code-reviewer-[0-9a-f-]{36}\.json$`) resolved against the known scratchpad path (reject symlinks); JSON schema is well-formed (`agent`, `findings[]` with typed `file`/`line`/`summary`/`failure_scenario`, capped array length and string length); the in-file `agent` field matches the dispatched agent; each finding's `file` corresponds to a file that was actually in the reviewed changeset.
5. **Decode and translate.** Orchestrator translates compressed `summary`/`failure_scenario` to plain English only immediately before constructing the `ReportFindings` call.
6. **Retry/hard-fail.** If the file is missing, fails schema validation, or fails translation unambiguously: delete the malformed file, re-invoke `sdlc-code-reviewer` once with an explicit instruction to return plain English findings directly (no file write) for this retry. If that also fails or still looks suspect, hard-fail the run for this agent — surface the raw file path and an explicit error (do not print file contents), and do not guess a translation.
7. **Cleanup.** Delete the handoff file immediately after a successful `ReportFindings` call. On hard-fail, still delete/quarantine the file after surfacing the path (don't leave it indefinitely).
8. **Confirm `.claudeignore`/`.gitignore` cover the scratchpad root** so handoff files never land in git history.

---

## Acceptance Criteria

- [ ] `sdlc-code-reviewer` writes findings to a scratchpad JSON handoff file per the schema, with `summary`/`failure_scenario` in wenyan-ultra and no verbatim/partial PII or secret values
- [ ] Orchestrator reads the file via `Read` (not `Bash`), validates filename/schema/agent-field/file-membership, decodes, and produces a `ReportFindings` call with correct plain-English `summary`/`failure_scenario`
- [ ] Filenames are orchestrator-minted, uuid-suffixed, and collision-safe under a simulated retry (a fresh UUID per attempt, never reused)
- [ ] Injecting a malformed/garbled handoff file triggers exactly one plain-English retry of the agent
- [ ] A second consecutive failure hard-fails the run with a clear error referencing the raw file path, without printing file contents, rather than passing through a guessed translation
- [ ] Handoff file is deleted after successful `ReportFindings` and after a hard-fail (no orphaned files)
- [ ] No change to `ReportFindings`'s own schema

---

## Pre-Implementation Review

**Security:**
- Orchestrator (not the subagent) must mint the UUID/path and pass it as a literal value; the agent must not construct its own path (path-traversal risk if the model is prompt-injected via reviewed content).
- Use the `Write` tool for the agent's file authoring, not `Bash` (heredoc/shell-interpolation risk with code snippets containing quotes/backticks/`$()`).
- Strict filename allow-list regex validated against the resolved scratchpad path before read; reject symlinks; treat the file as untrusted input requiring full schema + size/length validation, not just "parses as JSON."
- Delete handoff files after use on both success and hard-fail paths; never leave them on disk indefinitely, and never print file contents in logs/errors — only the path.
- Cross-validate each finding's `file` against the actual reviewed changeset before it reaches `ReportFindings`.
- Do not rely on the in-file `agent` field for identity — compare against the orchestrator's own dispatch record.
- Keep this PoC's new instructions scoped textually to the `sdlc-code-reviewer` invocation only; don't let it bleed into the other 6 agents' shared Phase 3 block by copy-paste.

**Privacy:**
- Converting an ephemeral `Agent()` reply into a durable-ish scratchpad file is a new storage location for content that may quote PII/secrets found in reviewed code (test fixtures, hardcoded credentials, logged emails). Add an explicit, example-backed rule in `agents/sdlc-code-reviewer.md`: reference by category/location only, never literal or partially-masked values.
- Explicit file-deletion step required on both the success path and the hard-fail path (the hard-fail path as originally scoped only "surfaces the path," which would otherwise leave the file on disk indefinitely).

**Accessibility:** No WCAG-relevant surface (backend/orchestration only, no UI). Downstream note: ensure the final `ReportFindings` output reconstructs full, non-truncated plain English — compression must not leak into the human-facing surface.

**Design:**
- `agents/sdlc-code-reviewer.md` currently declares `tools: [Read, Glob, Grep, Bash]` — must add `Write` or the PoC fails at first write attempt.
- Add the new handoff instructions under the existing `## Output format` heading (not a new heading) so the doc's structural skeleton stays consistent with its 7 siblings, making future rollout (#30) a mechanical diff.
- Add a one-line note explaining why this uses per-invocation UUID-named files rather than reusing the existing `meta/plans/prd.json` shared-file + lock pattern (no shared-state merge needed here, so no lock required).
- Keep retry/hard-fail control flow documented only in `SKILL.md` (orchestrator-owned), not duplicated in the agent doc.
- Document the JSON schema identically (byte-for-byte) in both `SKILL.md` and `agents/sdlc-code-reviewer.md` to avoid the exact kind of drift this PoC is meant to prevent.
