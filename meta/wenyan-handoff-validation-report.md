# wenyan-ultra handoff validation report

Token/latency/drift comparison of baseline vs. wenyan-ultra-enabled sdlc review runs across a 5-PR corpus (claude-tools + bible-flashcards, both public repos). No raw diff content or PII/secret values are reproduced below — findings are summarized by category/count and referenced by PR number/URL/commit SHA only.

---

## PR corpus

- `claude-tools#12` — user-specified via --prs
- `claude-tools#16` — user-specified via --prs
- `bible-flashcards#62` — user-specified via --prs
- `bible-flashcards#61` — user-specified via --prs
- `bible-flashcards#54` — user-specified via --prs

---

## Per-PR results

### `claude-tools#12`

- baseline: tokens=82, latency_s=80.175
- wenyan: tokens=80, latency_s=90.799
- drift mismatches: 0
- ship (this PR independently): True

### `claude-tools#16`

- baseline: tokens=188, latency_s=48.573
- wenyan: tokens=251, latency_s=53.9
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#62`

- baseline: tokens=108, latency_s=36.861
- wenyan: tokens=20, latency_s=15.718
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#61`

- baseline: tokens=274, latency_s=40.326
- wenyan: tokens=209, latency_s=38.958
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#54`

- baseline: tokens=38, latency_s=69.439
- wenyan: tokens=150, latency_s=27.329
- drift mismatches: 0
- ship (this PR independently): True

---

## Verdict

**SHIP** — bar is 0 substantive drift mismatches on every PR independently (not corpus-averaged).

---

## Privacy note

Sourced from claude-tools and bible-flashcards (both public). No third-party production user data is reproduced verbatim in this report; any secret- or PII-shaped string surfaced during either run was redacted.
