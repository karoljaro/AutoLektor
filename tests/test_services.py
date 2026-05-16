from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from services.subtitle_service import SubtitleService
from services.video_service import VideoService
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


def test_video_service_creates_all_variants(monkeypatch) -> None:
    fake_ffmpeg = MagicMock()
    fake_ffmpeg.merge_videos = MagicMock()

    monkeypatch.setattr("services.video_service.FFmpegProvider", lambda: fake_ffmpeg)
    monkeypatch.setattr("services.video_service.file_exists", lambda path: True)

    service = VideoService()
    result = service.create_all_variants(
        source_video="video.mp4",
        dubbed_audio="audio.mp3",
        subtitles_file="subs.srt",
        output_paths={
            "full": "full.mp4",
            "dubbed": "dubbed.mp4",
            "subtitles_only": "subs_only.mp4",
        },
    )

    assert result is True
    assert fake_ffmpeg.merge_videos.call_count == 3
    fake_ffmpeg.merge_videos.assert_any_call("video.mp4", "audio.mp3", "subs.srt", "full.mp4", variant="full")
    fake_ffmpeg.merge_videos.assert_any_call("video.mp4", "audio.mp3", "subs.srt", "dubbed.mp4", variant="dubbed")
    fake_ffmpeg.merge_videos.assert_any_call("video.mp4", "audio.mp3", "subs.srt", "subs_only.mp4", variant="subtitles_only")


def test_video_service_returns_false_when_source_video_missing(monkeypatch) -> None:
    fake_ffmpeg = MagicMock()
    fake_ffmpeg.merge_videos = MagicMock()

    monkeypatch.setattr("services.video_service.FFmpegProvider", lambda: fake_ffmpeg)
    monkeypatch.setattr("services.video_service.file_exists", lambda path: False)

    service = VideoService()
    result = service.create_all_variants(
        source_video="missing.mp4",
        dubbed_audio="audio.mp3",
        subtitles_file="subs.srt",
        output_paths={"full": "full.mp4", "dubbed": "dubbed.mp4", "subtitles_only": "subs_only.mp4"},
    )

    assert result is False
    fake_ffmpeg.merge_videos.assert_not_called()




