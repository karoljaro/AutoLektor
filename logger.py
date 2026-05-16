"""Central logger configuration for the project.

Use `from logger import get_logger` and then `logger = get_logger(__name__)`.
"""

from __future__ import annotations

import logging
import os
import sys

LOGGER_NAME = "autolektor"

_logger = logging.getLogger(LOGGER_NAME)
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)


def _resolve_log_level(default: str = "INFO") -> int:
    raw_level = os.getenv("AUTOLEKTOR_LOG_LEVEL", default).strip().upper()
    return getattr(logging, raw_level, logging.INFO)


# Default level can be adjusted by environment or later in code
_logger.setLevel(_resolve_log_level())


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return _logger

