# Review gate running the branch's copy of the review skill

`run-next-plan.py`'s SDLC review gate always runs the **installed** copy of the configured
review skill. It does not load the skill's plugin from the repo under review, even when that
repo ships the plugin in `.claude-plugin/marketplace.json`.

## Why this is out of scope

The request only matters when the repo being iterated on is the plugin that contains the
review skill (for example, hd-tech-standards and `hd-standards:hd-code-review`). There, the
branch's changes to the skill don't run until after merge and sync. That gap is real, but
closing it inside the gate costs more than it buys:

- **The reviewer would grade its own change.** The gate's job is to review the code, not to
  test the reviewer. An in-progress or broken branch copy could crash the gate, or pass code
  that weakened the reviewer. A stable, installed reviewer is the correct judge.
- **The runner–skill contract can drift mid-branch.** The runner invokes the skill with fixed
  flags (`--range`, `--only`, `--report-only`, `--out`, `--registry`) and requires a
  `<reviewed>` sigil per reviewer. An iteration that changes that contract would break the
  gate partway through, with neither copy correct until the iteration lands.
- **Too much machinery for one repo.** Parsing the marketplace, validating `source` paths
  against escape and symlinks, and an unverified precedence question (does `--plugin-dir`
  beat an installed plugin of the same name?) all to serve essentially one repository.

Dogfooding a review skill belongs in the plugin's own repo: run
`claude --plugin-dir ./plugins/<plugin>` by hand, or add tests there.

If automatic dogfooding is ever wanted, the acceptable shape is an explicit opt-in in
`ralph.json` (for example a `review.plugin_dir` path), not auto-detection from the
marketplace. That would be a new request.

## Prior requests

- #100 — "run-next-plan: review gate uses the repo's own plugin when it ships one"
