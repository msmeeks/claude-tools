# SDLC Phase 3 Review Handoff (wenyan-ultra PoC)

## Summary
Proof of concept for a compressed file-based handoff between the `/sdlc` orchestrator and a single review agent (`sdlc-code-reviewer`), instead of that agent returning plain-English prose. Goal: reduce orchestrator context usage from review output. Scoped to one agent only; not yet rolled out to the other six Phase 3 review agents.

## Users / Use Cases
- **Admin**: N/A
- **Worker**: N/A (internal Claude Code agent-orchestration mechanism, not an end-user-facing feature)

## Technologies
- **JSON** — handoff file schema
- **wenyan-ultra** — compression scheme applied only to the `summary` and `failure_scenario` string fields inside the handoff JSON; decoded back to plain English by the orchestrator before use
- **UUID** — per-invocation unique filename to avoid any concurrent-writer/merge concerns (one agent, one file, one read — no lock needed)

## Technical Overview
`skills/sdlc/SKILL.md` Phase 3 mints an absolute path `{repo_root}/meta/plans/scratchpad/sdlc-code-reviewer-{uuid}.json` (orchestrator-minted, never agent-chosen) and instructs `sdlc-code-reviewer` to write its findings there via the `Write` tool instead of returning prose. The orchestrator reads the file back via the `Read` tool (never Bash/cat), validates filename regex + JSON schema + finding-file membership against the actual changed files, decodes the compressed fields, then deletes the handoff file. On any validation failure it deletes the file and retries once with an explicit plain-prose instruction (no file write); a second failure is a hard-fail that surfaces the scratchpad path and error only — file contents are never printed — and the file is still deleted. The other six Phase 3 review agents (style, security, privacy, accessibility, design, test) are unchanged and continue to return plain-English prose directly.

## API Endpoints
N/A — no HTTP endpoints; this is an internal agent-dispatch protocol within Claude Code.

## Key Files
| File | Purpose |
|---|---|
| `skills/sdlc/SKILL.md` | Phase 3 orchestration: mints scratchpad path, dispatches agent, reads/validates/decodes result, retry + hard-fail + delete logic |
| `agents/sdlc-code-reviewer.md` | "Handoff-file mode (PoC)" section under Output format: writes findings JSON to the literal given path, applies wenyan-ultra compression to `summary`/`failure_scenario`; on write failure it reports the failure in its response rather than retrying or falling back to prose itself — the orchestrator owns that decision |
| `.gitignore` | Ignores `meta/plans/scratchpad/` |
| `.claudeignore` | Ignores `meta/plans/scratchpad/` (keeps handoff files out of context loads) |

## Technical Detail

### Handoff file schema
Byte-for-byte identical copy lives in both `agents/sdlc-code-reviewer.md` and `skills/sdlc/SKILL.md` — keep in sync if either changes:
```json
{
  "agent": "sdlc-code-reviewer",
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
Only `summary` and `failure_scenario` are compressed. `agent`, `file`, `line` stay plain and literal. The agent must never quote verbatim secrets/PII in `summary` — reference by file:line and category only (e.g. `"hardcoded API key literal, config.py:12"`, not the key value).

### Validation (orchestrator side)
Before trusting the file:
- Filename matches a proper UUID shape — `^sdlc-code-reviewer-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json$` — and resolves (no symlink) inside the minted scratchpad dir
- JSON parses and matches the schema above, with `findings` capped at 50 entries and each `summary`/`failure_scenario` capped at 2000 characters
- Each finding's `file` is one of the files actually under review in this pass — the orchestrator does not trust the JSON's `agent` field for identity, since it already knows which agent it dispatched
- A missing/unreadable file (e.g. the agent's `Write` call errored) counts as a validation failure too, not a separate case

### Failure handling
- Validation failure (including a missing file) → delete the file if present, re-invoke `sdlc-code-reviewer` exactly once with an explicit instruction to return plain prose directly in its response (no file write, no scratchpad path given)
- The retry has no file to validate — it's judged only on whether the returned prose is present and usable
- If the retry's prose is missing/empty/unusable → hard-fail this agent's review; surface the raw scratchpad path (if one exists) and error message only, never file contents; delete the file after surfacing the error
- On success → decode wenyan-ultra fields to plain English immediately before use, then delete the file

### Why no lock file
Unlike `meta/plans/prd.json`, each invocation gets a fresh UUID-named file — one agent, one file, one read, no concurrent writers — so the shared-state lock pattern used elsewhere in the repo doesn't apply here.

### Scope / status
PoC covers `sdlc-code-reviewer` only. The remaining six Phase 3 review agents (style, security, privacy, accessibility, design, test) are unchanged. Rollout to those agents is tracked separately in `meta/plans/feat-wenyan-handoff-rollout.md` (not yet implemented).
