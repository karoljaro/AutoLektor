from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from services.subtitle_service import SubtitleService
from services.voiceover_service import VoiceoverService


def test_voiceover_service_adjusts_rate_when_audio_is_longer() -> None:
    async def run() -> None:
        tts_provider = MagicMock()
        tts_provider.generate_voiceover = AsyncMock()
        service = VoiceoverService(tts_provider)

        with patch("services.voiceover_service.file_exists", return_value=True), \
             patch("services.voiceover_service.get_duration", side_effect=[10.0, 12.0]):
            await service.create_and_adjust_voiceover("hello", "video.mp4", "audio.mp3")

        assert tts_provider.generate_voiceover.await_count == 2
        tts_provider.generate_voiceover.assert_any_await("hello", "audio.mp3")
        tts_provider.generate_voiceover.assert_any_await("hello", "audio.mp3", rate="+20%")

    asyncio.run(run())


def test_voiceover_service_raises_for_missing_source_video() -> None:
    async def run() -> None:
        tts_provider = MagicMock()
        tts_provider.generate_voiceover = AsyncMock()
        service = VoiceoverService(tts_provider)

        with patch("services.voiceover_service.file_exists", return_value=False):
            try:
                await service.create_and_adjust_voiceover("hello", "missing.mp4", "audio.mp3")
            except FileNotFoundError as exc:
                assert "Source video not found" in str(exc)
            else:
                raise AssertionError("Expected FileNotFoundError for missing source video")

    asyncio.run(run())


def test_subtitle_service_writes_srt_file(tmp_path: Path) -> None:
    whisper_provider = MagicMock()
    whisper_provider.transcribe.return_value = {
        "segments": [
            {"start": 0.0, "end": 1.2, "text": "Hello"},
            {"start": 1.2, "end": 2.5, "text": "world"},
        ]
    }

    service = SubtitleService(whisper_provider)
    output_path = tmp_path / "out.srt"

    service.generate_srt_from_audio("audio.mp3", str(output_path), language="pl")

    assert output_path.read_text(encoding="utf-8") == (
        "1\n00:00:00,000 --> 00:00:01,200\nHello\n\n"
        "2\n00:00:01,200 --> 00:00:02,500\nworld\n\n"
    )
    whisper_provider.transcribe.assert_called_once_with("audio.mp3", language="pl")


