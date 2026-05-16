"""
Helper functions for getting file duration using ffprobe.
"""

import subprocess


def get_duration(file_path):
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
    result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)
    return float(result.stdout.strip())

