# statusline

Configuration for [ccstatusline](https://github.com/sirmalloc/ccstatusline), the status line
Claude Code renders at the bottom of the terminal. `ccstatusline-settings.json` is the
committed configuration; `install.sh` places it where the CLI expects it.

## Language

**Status line**:
The single line the CLI renders showing model, context usage, branch, and cost. Configuration
only — no code of ours runs in it.
_Avoid_: prompt, header, bar

**Widget**:
One segment of the status line, enabled and ordered by the settings file.
_Avoid_: item, field

## Boundaries

- Settings only. Upgrading ccstatusline itself is outside this repo.
- The status line is cosmetic: nothing here may be load-bearing for any skill, agent, or the
  Ralph loop.
