"""Central logger configuration for the project.

Use `from logger import get_logger` and then `logger = get_logger(__name__)`.
"""
import logging
import sys

LOGGER_NAME = "autolektor"

_logger = logging.getLogger(LOGGER_NAME)
if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)

# Default level can be adjusted by environment or later in code
_logger.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return _logger

