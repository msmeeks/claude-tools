---
name: pr-image-upload
description: Upload local screenshots to a GitHub repo and return ready-to-paste markdown image tags. Works on both public and private repos. Use whenever you need to embed images in a PR body or comment via CLI — raw.githubusercontent.com URLs silently 404 on private repos.
---

# PR Image Upload

Uploads one or more local image files as GitHub release assets and prints `![alt](url)` markdown lines suitable for pasting into a PR body or comment. Works on public and private repos. Never use `raw.githubusercontent.com` for private repos — that always 404s.

## Usage

```
/pr-image-upload [PR_NUMBER] <image1> [image2 ...]
```

Examples:
```
/pr-image-upload 8 /tmp/shot1.png /tmp/shot2.png
/pr-image-upload /tmp/screenshot.png          (no PR prefix)
```

## How it works

Images are uploaded as assets on a single permanent `pr-assets` prerelease in the current repo. The resulting `releases/download` URLs are served by GitHub via cookie-session auth — identical behavior to drag-drop `user-attachments` images, but scriptable and stable. The `pr-assets` release is marked prerelease so it doesn't appear in user-facing release lists.

## Step 1 — Ensure the script is available

The canonical script lives at `~/.claude/skills/pr-image-upload/pr-image-upload.sh`. Run it directly from there — no need to copy it into each project.

```bash
SKILL_SCRIPT="${HOME}/.claude/skills/pr-image-upload/pr-image-upload.sh"
if [[ ! -f "$SKILL_SCRIPT" ]]; then
  echo "error: skill script not found at $SKILL_SCRIPT" >&2
  exit 1
fi
```

## Step 2 — Run the upload

Parse ARGUMENTS:
- First token that is all digits → PR number
- Remaining tokens → file paths

```bash
bash "${HOME}/.claude/skills/pr-image-upload/pr-image-upload.sh" <PR_NUMBER> <file1> [file2 ...]
```

Capture stdout. Each output line is a markdown image tag:
```
![qa-pr8-1week-default](https://github.com/owner/repo/releases/download/pr-assets/pr8-qa-pr8-1week-default.png)
```

## Step 3 — Verify the upload

```bash
gh release view pr-assets --repo <REPO> --json assets --jq '[.assets[].name]'
```

Confirm each uploaded filename appears in the asset list. If any is missing, re-run with `--clobber`.

## Step 4 — Return the markdown

Print the collected markdown lines to the user. They can be pasted directly into:
- `gh pr edit <N> --body "... ![alt](url) ..."`
- `gh pr comment <N> --body "... ![alt](url) ..."`
- Any PR body file passed to `gh pr create --body-file`

## Error handling

| Error | Fix |
|---|---|
| `error: could not determine repo` | Must be run from inside a git repository with a GitHub remote. `cd` to the repo first. |
| `gh release upload` fails on `--clobber` | Asset may be locked. Delete it first: `gh release delete-asset pr-assets <name> --repo <REPO> -y` |
| Image does not render in PR (shows broken tile) | Verify the URL format is `releases/download/pr-assets/<name>`, not `raw.githubusercontent.com`. The latter always 404s on private repos. |
| `gh: command not found` | GitHub CLI is not installed or not on PATH. Install from https://cli.github.com/ |

## Dependencies

- `gh` (GitHub CLI) — authenticated via `gh auth login`
- `bash` 3.2+ — pre-installed on macOS and Linux
- No other dependencies

## When NOT to use this skill

- **Public repos where you already have a working `raw.githubusercontent.com` URL** — that URL works fine; no need to change it.
- **When pasting an image directly in the GitHub web UI** — drag-drop produces `user-attachments` URLs that work without this script.
