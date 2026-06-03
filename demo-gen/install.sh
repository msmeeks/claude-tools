#!/usr/bin/env bash
# install.sh — bootstrap demo-gen on this machine. Safe to re-run.
#
# Creates a Python 3.11 virtualenv at ./.venv if one is not already present,
# then runs `pip install -e '.[kokoro,dev]'`. The pip step re-resolves on
# every run; output is suppressed so a clean re-run is silent, but pip may
# legitimately upgrade pinned-loose dependencies — re-run with --verbose if
# you suspect something changed.
#
# Usage:
#   bash demo-gen/install.sh
#
# Requires: python3.11 on PATH (e.g. `brew install python@3.11`).

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if ! command -v python3.11 &>/dev/null; then
  echo "error: python3.11 required (brew install python@3.11)" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv with python3.11"
  python3.11 -m venv .venv
else
  echo ".venv already exists — reusing"
fi

echo "Upgrading pip"
.venv/bin/pip install --quiet --upgrade pip

echo "Installing demo-gen in editable mode (with kokoro + dev extras)"
.venv/bin/pip install --quiet -e '.[kokoro,dev]'

echo ""
echo "Done. Binary: $DIR/.venv/bin/demo-gen"
echo ""
echo "Optional: expose on PATH with"
echo "  ln -sf $DIR/.venv/bin/demo-gen ~/.local/bin/demo-gen"
