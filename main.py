import asyncio
import warnings
from dataclasses import dataclass

from config import (
    TEXT_FILE, VOICE, POLISH_AUDIO_FILE, SUBTITLE_FILE, SOURCE_VIDEO,
    VIDEO_DUBBED_WITH_SUBTITLES, VIDEO_DUBBED_ONLY, VIDEO_SUBTITLES_ONLY,
    WHISPER_MODEL, TRANSCRIPTION_LANGUAGE
)
from helpers import read_text_from_file
from providers.tts_provider import TTSProvider
from providers.whisper_provider import WhisperProvider
from services.subtitle_service import SubtitleService
from services.video_service import VideoService
from services.voiceover_service import VoiceoverService

# Suppress non-essential warnings
warnings.filterwarnings("ignore")


@dataclass(frozen=True)
class PipelineServices:
    """Typed container for initialized services."""

    voiceover: VoiceoverService
    subtitles: SubtitleService
    video: VideoService


# ==========================================
# INITIALIZATION
# ==========================================

def initialize_services() -> PipelineServices:
    """Initialize all services and providers."""
    # Providers
    tts_provider = TTSProvider(voice=VOICE)
    whisper_provider = WhisperProvider(model_name=WHISPER_MODEL)

    # Services
    voiceover_service = VoiceoverService(tts_provider)
    subtitle_service = SubtitleService(whisper_provider)
    video_service = VideoService()

    return PipelineServices(
        voiceover=voiceover_service,
        subtitles=subtitle_service,
        video=video_service,
    )


# ==========================================
# MAIN ORCHESTRATION
# ==========================================

async def main():
    """Main orchestration function."""
    print("=== VIDEO AUTOMATION START ===")

    # Initialize services
    services = initialize_services()

    # Step 0: Load text
    loaded_text = read_text_from_file(TEXT_FILE)

    if not loaded_text:
        print("=== PROCESS STOPPED ===")
        return

    # Step 1: Generate and adjust voiceover
    await services.voiceover.create_and_adjust_voiceover(
        text=loaded_text,
        source_video_path=SOURCE_VIDEO,
        output_audio_path=POLISH_AUDIO_FILE
    )

    # Step 2: Generate subtitles
    services.subtitles.generate_srt_from_audio(
        audio_path=POLISH_AUDIO_FILE,
        output_srt_path=SUBTITLE_FILE,
        language=TRANSCRIPTION_LANGUAGE
    )

    # Step 3: Create video variants
    output_paths = {
        "full": VIDEO_DUBBED_WITH_SUBTITLES,
        "dubbed": VIDEO_DUBBED_ONLY,
        "subtitles_only": VIDEO_SUBTITLES_ONLY
    }

    services.video.create_all_variants(
        source_video=SOURCE_VIDEO,
        dubbed_audio=POLISH_AUDIO_FILE,
        subtitles_file=SUBTITLE_FILE,
        output_paths=output_paths
    )

    print("=== END ===")


# Run the script
if __name__ == "__main__":
    asyncio.run(main())
