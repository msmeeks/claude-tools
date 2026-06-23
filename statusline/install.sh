#!/usr/bin/env bash
# statusline/install.sh
#
# Installs ccstatusline (https://github.com/sirmalloc/ccstatusline) pinned to a
# known-good version, symlinks this repo's config into
# ~/.config/ccstatusline/settings.json, and points Claude Code's
# statusLine.command at the `ccstatusline` binary.
#
# Safe to re-run.
#
# Usage:
#   bash statusline/install.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CCSTATUSLINE_VERSION="2.2.22"
CONFIG_DIR="${HOME}/.config/ccstatusline"
CONFIG_DST="${CONFIG_DIR}/settings.json"
CONFIG_SRC="${REPO_DIR}/ccstatusline-settings.json"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"

echo "=== Installing ccstatusline@${CCSTATUSLINE_VERSION} ==="
npm install -g "ccstatusline@${CCSTATUSLINE_VERSION}"

echo ""
echo "=== Linking statusline config ==="
mkdir -p "$CONFIG_DIR"
if [[ -L "$CONFIG_DST" ]]; then
  echo "  skip   $CONFIG_DST (already a symlink)"
elif [[ -e "$CONFIG_DST" ]]; then
  echo "  backup $CONFIG_DST → ${CONFIG_DST}.bak"
  mv "$CONFIG_DST" "${CONFIG_DST}.bak"
  ln -s "$CONFIG_SRC" "$CONFIG_DST"
  echo "  linked $CONFIG_DST"
else
  ln -s "$CONFIG_SRC" "$CONFIG_DST"
  echo "  linked $CONFIG_DST"
fi

echo ""
echo "=== Pointing Claude Code at ccstatusline ==="
if [[ ! -f "$CLAUDE_SETTINGS" ]]; then
  mkdir -p "$(dirname "$CLAUDE_SETTINGS")"
  echo '{}' > "$CLAUDE_SETTINGS"
fi

tmp_settings="$(mktemp)"
jq '.statusLine = {"type": "command", "command": "ccstatusline"}' "$CLAUDE_SETTINGS" > "$tmp_settings"
mv "$tmp_settings" "$CLAUDE_SETTINGS"
echo "  set statusLine.command = \"ccstatusline\" in $CLAUDE_SETTINGS"

echo ""
echo "Done. Restart Claude Code (or open a new session) to see the new status line."
