# Triage Labels

The five canonical triage roles, mapped to the label strings this repo actually uses. Each
string equals its role name — no overrides.

| Role | Label | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate |
| `needs-info` | `needs-info` | Waiting on the reporter |
| `ready-for-agent` | `ready-for-agent` | Fully specified; an agent can pick it up with no human context |
| `ready-for-human` | `ready-for-human` | Needs human implementation |
| `wontfix` | `wontfix` | Will not be actioned |

One additional label, outside the state machine: **`sdlc-finding`** marks an issue filed by
the SDLC review gate rather than reported by a person. Findings deferred at the review-round
cap keep this label and stay open for a human to schedule — they are deliberately *not*
listed in `prd.json`'s `sdlc_finding_issues`, because the integration PR must not claim to
close findings nobody fixed.
