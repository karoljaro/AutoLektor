"""Configuration settings for AutoLektor."""

# Voice settings
VOICE = "pl-PL-ZofiaNeural"

# Whisper model size
WHISPER_MODEL = "large-v3"

# Transcription language
TRANSCRIPTION_LANGUAGE = "pl"

# Text cleaning options
# If True, collapses all whitespace (newlines, tabs) into single spaces
# If False, preserves newlines as natural pauses for TTS
NORMALIZE_WHITESPACE = False

# Video FPS
VIDEO_FPS = 30

# Video encoding settings
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
