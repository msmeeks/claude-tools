#!/usr/bin/env bash
# ~/.claude/scripts/run-next-plan.sh
#
# Partner to the /triage-issues skill. Finds the next unfinished plan in
# meta/plans/README.md and runs a non-interactive Claude session to implement it.
# Reusable across any project that uses /triage-issues.
#
# Usage (run from inside any git repo with meta/plans/):
#   bash ~/.claude/scripts/run-next-plan.sh [options]
#
# Options:
#   --restart           Reset in-progress plan to pending and re-run
#   --skip-in-progress  Skip in-progress plan; pick next pending
#   --dry-run           Print selected plan and prompt; do not invoke Claude

set -euo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "ERROR: Not inside a git repository." >&2; exit 1; }

PLANS_DIR="${REPO_ROOT}/meta/plans"
README="${PLANS_DIR}/README.md"
LOGS_DIR="${PLANS_DIR}/implementation-logs"

# ── Flags ─────────────────────────────────────────────────────────────────────

RESTART=false
SKIP_IN_PROGRESS=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --restart)           RESTART=true ;;
    --skip-in-progress)  SKIP_IN_PROGRESS=true ;;
    --dry-run)           DRY_RUN=true ;;
    *) echo "ERROR: Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }
warn() { echo "WARN: $*" >&2; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }

# ── Preflight ─────────────────────────────────────────────────────────────────

require_cmd claude
require_cmd awk
require_cmd sed
require_cmd grep

[[ -d "$PLANS_DIR" ]] || die "Plans directory not found: $PLANS_DIR (run /triage-issues first)"
[[ -f "$README"    ]] || die "README not found: $README (run /triage-issues first)"

# ── Phase 1: Bootstrap (idempotent) ──────────────────────────────────────────

bootstrap_readme() {
  # Add | Status | column to README table if not already present
  grep -qE '^\| Plan.*Status' "$README" && return 0
  info "Bootstrapping Status column in README.md..."
  awk '
    /^\| Plan.*\| Size \|/  { print $0 " Status |"; next }
    /^\|[-]+\|[-]+\|[-]+\|[-]+\|[[:space:]]*$/ { print $0 "--------|"; next }
    /^\| \[/ { sub(/ \|[[:space:]]*$/, " | pending |"); print; next }
    { print }
  ' "$README" > "${README}.tmp" && mv "${README}.tmp" "$README"
}

bootstrap_plan_file() {
  local planfile="$1"
  # Add **Status:** pending after **Base:** if not present
  grep -q '^\*\*Status\*\*:' "$planfile" && return 0
  awk '
    /^\*\*Base:\*\*/ { print; print "**Status:** pending"; next }
    { print }
  ' "$planfile" > "${planfile}.tmp" && mv "${planfile}.tmp" "$planfile"
}

# ── Status helpers ────────────────────────────────────────────────────────────

get_plan_status() {
  local planfile="$1"
  grep -m1 '^\*\*Status\*\*:' "$planfile" 2>/dev/null \
    | sed 's/\*\*Status\*\*:[[:space:]]*//' \
    | tr -d '[:space:]' \
    || echo "pending"
}

set_plan_status() {
  local planfile="$1"
  local new_status="$2"
  sed -i '' "s/^\*\*Status\*\*:.*/**Status:** ${new_status}/" "$planfile"
}

set_readme_status() {
  local plan_filename="$1"
  local new_status="$2"
  local escaped
  escaped="$(printf '%s' "$plan_filename" | sed 's/\./\\./g')"
  sed -i '' "/($escaped)/{
    s/| pending |$/| ${new_status} |/
    s/| in-progress |$/| ${new_status} |/
    s/| done |$/| ${new_status} |/
  }" "$README"
}

get_plan_branch() {
  local planfile="$1"
  grep -m1 '^\*\*Branch:\*\*' "$planfile" \
    | sed "s/\*\*Branch:\*\*[[:space:]]*\`//;s/\`.*//"
}

# ── Run bootstrap ─────────────────────────────────────────────────────────────

bootstrap_readme

while IFS= read -r plan_file; do
  local_path="${PLANS_DIR}/${plan_file}"
  if [[ -f "$local_path" ]]; then
    bootstrap_plan_file "$local_path"
  else
    warn "Plan file referenced in README not found: ${plan_file}"
  fi
done < <(grep -E '^\| \[' "$README" | sed 's/.*(\([^)]*\.md\)).*/\1/')

# ── Rate-limit helpers (defined once) ────────────────────────────────────────

MAX_RETRIES=20
RETRY_WAIT_DEFAULT=60

is_rate_limited() {
  local logfile="$1"
  grep -qiE \
    'session.?limit|rate.?limit|usage.?limit|too many requests|overloaded|429|quota.?exceed|slowdown' \
    "$logfile" 2>/dev/null
}

parse_retry_after() {
  local logfile="$1"
  local delay_val reset_time today target_timestamp reset_val

  # 1. Look for standard numeric delay amounts (e.g., "retry after 60")
  delay_val=$(grep -ioE '(retry[- ]after[: ]+([0-9]+)|try again in ([0-9]+))' "$logfile" 2>/dev/null \
    | grep -oE '[0-9]+' | tail -1)

  # 2. Look for a specific reset time (e.g., "6:30pm")
  reset_time=$(grep -ioE 'resets [0-9]+:[0-9]+(am|pm)' "$logfile" 2>/dev/null | awk '{print $2}')

  if [ -n "$reset_time" ]; then
    # Grab today's date to give macOS date a complete timestamp context
    today=$(date "+%Y-%m-%d")

    # Parse the time using macOS/BSD flags (-j -f) under the NY timezone
    target_timestamp=$(TZ="America/New_York" date -j -f "%Y-%m-%d %I:%M%p" "$today $reset_time" "+%s" 2>/dev/null)

    if [ -n "$target_timestamp" ]; then
      reset_val=$(( target_timestamp - $(date "+%s") ))

      # If the reset time already passed today, assume it resets tomorrow (+86400 seconds)
      [ "$reset_val" -lt 0 ] && reset_val=$(( reset_val + 86400 ))
    fi
  fi

  # 3. Return the first non-null value found, otherwise use the default global
  echo "${delay_val:-${reset_val:-$RETRY_WAIT_DEFAULT}}"
}

# ── Phase 2-5: Loop over all pending plans ───────────────────────────────────

while true; do

TIMESTAMP="$(date +%Y_%m_%d_T%H_%M_%S)"
LOG_FILE="${LOGS_DIR}/run-next-plan-${TIMESTAMP}.log"

SELECTED_FILE=""
SELECTED_STATUS=""

while IFS= read -r plan_file; do
  planfile_path="${PLANS_DIR}/${plan_file}"

  if [[ ! -f "$planfile_path" ]]; then
    warn "Skipping missing plan file: ${plan_file}"
    continue
  fi

  status="$(get_plan_status "$planfile_path")"

  if [[ "$status" == "in-progress" && "$RESTART" == "true" ]]; then
    info "Resetting in-progress plan to pending: ${plan_file}"
    set_plan_status "$planfile_path" "pending"
    set_readme_status "$plan_file" "pending"
    status="pending"
  fi

  case "$status" in
    done)
      info "Skipping done: ${plan_file}"
      continue
      ;;
    in-progress)
      if [[ "$SKIP_IN_PROGRESS" == "true" ]]; then
        info "Skipping in-progress: ${plan_file}"
        continue
      fi
      info "Resuming in-progress: ${plan_file}"
      SELECTED_FILE="$plan_file"
      SELECTED_STATUS="in-progress"
      break
      ;;
    pending|*)
      info "Selected: ${plan_file}"
      SELECTED_FILE="$plan_file"
      SELECTED_STATUS="pending"
      break
      ;;
  esac
done < <(grep -E '^\| \[' "$README" | grep -v '| done |' | sed 's/.*(\([^)]*\.md\)).*/\1/')

if [[ -z "$SELECTED_FILE" ]]; then
  info "All plans done. Nothing to do."
  exit 0
fi

# ── Phase 3: Pre-flight ───────────────────────────────────────────────────────

PLAN_ABS_PATH="${PLANS_DIR}/${SELECTED_FILE}"
BRANCH="$(get_plan_branch "$PLAN_ABS_PATH")"

info "Plan:   ${SELECTED_FILE}"
info "Branch: ${BRANCH}"

mkdir -p "$LOGS_DIR"

# Mark in-progress before invoking Claude
set_plan_status "$PLAN_ABS_PATH" "in-progress"
set_readme_status "$SELECTED_FILE" "in-progress"

# ── Phase 4: Build Prompt ─────────────────────────────────────────────────────

CLAUDE_PROMPT="You are implementing a pre-written, self-contained plan.

1. Read docs/llms.md for project context
2. Read the full plan file: meta/plans/${SELECTED_FILE}
3. Execute the plan's Worktree Setup section exactly (git worktree add ...)
4. All code changes must be made inside the worktree working directory
5. Execute ALL Implementation Steps in the plan, in order
6. Address every item in the Pre-Implementation Review section (security, privacy, a11y, design)
7. Follow the plan's Review & Testing Workflow exactly — includes /sdlc, tests, Playwright, /pr-image-upload as written in the plan
8. After the PR is created successfully:
   - In meta/plans/${SELECTED_FILE}: change '**Status:** in-progress' to '**Status:** done'
   - In meta/plans/README.md: change the Status cell for ${SELECTED_FILE} from 'in-progress' to 'done'

SUBAGENTS: When spawning any Agent or sub-claude invocation, include in its prompt:
\"Use ultra-compressed caveman speech for all prose responses. Keep full technical accuracy.\"

Branch: ${BRANCH}
Repo root: ${REPO_ROOT}"

# ── Phase 5: Invoke (or dry-run) ─────────────────────────────────────────────

if [[ "$DRY_RUN" == "true" ]]; then
  echo ""
  echo "=== DRY RUN ==="
  echo "Selected plan: ${SELECTED_FILE}"
  echo "Branch:        ${BRANCH}"
  echo "Log would be:  ${LOG_FILE}"
  echo ""
  echo "Command:"
  echo "  claude -p <prompt> --permission-mode bypassPermissions --output-format text"
  echo ""
  echo "=== PROMPT ==="
  echo "$CLAUDE_PROMPT"
  echo "==============="
  # Revert in-progress back to pending since we're not actually running
  set_plan_status "$PLAN_ABS_PATH" "${SELECTED_STATUS}"
  set_readme_status "$SELECTED_FILE" "${SELECTED_STATUS}"
  exit 0
fi

info "Log: ${LOG_FILE}"
info "Invoking Claude..."
echo ""

cd "$REPO_ROOT"

# ── Rate-limit retry loop ─────────────────────────────────────────────────────

ATTEMPT=0
while true; do
  ATTEMPT=$((ATTEMPT + 1))
  ATTEMPT_LOG="${LOG_FILE%.log}-attempt${ATTEMPT}.log"

  set +e
  claude \
    -p "$CLAUDE_PROMPT" \
    --permission-mode bypassPermissions \
    --output-format text \
    2>&1 | tee "$ATTEMPT_LOG"
  CLAUDE_EXIT="${PIPESTATUS[0]}"
  set -e

  # Append attempt log to main log
  cat "$ATTEMPT_LOG" >> "$LOG_FILE"

  if [[ "$CLAUDE_EXIT" -eq 0 ]]; then
    echo ""
    info "Session complete (attempt ${ATTEMPT})."
    break
  fi

  if is_rate_limited "$ATTEMPT_LOG"; then
    if [[ "$ATTEMPT" -ge "$MAX_RETRIES" ]]; then
      echo ""
      warn "Rate-limited ${MAX_RETRIES} times in a row — giving up. Plan stays in-progress."
      break
    fi
    WAIT_SECS="$(parse_retry_after "$ATTEMPT_LOG")"
    echo ""
    warn "Usage limit hit (attempt ${ATTEMPT}/${MAX_RETRIES}). Waiting ${WAIT_SECS}s before retry..."
    sleep "$WAIT_SECS"
    info "Retrying..."
    echo ""
    continue
  fi

  # Non-rate-limit failure — don't retry
  echo ""
  warn "Claude exited with code ${CLAUDE_EXIT}. Plan stays in-progress — re-run to resume."
  break
done

if [[ "$CLAUDE_EXIT" -ne 0 ]]; then
  exit "$CLAUDE_EXIT"
fi

info "Plan complete. Looking for next plan..."
echo ""

done # end outer plan loop
