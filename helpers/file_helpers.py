"""Helper functions for file operations."""

import os
from logger import get_logger

logger = get_logger(__name__)


def read_text_from_file(file_name: str) -> str | None:
    """Load and clean text from a file.

    Args:
        file_name: Path to the text file

    Returns:
        Cleaned text string or None if file does not exist or is empty
    """
    logger.info(f"\n[STEP 0/3] Loading text from file {file_name}...")
    if not os.path.exists(file_name):
        logger.error(f"-> [ERROR] File not found: {file_name}!")
        return None

    with open(file_name, "r", encoding="utf-8") as file_handle:
        text = file_handle.read()

    # Normalize whitespace to avoid accidental pauses in TTS.
    text = " ".join(text.split())

    if not text:
        logger.error(f"-> [ERROR] File {file_name} is empty!")
        return None

    logger.info("-> Text loaded and cleaned up from whitespace.")
    return text


def file_exists(file_path: str) -> bool:
    """Check if a file exists."""
    return os.path.exists(file_path)
