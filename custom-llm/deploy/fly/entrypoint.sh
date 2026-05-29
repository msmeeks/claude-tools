#!/usr/bin/env bash
# entrypoint.sh
#
# Start Ollama and Caddy; forward SIGTERM/SIGINT to both.
# If either process exits unexpectedly, the container exits so the
# orchestrator can restart it.
#
# Requires: CADDY_BASIC_AUTH_HASH env var (set via fly secrets set)
# Requires: ollama and caddy on PATH (provided by Dockerfile)

set -euo pipefail

if [[ -z "${CADDY_BASIC_AUTH_HASH:-}" ]]; then
  echo "error: CADDY_BASIC_AUTH_HASH is not set" >&2
  echo "       Set it via: fly secrets set CADDY_BASIC_AUTH_HASH='<hash>'" >&2
  exit 1
fi

ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready before accepting proxied requests
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 1
done

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

trap 'kill "${OLLAMA_PID}" "${CADDY_PID}" 2>/dev/null; wait' SIGTERM SIGINT

# Exit if either child dies so the orchestrator restarts the container
wait -n "${OLLAMA_PID}" "${CADDY_PID}" 2>/dev/null || true
kill "${OLLAMA_PID}" "${CADDY_PID}" 2>/dev/null
wait
exit 1
