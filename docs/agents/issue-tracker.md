# Issue Tracker

Issues for this repo live in **GitHub Issues** on `msmeeks/claude-tools`, accessed with the
`gh` CLI.

- Create: `gh issue create --title "…" --body "…" --label "…"`
- Read: `gh issue list`, `gh issue view <n>`
- Comment: `gh issue comment <n> --body "…"`
- Close: `gh issue close <n> --comment "…"`

**External PRs are not a triage surface.** This is a personal configuration repo; `/triage`
processes issues only.

## Issues are outbound and public

`msmeeks/claude-tools` is public, and an issue cannot be retracted once filed. Anything filed
here — especially by the Ralph loop's automated finding-filing step, which runs unattended —
must be paraphrased rather than pasted: name the file and symbol, quote at most an
identifier-level excerpt, and redact any credential, token, key, connection string, email
address, or other personal data as `[REDACTED]`.

## Relationship to plans

`/plan-iteration` clusters `ready-for-agent` issues into plan files under
`docs/agents/plans/`, and each plan lists the issue numbers it closes. The Ralph loop reads
those numbers back out of the plan files to maintain the integration PR's `Closes` block — so
a plan's issue references are load-bearing, not decoration.
