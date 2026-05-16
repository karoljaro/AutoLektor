"""
Helper functions for time formatting.
"""


def format_time(seconds):
    """
    Format seconds to SRT subtitle time format (HH:MM:SS,mmm).

    Args:
        seconds: Time in seconds (float)

    Returns:
        Formatted time string as HH:MM:SS,mmm
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    # Format as e.g. 00:00:03,500
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

