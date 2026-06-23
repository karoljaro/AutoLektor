from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from api import app, health, render


class FakeUpload:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.was_read = False

    async def read(self, size: int) -> bytes:
        if self.was_read:
            return b""
        self.was_read = True
        return self.content


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_render_route_is_registered() -> None:
    assert any(route.path == "/render" and "POST" in route.methods for route in app.routes)


def test_render_voiceover_returns_mp3(monkeypatch) -> None:
    calls = []

    class FakeVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            calls.append((text, Path(source_video_path).read_bytes()))
            Path(output_audio_path).write_bytes(b"fake mp3")

    monkeypatch.setattr("api.TTSProvider", lambda voice: object())
    monkeypatch.setattr("api.VoiceoverService", FakeVoiceoverService)

    async def run_test() -> None:
        response = await render(
            video=FakeUpload(b"fake video"),
            text="  Test lektora  ",
            variant="voiceover",
        )

        try:
            assert response.status_code == 200
            assert response.media_type == "audio/mpeg"
            assert Path(response.path).read_bytes() == b"fake mp3"
        finally:
            await response.background()

    asyncio.run(run_test())
    assert calls == [("Test lektora", b"fake video")]


def test_render_subtitles_returns_srt(monkeypatch) -> None:
    calls = []

    class FakeVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            calls.append(("voiceover", text, Path(source_video_path).read_bytes()))
            Path(output_audio_path).write_bytes(b"fake mp3")

    class FakeSubtitleService:
        def __init__(self, whisper_provider) -> None:
            self.whisper_provider = whisper_provider

        def generate_srt_from_audio(self, audio_path, output_srt_path, language="pl") -> None:
            calls.append(("subtitles", Path(audio_path).read_bytes(), language))
            Path(output_srt_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nTest\n\n", encoding="utf-8")

    monkeypatch.setattr("api.TTSProvider", lambda voice: object())
    monkeypatch.setattr("api.WhisperProvider", lambda model_name: object())
    monkeypatch.setattr("api.VoiceoverService", FakeVoiceoverService)
    monkeypatch.setattr("api.SubtitleService", FakeSubtitleService)

    async def run_test() -> None:
        response = await render(
            video=FakeUpload(b"fake video"),
            text="Test napisow",
            variant="subtitles",
        )

        try:
            assert response.status_code == 200
            assert response.media_type == "application/x-subrip"
            assert Path(response.path).read_text(encoding="utf-8").startswith("1\n00:00:00,000")
        finally:
            await response.background()

    asyncio.run(run_test())
    assert calls == [
        ("voiceover", "Test napisow", b"fake video"),
        ("subtitles", b"fake mp3", "pl"),
    ]


def test_render_dubbed_returns_mp4(monkeypatch) -> None:
    calls = []

    class FakeVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            calls.append(("voiceover", text, Path(source_video_path).read_bytes()))
            Path(output_audio_path).write_bytes(b"fake mp3")

    def fake_merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full") -> None:
        calls.append((
            "ffmpeg",
            Path(source_video).read_bytes(),
            Path(dubbed_audio).read_bytes(),
            subtitles_file.endswith("subtitles.srt"),
            variant,
        ))
        Path(output_path).write_bytes(b"fake mp4")

    monkeypatch.setattr("api.TTSProvider", lambda voice: object())
    monkeypatch.setattr("api.VoiceoverService", FakeVoiceoverService)
    monkeypatch.setattr("api.FFmpegProvider.merge_videos", fake_merge_videos)

    async def run_test() -> None:
        response = await render(
            video=FakeUpload(b"fake video"),
            text="Test dubbingu",
            variant="dubbed",
        )

        try:
            assert response.status_code == 200
            assert response.media_type == "video/mp4"
            assert Path(response.path).read_bytes() == b"fake mp4"
        finally:
            await response.background()

    asyncio.run(run_test())
    assert calls == [
        ("voiceover", "Test dubbingu", b"fake video"),
        ("ffmpeg", b"fake video", b"fake mp3", True, "dubbed"),
    ]


def test_render_subtitled_returns_mp4(monkeypatch) -> None:
    calls = []

    class FakeVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            calls.append(("voiceover", text, Path(source_video_path).read_bytes()))
            Path(output_audio_path).write_bytes(b"fake mp3")

    class FakeSubtitleService:
        def __init__(self, whisper_provider) -> None:
            self.whisper_provider = whisper_provider

        def generate_srt_from_audio(self, audio_path, output_srt_path, language="pl") -> None:
            calls.append(("subtitles", Path(audio_path).read_bytes(), language))
            Path(output_srt_path).write_text("fake srt", encoding="utf-8")

    def fake_merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full") -> None:
        calls.append((
            "ffmpeg",
            Path(source_video).read_bytes(),
            Path(subtitles_file).read_text(encoding="utf-8"),
            variant,
        ))
        Path(output_path).write_bytes(b"fake subtitled mp4")

    monkeypatch.setattr("api.TTSProvider", lambda voice: object())
    monkeypatch.setattr("api.WhisperProvider", lambda model_name: object())
    monkeypatch.setattr("api.VoiceoverService", FakeVoiceoverService)
    monkeypatch.setattr("api.SubtitleService", FakeSubtitleService)
    monkeypatch.setattr("api.FFmpegProvider.merge_videos", fake_merge_videos)

    async def run_test() -> None:
        response = await render(
            video=FakeUpload(b"fake video"),
            text="Test napisow w filmie",
            variant="subtitled",
        )

        try:
            assert response.status_code == 200
            assert response.media_type == "video/mp4"
            assert Path(response.path).read_bytes() == b"fake subtitled mp4"
        finally:
            await response.background()

    asyncio.run(run_test())
    assert calls == [
        ("voiceover", "Test napisow w filmie", b"fake video"),
        ("subtitles", b"fake mp3", "pl"),
        ("ffmpeg", b"fake video", "fake srt", "subtitles_only"),
    ]


def test_render_requires_text() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(render(video=FakeUpload(b"fake video"), text="   ", variant="voiceover"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "text is required"


def test_render_rejects_unsupported_variant() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(render(video=FakeUpload(b"fake video"), text="Test", variant="bad"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "unsupported variant: bad"
