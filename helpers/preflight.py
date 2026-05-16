"""Preflight checks for dependency validation, filesystem preparation and path escaping."""

from __future__ import annotations

from pathlib import Path
import shutil


def ensure_parent_dirs_exist(*file_paths: str) -> None:
    """Ensure parent directories for all provided file paths exist."""
    for file_path in file_paths:
        Path(file_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def ensure_commands_available(*commands: str) -> None:
    """Raise a clear error if any required system command is missing."""
    missing = [command for command in commands if shutil.which(str(command)) is None]
    if missing:
        raise RuntimeError(
            "Missing required system commands: " + ", ".join(missing) + ". "
            "Please install them and make sure they are available on PATH."
        )


def escape_ffmpeg_filter_path(file_path: str) -> str:
    """Escape a path so it can safely be embedded in an FFmpeg filter argument."""
    normalized = Path(file_path).expanduser().as_posix()
    return (
        normalized
        .replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace(",", r"\,")
    )

