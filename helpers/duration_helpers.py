"""
Helper functions for getting file duration using ffprobe.
"""

import subprocess


def get_duration(file_path: str) -> float:
    """
    Use system ffprobe to measure file duration in seconds.

    Args:
        file_path: Path to the media file

    Returns:
        Duration in seconds (float)
    """
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "unknown ffprobe error").strip()
        raise RuntimeError(f"Could not read duration for '{file_path}': {details}") from exc

    return float(result.stdout.strip())
