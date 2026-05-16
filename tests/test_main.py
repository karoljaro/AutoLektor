from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import main


def test_initialize_services_creates_expected_container() -> None:
    services = main.initialize_services()

    assert hasattr(services, "voiceover")
    assert hasattr(services, "subtitles")
    assert hasattr(services, "video")
    assert services.voiceover.tts_provider.__class__.__name__ == "TTSProvider"
    assert services.subtitles.whisper_provider.__class__.__name__ == "WhisperProvider"


def test_main_runs_full_pipeline_when_text_is_present() -> None:
    voiceover = MagicMock()
    voiceover.create_and_adjust_voiceover = AsyncMock()

    subtitles = MagicMock()
    subtitles.generate_srt_from_audio = MagicMock()

    video = MagicMock()
    video.create_all_variants = MagicMock()

    fake_services = main.PipelineServices(voiceover=voiceover, subtitles=subtitles, video=video)

    with patch("main.initialize_services", return_value=fake_services), \
         patch("main.read_text_from_file", return_value="Hello world"):
        asyncio.run(main.main())

    voiceover.create_and_adjust_voiceover.assert_awaited_once_with(
        text="Hello world",
        source_video_path=main.SOURCE_VIDEO,
        output_audio_path=main.POLISH_AUDIO_FILE,
    )
    subtitles.generate_srt_from_audio.assert_called_once_with(
        audio_path=main.POLISH_AUDIO_FILE,
        output_srt_path=main.SUBTITLE_FILE,
        language=main.TRANSCRIPTION_LANGUAGE,
    )
    video.create_all_variants.assert_called_once_with(
        source_video=main.SOURCE_VIDEO,
        dubbed_audio=main.POLISH_AUDIO_FILE,
        subtitles_file=main.SUBTITLE_FILE,
        output_paths={
            "full": main.VIDEO_DUBBED_WITH_SUBTITLES,
            "dubbed": main.VIDEO_DUBBED_ONLY,
            "subtitles_only": main.VIDEO_SUBTITLES_ONLY,
        },
    )


def test_main_stops_when_text_is_missing() -> None:
    voiceover = MagicMock()
    voiceover.create_and_adjust_voiceover = AsyncMock()

    subtitles = MagicMock()
    subtitles.generate_srt_from_audio = MagicMock()

    video = MagicMock()
    video.create_all_variants = MagicMock()

    fake_services = main.PipelineServices(voiceover=voiceover, subtitles=subtitles, video=video)

    with patch("main.initialize_services", return_value=fake_services), \
         patch("main.read_text_from_file", return_value=None):
        asyncio.run(main.main())

    voiceover.create_and_adjust_voiceover.assert_not_called()
    subtitles.generate_srt_from_audio.assert_not_called()
    video.create_all_variants.assert_not_called()


