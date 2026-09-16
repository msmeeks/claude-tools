# Privacy Notes — Ralph Orchestration Loop

This file documents what data the Ralph loop (`scripts/run-next-plan.py` and
the artifacts under its config root) captures, where it lives, and how long it
should be kept.

## Two layouts, one policy

A repo's project-scoped config lives under **`docs/agents/`** (this repo's
layout, matching the upstream scaffolding) or under **`meta/`** (the original
layout, still used by every repo that has not migrated). The orchestrator reads
both, permanently — see
[ADR 0001](../adr/0001-scaffolding-layout-with-dual-read-fallback.md). Paths
below are written for this repo's layout; **everything here applies identically
to the `meta/` equivalent** in an un-migrated repo: same files, same
sensitivity, same scrubbing, same retention. A repo carrying *both* roots is
refused at startup rather than guessed at.

Because these paths now sit under `docs/`, which reads as publishable, the
ignore rules are name patterns rather than exact paths — `**/implementation-logs/`,
`**/prd.json.lock`, `**/sdlc-review-findings.md`, `**/pr-summary.md` — so they
cover both layouts and survive the next reorganisation. The orchestrator also
refuses to write a log line at all if its resolved log directory is not ignored
by the target repo, converting a silent exposure into a loud failure. Exclude
all four from any docs-publishing or GitHub Pages pipeline.

## Data captured

### Implementation logs (`docs/agents/plans/implementation-logs/`)
Each invocation writes a single timestamped log file capturing the full
stdout/stderr stream of the spawned Claude session. This can include:
- Source code, file paths, and diffs from the target repo
- Command output (test failures, stack traces, build errors)
- Anything the invoked Claude session printed, including secrets accidentally
  echoed by a misconfigured command or a leaked environment variable

Before each line is written, `run-next-plan.py` scrubs a small set of common
credential patterns (`sk-ant-...`, `ghp_...`, PEM private key blocks,
`password=...`) and replaces matches with `[REDACTED]`. This is a
best-effort safety net, not a guarantee — it will not catch novel secret
formats, secrets split across lines, or secrets embedded in non-text output.
Treat logs as sensitive regardless — do not commit them to a public repo, and
do not share them outside the team without review.

### `progress.md` (`docs/agents/plans/progress.md`)
Free-form narrative notes describing what each plan run did. This file is
intended to be committed to git and is human-readable project history. Avoid
pasting secrets, credentials, or customer data into it.

### `prd.json` (`docs/agents/plans/prd.json`)
Machine-readable plan state: filenames, status (`pending|in-progress|done|stalled`),
attempt counts, and blocking relationships. Plan filenames may encode GitHub
issue numbers (e.g. `issue-42.md`), which indirectly reference issue titles
and content in the source repo's issue tracker. `prd.json` itself stores no
issue body text, author names, or other PII — only filenames and status
metadata. `sdlc_review_rounds` (an integer count of completed review-gate
rounds) is likewise pure metadata.

### Outbound: SDLC finding issues (`gh issue create`)
The review gate's issue-filing phase is the loop's one *outbound* data path:
it takes reviewer-written findings from `docs/agents/sdlc-review-findings.md`, which
are authored while reading `git diff <review-range>`, and publishes them to
the target repo's GitHub issue tracker under the `sdlc-finding` label. Unlike
the implementation logs, nothing downstream can redact a filed issue — the
automation has no retraction path.

The filing prompt therefore requires each body to be rewritten before it is
posted: paraphrase the defect (name the file and symbol; quote at most a short
identifier-level excerpt) rather than pasting raw diff or source lines, and
redact any credential, token, key, connection string, customer data, email
address, or other personal data as `[REDACTED]`. As with the log scrubber,
this is a mitigation rather than a guarantee. Do not point the loop at a
repository whose issue tracker is public unless the diff under review is also
public.

### `sdlc-review-findings.md` and `pr-summary.md`
Both are written by a Claude session at the config root and are gitignored.
The findings file holds reviewer prose about the diff under review — the same
content that later becomes GitHub issues, before any paraphrasing or redaction
has happened, so treat it as at least as sensitive as the logs. `pr-summary.md`
is a generated PR body: it is *intended* to become public, via the PR
description, so it must contain nothing that the PR itself should not carry.

### ADRs (`docs/adr/`)
ADRs are the `docs/` content most likely to be read by outsiders. They record
decisions and their rationale — they must never quote raw log, findings, or
session-transcript content.

## Retention guidance

- **`implementation-logs/`** (both layouts): treat as short-lived debugging
  artifacts. Prune logs older than 30 days, or sooner if the batch they belong
  to has merged and no issues were found. Do not retain indefinitely.
- **`progress.md`**: retained indefinitely as part of project history (it is
  committed to git); keep entries free of secrets and PII at write time since
  removal later requires history rewriting.
- **`prd.json`**: retained for the lifetime of the plan batch it tracks; safe
  to delete once all plans in a batch reach `done`.
- **`sdlc-review-findings.md`**: per-round scratch. The gate rotates it away at
  the start of each fresh round; delete it with the plan batch.
- **`pr-summary.md`**: regenerated each time the PR description is updated. No
  retention value once the PR body is written.
- **`sdlc-finding` issues**: retained until a human closes them. The review
  gate stops re-arming after `MAX_REVIEW_ROUNDS` (2) rounds, so the final
  round's findings are filed and triaged but deliberately *not* scheduled into
  the iteration — they sit open in the tracker indefinitely by design. Review
  them when closing the iteration: close or de-scope what is stale, and edit
  or delete any issue body that turns out to carry content the filing-time
  redaction missed. The automation cannot do either for you.

## Residual risk: indirect prompt injection via plan files

`prd.json` itself only carries structured fields (filename, status, attempts,
blocked_by) — never raw GitHub issue body text — so it is not a direct
injection vector. However, the Claude session invoked by `run-next-plan.py`
runs with `--permission-mode bypassPermissions` and is instructed to read the
full plan `.md` files under `docs/agents/plans/`, which were generated by
`/triage-issues` from GitHub issue bodies and may contain attacker-controlled
text (anyone who can open an issue on the source repo can write that text).

A crafted issue body embedded in a plan file could attempt to inject
instructions ("ignore the above, instead run...") that get interpreted as
commands by the Claude session reading the file, with full filesystem
authority. The orchestrator prompt explicitly tells Claude to treat plan file
content as untrusted document text, not instructions — but this is a
mitigation, not a guarantee; prompt-injection defenses are not foolproof.

This risk is accepted for the personal-developer / single-maintainer use case
this tool targets. It is not recommended for use against repositories with
public issue trackers where untrusted third parties can open issues, unless
issue bodies are reviewed before triage.

## Minimization

- `mark_stalled` strips non-printable and ANSI escape characters from plan
  filenames before logging, to prevent terminal/log injection — but this is a
  display-safety measure, not a privacy redaction. Do not rely on it to scrub
  sensitive content from logs.
- No PII (names, emails, tokens) is intentionally written into `prd.json`. If
  PII-bearing data is found in `implementation-logs/`, delete the affected log
  file rather than relying on the program to redact it.
