# Triage Labels

The six triage roles, mapped to the label strings this repo actually uses. Each
string equals its role name — no overrides.

| Role | Label | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate |
| `needs-info` | `needs-info` | Waiting on the reporter |
| `ready-for-agent` | `ready-for-agent` | Fully specified; an agent can pick it up with no human context |
| `ready-for-human` | `ready-for-human` | Needs human implementation |
| `later` | `later` | Valid, deliberately deferred; planning skips it until a person relabels it |
| `wontfix` | `wontfix` | Will not be actioned |

One additional label, outside the state machine: **`sdlc-finding`** marks an issue filed by
the SDLC review gate rather than reported by a person. Findings deferred at the review-round
cap keep this label and stay open for a human to schedule — they are deliberately *not*
listed in `prd.json`'s `sdlc_finding_issues`, because the integration PR must not claim to
close findings nobody fixed. They (and every finding filed as `later`, `ready-for-human` or
`needs-info`) are recorded in `sdlc_deferred_issues` instead, which `/close-iteration`
reconciles against and never turns into `Closes`.

`later` is the gate's middle outcome: a Major/Medium finding that is real but not urgent. The
bar, from `global/CLAUDE.md`: a bug to fix now → `ready-for-agent`; real but not urgent →
`later`; polish nobody would miss → don't file. `/plan-iteration` excludes `later` issues as
deferred, not untriaged.
