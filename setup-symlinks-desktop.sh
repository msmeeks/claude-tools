#!/usr/bin/env bash
# setup-symlinks-desktop.sh
#
# Installs skills and agents from this repo into the Claude Desktop app.
#
# Skills:  symlinked into the Desktop app's skills-plugin directory, and
#          registered in the plugin's manifest.json so they appear in the UI.
# Agents:  symlinked into ~/.claude/agents/ (same location as Claude CLI).
# CLAUDE.md: symlinked to ~/.claude/CLAUDE.md (same as Claude CLI).
#
# Run once after cloning:
#   bash setup-symlinks-desktop.sh
#
# Safe to re-run; existing symlinks are skipped and manifest entries are
# updated in-place.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
DESKTOP_SUPPORT="${HOME}/Library/Application Support/Claude"
SKILLS_PLUGIN_ROOT="${DESKTOP_SUPPORT}/local-agent-mode-sessions/skills-plugin"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve a path to its canonical absolute form (handles relative symlinks).
# Uses python3 because `readlink -f` is not available on stock macOS.
realpath_of() {
  python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

link() {
  local src="$1"
  local dst="$2"
  if [[ -L "$dst" ]]; then
    # Compare resolved targets so symlinks created with relative paths still
    # match correctly and are skipped instead of being noisily re-linked.
    if [[ "$(realpath_of "$dst")" == "$(realpath_of "$src")" ]]; then
      echo "  skip   $dst (already linked to $src)"
    else
      local current
      current="$(readlink "$dst")"
      echo "  relink $dst ($current → $src)"
      # `ln -snf` atomically replaces a symlink (the -n flag prevents ln from
      # following an existing symlink-to-directory and writing inside it).
      ln -snf "$src" "$dst"
    fi
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

# Parse the 'description' field from a SKILL.md YAML frontmatter block.
# Handles multi-line values that use YAML block scalars (|, >) or simple
# single-line values.  Returns the value on stdout.
parse_skill_description() {
  local skill_md="$1"
  python3 - "$skill_md" <<'PYEOF'
import sys, re

path = sys.argv[1]
with open(path) as f:
    content = f.read()

# Extract frontmatter between first pair of ---
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if not m:
    print("")
    sys.exit(0)

fm = m.group(1)

# Find description line (may be multiline block scalar)
lines = fm.splitlines()
desc_lines = []
in_desc = False
indent = None

for i, line in enumerate(lines):
    if re.match(r'^description\s*:', line):
        # Check if rest of line has content
        rest = re.sub(r'^description\s*:\s*', '', line).strip()
        if rest and rest not in ('|', '>'):
            desc_lines.append(rest)
            break
        elif rest in ('|', '>'):
            # block scalar — collect indented lines below
            in_desc = True
        else:
            in_desc = True
        continue
    if in_desc:
        if line == '' or (indent is None and not line.startswith(' ')):
            if desc_lines:
                break
            continue
        if indent is None:
            indent = len(line) - len(line.lstrip())
        if line.startswith(' ' * indent):
            desc_lines.append(line.strip())
        else:
            break

print(' '.join(desc_lines))
PYEOF
}

# Find the single session directory inside skills-plugin.
# Structure: skills-plugin/<plugin-uuid>/<session-uuid>/
find_skills_session_dir() {
  if [[ ! -d "$SKILLS_PLUGIN_ROOT" ]]; then
    echo ""
    return
  fi
  # There should be exactly one plugin-uuid dir, and one session-uuid inside it.
  local plugin_uuid_dir
  plugin_uuid_dir="$(find "$SKILLS_PLUGIN_ROOT" -mindepth 1 -maxdepth 1 -type d | head -1)"
  if [[ -z "$plugin_uuid_dir" ]]; then
    echo ""
    return
  fi
  local session_uuid_dir
  session_uuid_dir="$(find "$plugin_uuid_dir" -mindepth 1 -maxdepth 1 -type d | head -1)"
  echo "$session_uuid_dir"
}

# Add or update a skill entry in manifest.json using Python.
upsert_manifest_entry() {
  local manifest="$1"
  local skill_id="$2"
  local skill_name="$3"
  local description="$4"

  python3 - "$manifest" "$skill_id" "$skill_name" "$description" <<'PYEOF'
import sys, json, datetime

manifest_path, skill_id, skill_name, description = sys.argv[1:]

with open(manifest_path) as f:
    data = json.load(f)

skills = data.get("skills", [])

# Find existing entry
existing = next((s for s in skills if s.get("skillId") == skill_id), None)

now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.") + "000000Z"

if existing:
    existing["name"] = skill_name
    existing["description"] = description
    existing["updatedAt"] = now_iso
    print(f"  updated manifest entry for {skill_id}")
else:
    skills.append({
        "skillId": skill_id,
        "name": skill_name,
        "description": description,
        "creatorType": "user",
        "updatedAt": now_iso,
        "enabled": True
    })
    print(f"  added   manifest entry for {skill_id}")

data["skills"] = skills
import time
data["lastUpdated"] = int(time.time() * 1000)

with open(manifest_path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

if [[ ! -d "$DESKTOP_SUPPORT" ]]; then
  echo "ERROR: Claude Desktop support directory not found at:"
  echo "  $DESKTOP_SUPPORT"
  echo "Is Claude Desktop installed?"
  exit 1
fi

SKILLS_SESSION_DIR="$(find_skills_session_dir)"
if [[ -z "$SKILLS_SESSION_DIR" ]]; then
  echo "ERROR: Could not find skills-plugin session directory under:"
  echo "  $SKILLS_PLUGIN_ROOT"
  echo "Open Claude Desktop at least once to initialize the skills plugin."
  exit 1
fi

SKILLS_DIR="${SKILLS_SESSION_DIR}/skills"
MANIFEST="${SKILLS_SESSION_DIR}/manifest.json"

mkdir -p "$SKILLS_DIR"
mkdir -p "${CLAUDE_DIR}/agents"

if [[ ! -f "$MANIFEST" ]]; then
  echo '{"lastUpdated":0,"skills":[]}' > "$MANIFEST"
fi

echo "Skills plugin dir: $SKILLS_SESSION_DIR"
echo ""

# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

echo "=== Linking skills ==="
for skill_dir in "$REPO_DIR/skills"/*/; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"
  skill_md="${skill_dir}SKILL.md"

  link "$skill_dir" "${SKILLS_DIR}/${skill_name}"

  if [[ -f "$skill_md" ]]; then
    description="$(parse_skill_description "$skill_md")"
    upsert_manifest_entry "$MANIFEST" "$skill_name" "$skill_name" "$description"
  else
    echo "  warn   no SKILL.md found in $skill_dir — manifest not updated"
  fi
done

# ---------------------------------------------------------------------------
# Agents  (same location as Claude CLI)
# ---------------------------------------------------------------------------

echo ""
echo "=== Linking agents ==="
for agent_file in "$REPO_DIR/agents"/*.md; do
  [[ -f "$agent_file" ]] || continue
  agent_name="$(basename "$agent_file")"
  link "$agent_file" "${CLAUDE_DIR}/agents/${agent_name}"
done

# ---------------------------------------------------------------------------
# Global CLAUDE.md  (same location as Claude CLI)
# ---------------------------------------------------------------------------

echo ""
echo "=== Linking global CLAUDE.md ==="
link "${REPO_DIR}/global/CLAUDE.md" "${CLAUDE_DIR}/CLAUDE.md"

echo ""
echo "Done."
echo ""
echo "Skills installed to: $SKILLS_DIR"
echo "Agents installed to: ${CLAUDE_DIR}/agents/"
echo "CLAUDE.md linked at: ${CLAUDE_DIR}/CLAUDE.md"
echo ""
echo "Restart Claude Desktop for skill changes to take effect."
