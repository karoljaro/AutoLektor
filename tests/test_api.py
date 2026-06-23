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


def test_render_requires_text() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(render(video=FakeUpload(b"fake video"), text="   ", variant="voiceover"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "text is required"


def test_render_rejects_unsupported_variant() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(render(video=FakeUpload(b"fake video"), text="Test", variant="subtitles"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "unsupported variant: subtitles"
