"""Path validation utilities: canonicalize, suffix allowlist, anti-traversal."""

from __future__ import annotations

import os
from pathlib import Path

_MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mkv", ".avi"}
_DOC_SUFFIXES = {".md", ".txt", ".rst", ".html", ".json", ".yaml", ".yml"}


def sanitize_media_path(raw: str | Path) -> Path:
    """Resolve and validate a user-supplied media file path.

    Raises ValueError with a descriptive message on any violation.
    """
    return _validate(Path(raw), _MEDIA_SUFFIXES, label="media")


def sanitize_doc_path(raw: str | Path) -> Path:
    return _validate(Path(raw), _DOC_SUFFIXES, label="document")


def sanitize_output_dir(raw: str | Path) -> Path:
    """Resolve output directory; must be under home dir or cwd."""
    resolved = Path(raw).resolve()
    _assert_safe_root(resolved, label="output directory")
    return resolved


def safe_output_filename(name: str) -> str:
    """Return only the final path component with dangerous chars stripped."""
    stem = Path(name).name
    # strip leading dots, null bytes, path separators
    stem = stem.lstrip(".-").replace("\x00", "").replace("/", "").replace("\\", "")
    return stem or "output"


def _validate(path: Path, allowed_suffixes: set[str], label: str) -> Path:
    raw_str = str(path)
    if raw_str.startswith("-"):
        raise ValueError(f"{label} path must not start with '-': {raw_str!r}")
    if "\x00" in raw_str:
        raise ValueError(f"{label} path contains null byte")
    resolved = path.resolve()
    if not resolved.exists():
        raise ValueError(f"{label} path does not exist: {resolved}")
    if resolved.suffix.lower() not in allowed_suffixes:
        raise ValueError(
            f"{label} path has unsupported extension {resolved.suffix!r}. "
            f"Allowed: {sorted(allowed_suffixes)}"
        )
    _assert_safe_root(resolved, label=label)
    return resolved


def _assert_safe_root(path: Path, label: str) -> None:
    home = Path.home().resolve()
    cwd = Path.cwd().resolve()
    try:
        path.relative_to(home)
        return
    except ValueError:
        pass
    try:
        path.relative_to(cwd)
        return
    except ValueError:
        pass
    # Allow system temp dirs (/tmp symlinks to /private/var/... on macOS)
    tmpdir = Path(os.environ.get("TMPDIR", "/tmp")).resolve()
    if str(path).startswith(str(tmpdir)) or str(path).startswith("/tmp"):
        return
    raise ValueError(
        f"{label} path {path} is outside allowed roots (home directory, cwd, or /tmp)"
    )
