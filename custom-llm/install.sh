#!/usr/bin/env bash
# install.sh
#
# Bootstrap claude-code-router on this machine.
# Installs the ccr npm package if absent and seeds ~/.claude-code-router/config.json.
#
# Usage:
#   bash install.sh
#
# Requires: Node >= 18, npm, internet access for npm install

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CCR_HOME="${CCR_HOME:-${HOME}/.claude-code-router}"

# --- Node version check ---
if ! command -v node &>/dev/null; then
  echo "error: node not found. Install Node 18+ from https://nodejs.org" >&2
  exit 1
fi

node_major="$(node --version | sed 's/v\([0-9]*\).*/\1/')"
if [[ "$node_major" -lt 18 ]]; then
  echo "error: Node 18+ required (found $(node --version)). See https://nodejs.org" >&2
  exit 1
fi

# --- Install ccr ---
echo "=== Installing claude-code-router ==="
if command -v ccr &>/dev/null; then
  echo "  ccr already installed ($(ccr --version 2>/dev/null || echo 'version unknown'))"
else
  npm install -g @musistudio/claude-code-router
  echo "  installed: $(ccr --version 2>/dev/null || echo 'ok')"
fi

# --- Scaffold config dir ---
echo ""
echo "=== Scaffolding ${CCR_HOME} ==="
mkdir -p "${CCR_HOME}"

if [[ ! -f "${CCR_HOME}/config.json" ]]; then
  cp "${SCRIPT_DIR}/configs/ollama-lan.example.json" "${CCR_HOME}/config.json"
  chmod 600 "${CCR_HOME}/config.json"
  echo "  seeded config.json from ollama-lan.example.json (placeholder — edit before use)"
else
  echo "  config.json already exists — not overwritten"
fi

# Secure any existing *.local.json files in the configs dir
for f in "${SCRIPT_DIR}/configs"/*.local.json; do
  [[ -f "$f" ]] && chmod 600 "$f"
done

echo ""
echo "=== Done ==="
echo ""
echo "Next steps:"
echo "  1. Copy a config template and fill in your values:"
echo "       cp configs/ollama-lan.example.json configs/ollama-lan.local.json"
echo "       \$EDITOR configs/ollama-lan.local.json"
echo ""
echo "  2. Launch Claude Code via your chosen backend:"
echo "       ./claude-byom ollama-lan"
echo ""
echo "  3. Verify traffic is flowing:"
echo "       ./verify.sh  (in a second terminal while claude-byom is running)"
echo ""
echo "See README.md for networking options (Tailscale / SSH tunnel / Caddy)."
