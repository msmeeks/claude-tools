#!/usr/bin/env bash
# network/ssh-tunnel.sh
#
# Forward local port 11434 to an Ollama instance on a remote host via SSH.
# After the tunnel is up, point configs/ollama-cloud.local.json at
# http://127.0.0.1:11434/v1.
#
# Usage:
#   REMOTE_HOST=my-vm.example.com bash network/ssh-tunnel.sh
#
# Environment:
#   REMOTE_HOST   (required) hostname or IP of the remote Ollama host
#   REMOTE_USER   SSH username (default: $USER)
#   LOCAL_PORT    local port to bind (default: 11434)
#   REMOTE_PORT   remote port Ollama listens on (default: 11434)
#   SSH_KEY       path to SSH private key (optional; uses ssh-agent if unset)
#
# Requires: ssh, remote host accessible via SSH, Ollama running on the remote

set -euo pipefail

: "${REMOTE_HOST:?REMOTE_HOST is required (e.g. REMOTE_HOST=my-vm.example.com $0)}"
REMOTE_USER="${REMOTE_USER:-${USER}}"
LOCAL_PORT="${LOCAL_PORT:-11434}"
REMOTE_PORT="${REMOTE_PORT:-11434}"

# Validate REMOTE_HOST to prevent command injection
if [[ ! "${REMOTE_HOST}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
  echo "error: REMOTE_HOST contains invalid characters: ${REMOTE_HOST}" >&2
  exit 1
fi

if [[ ! "${REMOTE_USER}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
  echo "error: REMOTE_USER contains invalid characters: ${REMOTE_USER}" >&2
  exit 1
fi

if [[ "${LOCAL_PORT}" -lt 1 || "${LOCAL_PORT}" -gt 65535 ]]; then
  echo "error: LOCAL_PORT must be 1-65535" >&2
  exit 1
fi

if [[ "${REMOTE_PORT}" -lt 1 || "${REMOTE_PORT}" -gt 65535 ]]; then
  echo "error: REMOTE_PORT must be 1-65535" >&2
  exit 1
fi

key_args=()
if [[ -n "${SSH_KEY:-}" ]]; then
  [[ -f "${SSH_KEY}" ]] || { echo "error: SSH_KEY not found: ${SSH_KEY}" >&2; exit 1; }
  key_args=(-i "${SSH_KEY}")
fi

echo "=== SSH tunnel: localhost:${LOCAL_PORT} → ${REMOTE_HOST}:${REMOTE_PORT} ==="
echo "  Connect as: ${REMOTE_USER}@${REMOTE_HOST}"
echo "  Press Ctrl-C to close the tunnel."
echo ""
echo "  Once the tunnel is up, configure ollama-cloud.local.json:"
echo "    \"api_base_url\": \"http://127.0.0.1:${LOCAL_PORT}/v1\""
echo ""

exec ssh -N \
  -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
  "${key_args[@]}" \
  "${REMOTE_USER}@${REMOTE_HOST}"
