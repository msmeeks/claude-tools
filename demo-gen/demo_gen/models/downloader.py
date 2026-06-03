"""Model weight downloader with SHA-256 checksum verification."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_MODELS_DIR = Path.home() / ".demo-gen" / "models"
_MANIFEST_PATH = Path(__file__).parent / "manifest.json"
_CHUNK_SIZE = 8192


def models_dir() -> Path:
    _MODELS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    return _MODELS_DIR


def load_manifest() -> dict:
    with _MANIFEST_PATH.open() as f:
        return json.load(f)


def is_downloaded(model_key: str) -> bool:
    manifest = load_manifest()
    if model_key not in manifest:
        return False
    entry = manifest[model_key]
    target = models_dir() / entry["local_path"]
    if not target.exists():
        return False
    if entry["sha256"] == "placeholder_update_before_use":
        return True  # Skip checksum for dev/placeholder entries
    return _verify_checksum(target, entry["sha256"])


def download(model_key: str, force: bool = False) -> Path:
    manifest = load_manifest()
    if model_key not in manifest:
        raise ValueError(f"Unknown model key: {model_key!r}. Available: {list(manifest)}")
    entry = manifest[model_key]
    target = models_dir() / entry["local_path"]

    if target.exists() and not force:
        if entry["sha256"] == "placeholder_update_before_use":
            logger.info("Model %s already downloaded (checksum not yet pinned)", model_key)
            return target
        if _verify_checksum(target, entry["sha256"]):
            logger.info("Model %s already downloaded and verified", model_key)
            return target
        logger.warning("Model %s checksum mismatch — re-downloading", model_key)
        target.unlink()

    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _download_file(entry["url"], target)

    if entry["sha256"] != "placeholder_update_before_use" and not _verify_checksum(target, entry["sha256"]):
        target.unlink()
        raise RuntimeError(
            f"SHA-256 checksum mismatch for {model_key}. "
            "The downloaded file may be corrupted or tampered with."
        )
    logger.info("Model %s downloaded and verified: %s", model_key, target)
    return target


def _download_file(url: str, target: Path) -> None:
    if not url.startswith("https://"):
        raise ValueError(f"Model URLs must use HTTPS. Got: {url!r}")
    logger.info("Downloading %s → %s", url, target)
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    tmp = target.with_suffix(".tmp")
    try:
        with tmp.open("wb") as f:
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                f.write(chunk)
        os.chmod(tmp, 0o600)
        tmp.rename(target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _verify_checksum(path: Path, expected: str) -> bool:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected:
        logger.warning("Checksum mismatch for %s: expected %s, got %s", path, expected, actual)
        return False
    return True
