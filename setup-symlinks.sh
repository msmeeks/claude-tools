#!/usr/bin/env bash
# setup-symlinks.sh
#
# Replaces the real files in ~/.claude/skills/ and ~/.claude/agents/ with
# symlinks back into this repo so edits here take effect immediately in
# Claude Code — no copy step needed.
#
# Run once after cloning:
#   bash setup-symlinks.sh
#
# Safe to re-run; existing symlinks are skipped.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"

link() {
  local src="$1"
  local dst="$2"
  if [[ -L "$dst" ]]; then
    echo "  skip  $dst (already a symlink)"
  elif [[ -e "$dst" ]]; then
    echo "  backup $dst → ${dst}.bak"
    mv "$dst" "${dst}.bak"
    ln -s "$src" "$dst"
    echo "  linked $dst"
  else
    ln -s "$src" "$dst"
    echo "  linked $dst"
  fi
}

echo "=== Linking skills ==="
for skill_dir in "$REPO_DIR/skills"/*/; do
  skill_name="$(basename "$skill_dir")"
  link "$skill_dir" "${CLAUDE_DIR}/skills/${skill_name}"
done

echo ""
echo "=== Linking agents ==="
for agent_file in "$REPO_DIR/agents"/*.md; do
  agent_name="$(basename "$agent_file")"
  link "$agent_file" "${CLAUDE_DIR}/agents/${agent_name}"
done

echo ""
echo "=== Linking global CLAUDE.md ==="
link "${REPO_DIR}/global/CLAUDE.md" "${CLAUDE_DIR}/CLAUDE.md"

echo ""
echo "Done. Edit files in $REPO_DIR — changes are live immediately."
