#!/usr/bin/env python3
"""Asserts the wenyan-ultra handoff schema is identical everywhere it's duplicated.

The schema is copy-pasted (by design, for agent-file readability) into
skills/sdlc/SKILL.md, docs/features/sdlc-review-handoff.md, and each
agents/sdlc-*.md file. Nothing but a prose reminder keeps these in sync, so
this script extracts every fenced ```json schema block from those files,
classifies it by variant (plain 4-field / 4-field+category / QA), and
asserts all blocks of the same variant share the same key structure.
"""
import json
import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"```json\s*\n(.*?\n)```", re.DOTALL)

DEFAULT_SOURCE_FILES = [
    Path("skills/sdlc/SKILL.md"),
    Path("docs/features/sdlc-review-handoff.md"),
    Path("agents/sdlc-code-reviewer.md"),
    Path("agents/sdlc-style-reviewer.md"),
    Path("agents/sdlc-security-reviewer.md"),
    Path("agents/sdlc-privacy-reviewer.md"),
    Path("agents/sdlc-accessibility-reviewer.md"),
    Path("agents/sdlc-design-reviewer.md"),
    Path("agents/sdlc-test-reviewer.md"),
    Path("agents/sdlc-qa-engineer.md"),
]


def extract_schema_blocks(text):
    blocks = []
    for match in FENCE_RE.finditer(text):
        try:
            blocks.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return blocks


def _shape(value):
    """Structural shape of a JSON value: keys/nesting, ignoring literal content."""
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(v) for v in value]
    return type(value).__name__


def classify_variant(schema):
    if not isinstance(schema, dict):
        return None
    if "tests_failed" in schema:
        return "qa"
    if "findings" not in schema or not schema["findings"]:
        return None
    finding_keys = set(schema["findings"][0].keys())
    if "category" in finding_keys:
        return "finding_with_category"
    if {"file", "line", "summary", "failure_scenario"}.issubset(finding_keys):
        return "finding_plain"
    return None


def check_consistency(repo_root, source_files=None):
    source_files = source_files or DEFAULT_SOURCE_FILES
    repo_root = Path(repo_root)

    variant_shapes = {}  # variant -> (shape, first_file)
    errors = []

    for rel_path in source_files:
        full_path = repo_root / rel_path
        text = full_path.read_text()
        for schema in extract_schema_blocks(text):
            variant = classify_variant(schema)
            if variant is None:
                continue
            shape = _shape(schema)
            if variant not in variant_shapes:
                variant_shapes[variant] = (shape, str(rel_path))
                continue
            expected_shape, first_file = variant_shapes[variant]
            if shape != expected_shape:
                errors.append(
                    f"{rel_path} diverges from {first_file} for schema variant "
                    f"'{variant}': expected shape {expected_shape}, got {shape}"
                )

    return errors


def main():
    repo_root = Path(__file__).resolve().parent.parent
    errors = check_consistency(repo_root)
    if errors:
        print("SDLC handoff schema consistency check FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("SDLC handoff schema consistency check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
