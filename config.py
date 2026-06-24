"""Configuration settings for AutoLektor."""

from __future__ import annotations

import os


def env_str(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Voice settings
VOICE = env_str("AUTOLEKTOR_VOICE", "pl-PL-ZofiaNeural")

# Whisper model size
WHISPER_MODEL = env_str("AUTOLEKTOR_WHISPER_MODEL", "large-v3")

# Transcription language
TRANSCRIPTION_LANGUAGE = env_str("AUTOLEKTOR_TRANSCRIPTION_LANGUAGE", "pl")

# Text cleaning options
# If True, collapses all whitespace (newlines, tabs) into single spaces
# If False, preserves newlines as natural pauses for TTS
NORMALIZE_WHITESPACE = env_bool("AUTOLEKTOR_NORMALIZE_WHITESPACE", False)

# Video encoding settings
VIDEO_CODEC = env_str("AUTOLEKTOR_VIDEO_CODEC", "libx264")
AUDIO_CODEC = env_str("AUTOLEKTOR_AUDIO_CODEC", "aac")
