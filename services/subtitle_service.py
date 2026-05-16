"""
Subtitle Service - orchestrates subtitle generation.
"""

from helpers.time_helpers import format_time
from helpers.preflight import ensure_parent_dirs_exist
from providers.protocols import WhisperProtocol
from logger import get_logger

logger = get_logger(__name__)


class SubtitleService:
    """Service for generating SRT subtitles from audio."""

    def __init__(self, whisper_provider: WhisperProtocol) -> None:
        """
        Initialize Subtitle Service.

        Args:
            whisper_provider: Instance of WhisperProvider
        """
        self.whisper_provider = whisper_provider

    def generate_srt_from_audio(self, audio_path: str, output_srt_path: str, language: str = "pl") -> None:
        """
        Generate SRT subtitle file from audio.

        Args:
            audio_path: Path to audio file
            output_srt_path: Where to save the SRT file
            language: Language for transcription (default: "pl")
        """
        logger.info("\n[STEP 2/3] Generating SRT subtitles from the voice track...")

        # Transcribe audio
        result = self.whisper_provider.transcribe(audio_path, language=language)
        segments = result.get("segments", [])

        ensure_parent_dirs_exist(output_srt_path)

        if not isinstance(segments, list):
            raise TypeError("Whisper transcription result must contain a list under 'segments'")

        logger.info("-> Saving the SRT file...")

        # Write SRT file
        with open(output_srt_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(segments, start=1):
                start = format_time(segment["start"])
                end = format_time(segment["end"])
                text = segment["text"].strip()

                srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")

        logger.info("-> Saved: %s", output_srt_path)
