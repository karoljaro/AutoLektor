"""
Video Service - orchestrates video merging and rendering.
"""

from helpers import file_exists
from providers.ffmpeg_provider import FFmpegProvider
from logger import get_logger

logger = get_logger(__name__)


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
        logger.info("\n[STEP 3/3] Rendering three video variants (FFmpeg)...")

        if not file_exists(source_video):
            logger.error("-> [ERROR] Video not found: %s", source_video)
            return False

        try:
            # Variant 1: Voiceover + Subtitles
            logger.info("-> Rendering Variant 1: Voiceover + Subtitles (this will take the longest)...")
            self.ffmpeg.merge_videos(source_video, dubbed_audio, subtitles_file,
                                     output_paths["full"], variant="full")
            logger.info("   [DONE] %s", output_paths['full'])

            # Variant 2: Voiceover only
            logger.info("-> Rendering Variant 2: Voiceover only (very fast!)...")
            self.ffmpeg.merge_videos(source_video, dubbed_audio, subtitles_file,
                                     output_paths["dubbed"], variant="dubbed")
            logger.info("   [DONE] %s", output_paths['dubbed'])

            # Variant 3: Subtitles only
            logger.info("-> Rendering Variant 3: Subtitles only with the original audio...")
            self.ffmpeg.merge_videos(source_video, dubbed_audio, subtitles_file,
                                     output_paths["subtitles_only"], variant="subtitles_only")
            logger.info("   [DONE] %s", output_paths['subtitles_only'])

            logger.info("\n[SUCCESS] All 3 video variants have been generated!")
            return True

        except (RuntimeError, ValueError, KeyError) as e:
            logger.error("\n[FFmpeg ERROR] Something went wrong while merging the files: %s", e)
            return False
