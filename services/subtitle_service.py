"""
Subtitle Service - orchestrates subtitle generation.
"""

from helpers.time_helpers import format_time


class SubtitleService:
    """Service for generating SRT subtitles from audio."""

    def __init__(self, whisper_provider) -> None:
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
        print("\n[STEP 2/3] Generating SRT subtitles from the voice track...")

        # Transcribe audio
        result = self.whisper_provider.transcribe(audio_path, language=language)
        segments = result.get("segments", [])

        print("-> Saving the SRT file...")

        # Write SRT file
        with open(output_srt_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(segments, start=1):
                start = format_time(segment["start"])
                end = format_time(segment["end"])
                text = segment["text"].strip()

                srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")

        print(f"-> Saved: {output_srt_path}")
