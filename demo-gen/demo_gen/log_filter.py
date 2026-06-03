"""Log filter that strips API payloads, base64 data, and file contents from all log records."""

from __future__ import annotations

import logging
import re

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),  # Anthropic API keys
    re.compile(r'"data"\s*:\s*"[A-Za-z0-9+/=]{100,}"'),  # base64 blobs in JSON
    re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+"),  # inline data URIs
    re.compile(r'"content"\s*:\s*\[.*?\]', re.DOTALL),  # API content arrays
    re.compile(r'"text"\s*:\s*"[^"]{500,}"'),  # long text values (file contents)
]
_REPLACEMENT = "[REDACTED]"


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern in _PATTERNS:
            msg = pattern.sub(_REPLACEMENT, msg)
        record.msg = msg
        record.args = ()
        return True


def install(logger: logging.Logger | None = None) -> None:
    """Install the filter on root logger (and optionally a named logger)."""
    root = logging.getLogger()
    root.addFilter(SensitiveDataFilter())
    if logger is not None:
        logger.addFilter(SensitiveDataFilter())
