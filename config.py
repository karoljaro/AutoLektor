"""
Configuration settings for the Video Automation project.
"""

# Text input file used by the script
TEXT_FILE = "Video/tekst.txt"

# Voice settings
VOICE = "pl-PL-ZofiaNeural"

# Working and output file names
POLISH_AUDIO_FILE = "Video/lektor_pl.mp3"
SUBTITLE_FILE = "Video/lektor_pl.srt"
SOURCE_VIDEO = "Video/wideo_angielskie.mp4"

# Output video names
VIDEO_DUBBED_WITH_SUBTITLES = "1_wideo_lektor_napisy.mp4"
VIDEO_DUBBED_ONLY = "2_wideo_tylko_lektor.mp4"
VIDEO_SUBTITLES_ONLY = "3_wideo_tylko_napisy.mp4"

# Whisper model size
WHISPER_MODEL = "base"

# Transcription language
TRANSCRIPTION_LANGUAGE = "pl"

# Video FPS
VIDEO_FPS = 30

# Video encoding settings
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
