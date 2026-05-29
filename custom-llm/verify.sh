#!/usr/bin/env bash
# verify.sh
#
# Smoke-test the running claude-code-router proxy and the configured backend.
# Run this in a second terminal while claude-byom is running.
#
# Usage:
#   ./verify.sh
#
# Requires: curl, python3 (for JSON parsing), ccr running (start via ./claude-byom <profile>)

set -euo pipefail

CCR_HOST="127.0.0.1"
CCR_PORT="${CCR_PORT:-3456}"
CCR_HOME="${CCR_HOME:-${HOME}/.claude-code-router}"
CCR_BASE="http://${CCR_HOST}:${CCR_PORT}"

# --- Check proxy is up ---
echo "=== Checking claude-code-router proxy ==="
if ! curl -fsS --max-time 3 "${CCR_BASE}/health" &>/dev/null; then
  echo "error: proxy not responding at ${CCR_BASE}" >&2
  echo "       Start it first: ./claude-byom <profile>" >&2
  exit 1
fi
echo "  proxy is up at ${CCR_BASE}"

# --- Show active config and read model for the canary call ---
CONFIG="${CCR_HOME}/config.json"
if [[ ! -f "${CONFIG}" ]]; then
  echo "error: no config found at ${CONFIG}" >&2
  exit 1
fi

PROVIDER=""
BASE_URL=""
MODEL=""
if command -v python3 &>/dev/null; then
  read -r PROVIDER BASE_URL MODEL < <(CCR_CONFIG="${CONFIG}" python3 - <<'PYEOF'
import json, os
d = json.load(open(os.environ["CCR_CONFIG"]))
provider = d["Providers"][0]["name"]
base_url = d["Providers"][0]["api_base_url"]
model    = d["Router"]["default"].split(",")[1]
print(provider, base_url, model)
PYEOF
  )
  echo "  provider : ${PROVIDER}"
  echo "  base_url : ${BASE_URL}"
  echo "  model    : ${MODEL}"
fi

# --- Send canary prompt using the configured default model ---
echo ""
echo "=== Sending canary prompt ==="

# Use the model from the active config so the router can match its routing rules.
CANARY_MODEL="${MODEL:-claude-3-5-sonnet-20241022}"

RESPONSE="$(curl -fsS --max-time 30 \
  -X POST "${CCR_BASE}/v1/messages" \
  -H "Content-Type: application/json" \
  -H "x-api-key: test" \
  -H "anthropic-version: 2023-06-01" \
  -d "{
    \"model\": \"${CANARY_MODEL}\",
    \"max_tokens\": 32,
    \"messages\": [{\"role\": \"user\", \"content\": \"Reply with only the single word: BACKEND_OK\"}]
  }" 2>&1)" || {
  echo "error: request to proxy failed:" >&2
  echo "  ${RESPONSE}" >&2
  exit 1
}

echo "  response (first 300 chars):"
echo "${RESPONSE}" | head -c 300
echo ""

if echo "${RESPONSE}" | grep -q "BACKEND_OK"; then
  echo ""
  echo "  PASS — backend responded correctly"
else
  echo ""
  echo "  WARN — response received but did not contain 'BACKEND_OK'"
  echo "         Check proxy logs below for routing errors."
fi

# --- Show recent logs if available ---
LOG_DIR="${CCR_HOME}/logs"
if [[ -d "${LOG_DIR}" ]] && ls "${LOG_DIR}"/*.log &>/dev/null 2>&1; then
  LATEST_LOG="$(ls -t "${LOG_DIR}"/*.log | head -1)"
  echo ""
  echo "=== Last 5 lines of ${LATEST_LOG} ==="
  tail -5 "${LATEST_LOG}"
fi
