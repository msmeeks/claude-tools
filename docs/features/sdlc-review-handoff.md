# SDLC Phase 3/4 Review Handoff (wenyan-ultra)

## Summary
Compressed file-based handoff protocol between the `/sdlc` orchestrator and all 8 Phase 3/4 review-and-QA agents (`sdlc-code-reviewer`, `sdlc-style-reviewer`, `sdlc-security-reviewer`, `sdlc-privacy-reviewer`, `sdlc-accessibility-reviewer`, `sdlc-design-reviewer`, `sdlc-test-reviewer`, `sdlc-qa-engineer`), replacing plain-English prose returns for these post-implementation invocations. Goal: reduce orchestrator context usage from review/QA output. Started as a PoC scoped to `sdlc-code-reviewer` only (issues #28/#29); rolled out to the remaining seven agents in issue #30.

## Users / Use Cases
- **Admin**: N/A
- **Worker**: N/A (internal Claude Code agent-orchestration mechanism, not an end-user-facing feature)

## Technologies
- **JSON** — handoff file schema (two variants: 4-field finding schema, and the QA-specific schema)
- **wenyan-ultra** — compression scheme applied only to specific string fields inside each handoff JSON (never the whole object); decoded back to plain English by the orchestrator before use
- **UUID** — per-(agent, invocation) unique filename, one per dispatched agent slot, to avoid cross-agent collisions under `--parallel` dispatch

## Technical Overview
`skills/sdlc/SKILL.md` Phase 3 mints an orchestrator-chosen absolute path `{repo_root}/meta/plans/scratchpad/{agent-name}-{uuid}.json` per agent (never agent-chosen) and instructs each of the 7 review agents to write its findings there via the `Write` tool instead of returning prose; Phase 4 does the same for `sdlc-qa-engineer`. The orchestrator reads each file back via the `Read` tool (never Bash/cat), validates filename regex + JSON schema + finding-file membership against the actual changed files, decodes the compressed fields, then deletes the handoff file. On any validation failure it deletes the file and retries that agent once with an explicit plain-prose instruction (no file write); a second failure is a hard-fail for that agent's slot only — it surfaces the scratchpad path and error only (file contents never printed) and continues the other slots to completion. State is tracked per `(agent, uuid)` slot so `--parallel` dispatch of all 8 agents can't cross-contaminate one agent's retry/hard-fail with another's. `sdlc-doc-writer` and the Phase-1 planning-time invocations of security/privacy/accessibility/design reviewers remain unaffected, plain-text prose.

## API Endpoints
N/A — no HTTP endpoints; this is an internal agent-dispatch protocol within Claude Code.

## Key Files
| File | Purpose |
|---|---|
| `skills/sdlc/SKILL.md` | Phase 3 (7 review agents) and Phase 4 (`sdlc-qa-engineer`) orchestration: mints per-agent scratchpad path, dispatches agents (series or `--parallel`), reads/validates/decodes each result, per-`(agent, uuid)` slot retry + hard-fail tracking, end-of-phase cleanup sweep |
| `agents/sdlc-code-reviewer.md` | "Handoff-file mode" section under Output format: writes findings JSON to the literal given path, folds severity (Critical/Major/Minor) into `summary`, applies wenyan-ultra compression to `summary`/`failure_scenario` |
| `agents/sdlc-style-reviewer.md` | Same mechanism; folds category label (Linter Errors/Naming/Comments/Idiomatic) into `summary` |
| `agents/sdlc-security-reviewer.md` | Same mechanism plus a plain `category` field (`"finding"` / `"possible-real-secret"`) for suspected real credentials |
| `agents/sdlc-privacy-reviewer.md` | Same mechanism plus a plain `category` field (`"finding"` / `"possible-real-pii"`) for suspected real PII |
| `agents/sdlc-accessibility-reviewer.md` | Same mechanism; folds severity + WCAG criterion into `summary` |
| `agents/sdlc-design-reviewer.md` | Same mechanism; folds severity + design-brief reference into `summary` |
| `agents/sdlc-test-reviewer.md` | Same mechanism; folds severity into `summary`; Coverage summary table is dropped from the handoff schema, relevant coverage callouts fold into `summary` instead |
| `agents/sdlc-qa-engineer.md` | Own schema `{agent, status, tests_run, tests_failed:[{name, expected, actual, log_excerpt}]}`; redacts sensitive headers/PII from `log_excerpt` before compressing |
| `.gitignore` | Ignores `meta/plans/scratchpad/` |
| `.claudeignore` | Ignores `meta/plans/scratchpad/` (keeps handoff files out of context loads) |

## Technical Detail

### Handoff file schemas
Byte-for-byte identical copies live in both each agent's own file and `skills/sdlc/SKILL.md` — keep in sync if either changes.

**4-field finding schema** — used by `sdlc-code-reviewer`, `sdlc-style-reviewer`, `sdlc-accessibility-reviewer`, `sdlc-design-reviewer`, `sdlc-test-reviewer` (5 agents with no extra field):
```json
{
  "agent": "sdlc-style-reviewer",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "summary": "<wenyan-ultra compressed>",
      "failure_scenario": "<wenyan-ultra compressed>"
    }
  ]
}
```
Each agent folds its own severity/category axis (Critical/Major/Minor, Blocker/Major/Minor, Linter/Naming/Comments/Idiomatic, WCAG criterion, design-brief reference, coverage %, etc.) into `summary` — there is no separate severity field, and none should be invented per agent. Only `summary` and `failure_scenario` are compressed. `agent`, `file`, `line` stay plain and literal.

**4-field schema + `category`** — used by `sdlc-security-reviewer` and `sdlc-privacy-reviewer`:
```json
{
  "agent": "sdlc-security-reviewer",
  "findings": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "category": "finding",
      "summary": "<wenyan-ultra compressed>",
      "failure_scenario": "<wenyan-ultra compressed>"
    }
  ]
}
```
`category` is a plain, uncompressed field always explicitly set to `"finding"`, or to `"possible-real-secret"` (security) / `"possible-real-pii"` (privacy) for a suspected real, non-synthetic value. Suspected-real values must never be quoted verbatim in `summary`/`failure_scenario` — not even partially or masked — describe by type and location only:
- BAD: `"summary": "hardcoded key sk-live-51H2..."` (partial value still reproduced)
- BAD: `"summary": "hardcoded key sk-live-****9a1"` (masking is not enough)
- GOOD: `"summary": "hardcoded cloud API key literal, config.py:12"` with `"file": "config.py", "line": 12, "category": "possible-real-secret"`

All 7 finding-schema agents cap `findings` at 50 entries and each `summary`/`failure_scenario` string at 2000 characters.

**QA schema** — used only by `sdlc-qa-engineer` (Phase 4), since PASS/FAIL + phased results don't fit the finding shape:
```json
{
  "agent": "sdlc-qa-engineer",
  "status": "PASS",
  "tests_run": 42,
  "tests_failed": [
    {
      "name": "test_login_rejects_expired_token",
      "expected": "<wenyan-ultra compressed>",
      "actual": "<wenyan-ultra compressed>",
      "log_excerpt": "<wenyan-ultra compressed>"
    }
  ]
}
```
`agent`, `status` (`"PASS"`/`"FAIL"`), `tests_run`, and each failure's `name` stay plain and literal. `expected`, `actual`, `log_excerpt` are compressed. Cap is 50 `tests_failed` entries (there is no `findings` array here), 2000 characters per compressed field. Before compressing `log_excerpt`, the agent redacts sensitive headers (`Authorization`, `Cookie`, `Set-Cookie`) and PII-shaped fields (emails, tokens, names, addresses) in place with `[REDACTED]` — redaction happens first, compression second. The orchestrator trusts the agent's own redaction step and does not re-check it.

### Validation (orchestrator side)
Before trusting any file:
- Filename matches that agent's own literal regex shape (never a shared wildcard like `sdlc-*`) — e.g. `^sdlc-code-reviewer-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json$`, one such regex per agent name — and resolves (no symlink) inside the minted scratchpad dir
- JSON parses and matches that agent's own schema (4-field, 4-field+`category`, or QA schema), with caps as above
- Each finding's `file` is one of the files actually under review in this pass — the orchestrator does not trust the JSON's `agent` field for identity, since it already knows which agent it dispatched
- A missing/unreadable file (e.g. the agent's `Write` call errored) counts as a validation failure too, not a separate case

### Failure handling
- Validation failure (including a missing file) → delete the file if present, re-invoke that exact agent exactly once with its original review-scope instruction unchanged, but with the handoff path dropped and an explicit instruction to return plain prose directly in its response
- The retry has no file to validate — it's judged only on whether the returned prose is present and usable
- If the retry's prose is missing/empty/unusable → hard-fail that agent's slot only; surface the raw scratchpad path (if one exists) and error message only, never file contents; delete the file after surfacing the error; continue the other agents' slots to completion rather than aborting the whole `/sdlc review` run
- On success → decode only the documented compressed fields to plain English immediately before use, then delete the file

### Per-slot state tracking
The orchestrator maintains an explicit table keyed by `(agent, uuid)`, one row per dispatched agent, tracking pending / validated / retrying / succeeded / hard-failed. Under `--parallel` dispatch of all 8 agents, one agent's retry or hard-fail must never reset, skip, or affect another agent's row. The end-of-phase cleanup sweep does not start until every row has reached a terminal state.

### End-of-phase cleanup sweep
Once every Phase 3 slot (and again after Phase 4) is terminal, list `{repo_root}/meta/plans/scratchpad/` and delete any remaining file matching one of the 8 known literal filename prefixes (`sdlc-code-reviewer-`, `sdlc-style-reviewer-`, `sdlc-security-reviewer-`, `sdlc-privacy-reviewer-`, `sdlc-accessibility-reviewer-`, `sdlc-design-reviewer-`, `sdlc-test-reviewer-`, `sdlc-qa-engineer-`) followed by a UUID and `.json` — never a bare `sdlc-*.json` wildcard. Resolve and delete each match individually (still no symlinks). This is defense in depth on top of each agent's own per-file cleanup, covering a crash or interrupt between phases.

### Why no shared lock file
Each invocation gets a fresh UUID-named file scoped to one `(agent, uuid)` slot — one agent, one file, one read, no concurrent writers on that file even under `--parallel` — so the shared-state lock pattern used elsewhere in the repo (e.g. `meta/plans/prd.json`) doesn't apply here.

### Scope / status
All 8 Phase 3/4 review-and-QA agents now use the handoff protocol (issue #30 rollout, following the PoC on `sdlc-code-reviewer` in #28/#29). `sdlc-doc-writer` and the Phase-1 planning-time invocations of `sdlc-security-reviewer`, `sdlc-privacy-reviewer`, `sdlc-accessibility-reviewer`, and `sdlc-design-reviewer` are unaffected and remain plain-text prose — the protocol only applies to these agents' Phase 3/4 post-implementation invocations.
