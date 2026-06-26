# Privacy Notes — Ralph Orchestration Loop

This file documents what data the Ralph loop (`scripts/run-next-plan.py` and
its `meta/plans/` artifacts) captures, where it lives, and how long it should
be kept.

## Data captured

### Implementation logs (`meta/plans/implementation-logs/`)
Each invocation writes a single timestamped log file capturing the full
stdout/stderr stream of the spawned Claude session. This can include:
- Source code, file paths, and diffs from the target repo
- Command output (test failures, stack traces, build errors)
- Anything the invoked Claude session printed, including secrets accidentally
  echoed by a misconfigured command or a leaked environment variable

These logs are **not** sanitized or redacted before being written to disk.
Treat them as sensitive — do not commit them to a public repo, and do not
share them outside the team without review.

### `progress.md`
Free-form narrative notes describing what each plan run did. This file is
intended to be committed to git and is human-readable project history. Avoid
pasting secrets, credentials, or customer data into it.

### `prd.json`
Machine-readable plan state: filenames, status (`pending|in-progress|done|stalled`),
attempt counts, and blocking relationships. Plan filenames may encode GitHub
issue numbers (e.g. `issue-42.md`), which indirectly reference issue titles
and content in the source repo's issue tracker. `prd.json` itself stores no
issue body text, author names, or other PII — only filenames and status
metadata.

## Retention guidance

- **`implementation-logs/`**: treat as short-lived debugging artifacts. Prune
  logs older than 30 days, or sooner if the batch they belong to has merged
  and no issues were found. Do not retain indefinitely.
- **`progress.md`**: retained indefinitely as part of project history (it is
  committed to git); keep entries free of secrets and PII at write time since
  removal later requires history rewriting.
- **`prd.json`**: retained for the lifetime of the plan batch it tracks; safe
  to delete once all plans in a batch reach `done`.

## Minimization

- `mark_stalled` strips non-printable and ANSI escape characters from plan
  filenames before logging, to prevent terminal/log injection — but this is a
  display-safety measure, not a privacy redaction. Do not rely on it to scrub
  sensitive content from logs.
- No PII (names, emails, tokens) is intentionally written into `prd.json`. If
  PII-bearing data is found in `implementation-logs/`, delete the affected log
  file rather than relying on the program to redact it.
