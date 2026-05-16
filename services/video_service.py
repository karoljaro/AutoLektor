"""
Video Service - orchestrates video merging and rendering.
"""

from helpers import file_exists
from providers.ffmpeg_provider import FFmpegProvider


class VideoService:
    """Service for video operations (merging, rendering)."""

    def __init__(self) -> None:
        """Initialize Video Service."""
        self.ffmpeg = FFmpegProvider()

    def create_all_variants(
            self,
            source_video: str,
            dubbed_audio: str,
            subtitles_file: str,
            output_paths: dict[str, str],
    ) -> bool:
        """
        Create all three video variants.

        Args:
            source_video: Path to source video
            dubbed_audio: Path to dubbed audio
            subtitles_file: Path to SRT subtitles
            output_paths: Dict with keys "full", "dubbed", "subtitles_only"
        """
        print("\n[STEP 3/3] Rendering three video variants (FFmpeg)...")

        if not file_exists(source_video):
            print(f"-> [ERROR] Video not found: {source_video}")
            return False

        try:
            # Variant 1: Voiceover + Subtitles
            print("-> Rendering Variant 1: Voiceover + Subtitles (this will take the longest)...")
            self.ffmpeg.merge_videos(source_video, dubbed_audio, subtitles_file,
                                     output_paths["full"], variant="full")
            print(f"   [DONE] {output_paths['full']}")

            # Variant 2: Voiceover only
            print("-> Rendering Variant 2: Voiceover only (very fast!)...")
            self.ffmpeg.merge_videos(source_video, dubbed_audio, subtitles_file,
                                     output_paths["dubbed"], variant="dubbed")
            print(f"   [DONE] {output_paths['dubbed']}")

            # Variant 3: Subtitles only
            print("-> Rendering Variant 3: Subtitles only with the original audio...")
            self.ffmpeg.merge_videos(source_video, dubbed_audio, subtitles_file,
                                     output_paths["subtitles_only"], variant="subtitles_only")
            print(f"   [DONE] {output_paths['subtitles_only']}")

            print("\n[SUCCESS] All 3 video variants have been generated!")
            return True

        except (RuntimeError, ValueError, KeyError) as e:
            print(f"\n[FFmpeg ERROR] Something went wrong while merging the files: {e}")
            return False
