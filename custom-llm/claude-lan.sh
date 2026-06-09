#!/usr/bin/env bash
# claude-lan.sh - Launch Claude locally against a LAN Anthropic endpoint.
#
# This script sets up the necessary environment variables and runs the
# Claude client with a default model. It supports optional flags to
# override the model or provide an arbitrary command for debugging.

set -euo pipefail

# Default values; can be overridden by env vars or -m flag
DEFAULT_BASE_URL="http://192.168.1.137:11434"
DEFAULT_AUTH_TOKEN="ollama"
DEFAULT_API_KEY="ollama"

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-$DEFAULT_BASE_URL}"
export ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-$DEFAULT_AUTH_TOKEN}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$DEFAULT_API_KEY}"

MODEL="gpt-oss:20b"

usage() {
  cat <<'EOF'
Usage: $(basename "$0") [-m MODEL] [command]

Options:
  -m MODEL   Override the default Claude model (default: gpt-oss:20b)
  -h         Show this help message

If a command is supplied, it will be executed with the environment
variables set above. Otherwise, the script runs:

    claude --model "$MODEL"
EOF
}

# Parse options
while getopts ":m:h" opt; do
  case "$opt" in
    m) MODEL="$OPTARG";;
    h) usage; exit 0;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage; exit 1;;
  esac
done

shift $((OPTIND-1))

# If a command is supplied, exec it.
if [[ $# -gt 0 ]]; then
  exec "$@"
fi

exec claude --model "$MODEL"
