# Plan: Ralph Loop — Docker Sandbox

**Issues:** #4
**Branch:** `feat/ralph-docker-sandbox`
**Base:** `main`
**Status:** done
**Prerequisite:** Branch off `main` after #3 merges.
**Status:** done

---

## Worktree Setup

```bash
# Run from the repo root — only after feat/ralph-orchestration-loop merges
git worktree add .claude/worktrees/claude-tools-ralph-docker -b feat/ralph-docker-sandbox main
```

**Working directory:** `.claude/worktrees/claude-tools-ralph-docker`

When the PR merges:
```bash
git worktree remove .claude/worktrees/claude-tools-ralph-docker
```

---

## Context

The Ralph loop runs Claude with `bypassPermissions` — safe for HITL but risky AFK because Claude has unrestricted access to the host filesystem. This slice adds optional Docker sandboxing: if a repo contains `meta/ralph.dockerfile`, the script builds and runs Claude inside a container with the full project toolchain. The repo is bind-mounted so changes land on disk immediately. Repos without a dockerfile get the existing behaviour unchanged.

---

## Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Add `build_run_command`, `get_image_tag`; wire into main loop |
| `scripts/tests/test_docker_sandbox.py` | New — pytest suite for `build_run_command` (no subprocess execution) |

---

## Implementation Steps

1. **Add `get_image_tag(repo_root: Path) -> str`** — derive image tag from repo slug. Sanitize: replace `/` with `-`, strip any character not in `[a-zA-Z0-9_.-]`, truncate to 128 chars. Result: `ralph-<sanitized-slug>:latest`. Never call `get_repo_slug()` subprocess in tests — accept `repo_slug` as a parameter.

2. **Add `build_run_command(repo_root: Path, dockerfile: Path, env: dict, claude_argv: list[str]) -> list[str]`**:
   - If `dockerfile` does not exist: return `claude_argv` unchanged (bare fallback)
   - Validate `dockerfile` is not a symlink (`os.path.islink`); die if it is
   - Validate `dockerfile.resolve()` starts with `repo_root.resolve()` (containment check)
   - Build image: `["docker", "build", "-f", str(dockerfile), "-t", get_image_tag(repo_root, repo_slug), str(repo_root)]` — only if dockerfile mtime > image creation time (skip rebuild otherwise; use `docker inspect` to get image created timestamp)
   - Return `docker run` argv: `["docker", "run", "--rm", "-v", f"{repo_root}:/workspace", "-w", "/workspace", "-e", "ANTHROPIC_API_KEY", "-e", "GITHUB_TOKEN", "-e", "GIT_AUTHOR_NAME", "-e", "GIT_AUTHOR_EMAIL"] + claude_argv`
   - Use `-e KEY` form (no `=VALUE`) — Docker reads value from calling process env; value never appears in argv

3. **Wire into `main()`**: detect `repo_root / "meta" / "ralph.dockerfile"`. Pass `dockerfile` to `build_run_command`. Pass result as the `Popen` argv. Update `--dry-run` to indicate Docker mode and print the full resolved argv.

4. **Update `.gitignore`** — add `.docker-image-cache/` if any local caching is introduced (likely none needed).

5. **Write `scripts/tests/test_docker_sandbox.py`** covering:
   - Returns bare `claude_argv` when dockerfile absent
   - Returns `docker run ...` argv when dockerfile present (use `tmp_path` to create a fake dockerfile)
   - `-e ANTHROPIC_API_KEY` present in argv (no `=` sign)
   - `-e GITHUB_TOKEN` present in argv (no `=` sign)
   - Repo bind-mount `-v <repo_root>:/workspace` present
   - `-w /workspace` present
   - Dies when dockerfile is a symlink
   - Dies when dockerfile resolves outside `repo_root`
   - Image tag contains no `/` and no invalid Docker tag characters
   - No subprocess calls in any test (patch `subprocess.run` and assert it is not called)

---

## Pre-Implementation Review

### Security

**CRITICAL — Credential values must not appear in log file**
Use `-e KEY` form (no `=VALUE`) in docker run argv. Never log the full docker run command with credential values. In `--dry-run`, print the argv but redact any credential env var values if they happen to be present.

**HIGH — Credentials visible in process list with `-e KEY=VALUE` form**
Enforced by using `-e KEY` form only. Covered by test case asserting no `=` in credential flags.

**HIGH — Bind mount grants write access to `.git/hooks/`**
This is a known limitation of full-repo bind mounts. Document it explicitly in the `meta/ralph.dockerfile` template and in `--dry-run` output. Accept the risk for personal developer use; note that a production-grade mitigation would mount individual subdirectories and exclude `.git/`.

**MEDIUM — Repo slug slash produces registry-namespaced Docker tag**
`get_image_tag` replaces `/` with `-` before constructing the tag. Covered by test case.

**MEDIUM — Dockerfile symlink following**
`build_run_command` calls `os.path.islink(dockerfile)` and dies if true. Covered by test case.

**INFO — Docker build stdout captured to log**
Docker build output goes to the same log as Claude stdout. Accept for personal developer use; note that `RUN printenv` in the dockerfile could expose build args in logs — do not use build args for secrets.

---

## Review & Testing Workflow

### 1. Run tests and lint
```bash
cd scripts && python3 -m pytest && python3 -m ruff check .
```

### 2. Smoke test Docker detection
```bash
# In a repo WITH meta/ralph.dockerfile
python3 ~/.claude/scripts/run-next-plan.py --dry-run
# Verify: output shows "Docker mode: YES" and docker run command with -e KEY (no =VALUE)

# In a repo WITHOUT meta/ralph.dockerfile
python3 ~/.claude/scripts/run-next-plan.py --dry-run
# Verify: output shows "Docker mode: NO" and bare claude command
```

### 3. Push branch and open PR
```bash
git push -u origin feat/ralph-docker-sandbox
gh pr create --base main --title "feat: Docker sandbox for Ralph loop" --body "Closes #4"
```

---

## Verification Checklist

- [ ] `python3 -m pytest` passes (including no-subprocess assertion)
- [ ] `python3 -m ruff check scripts/` passes
- [ ] `-e KEY` form used (no `=VALUE` in credential argv items)
- [ ] Symlink dockerfile rejected (test case passes)
- [ ] Image tag contains no `/` (test case passes)
- [ ] `--dry-run` indicates Docker mode and prints full argv
- [ ] Fallback to bare `claude` when no dockerfile (test case passes)
