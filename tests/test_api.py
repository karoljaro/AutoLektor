from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from api import VARIANTS, app, autolektor_error_handler, health, render
from exceptions import (
    EmptyTextError,
    SubtitleGenerationError,
    UnsupportedVariantError,
    UploadSaveError,
    VideoRenderError,
    VoiceoverGenerationError,
)

FAKE_VIDEO = b"fake video"
FAKE_AUDIO = b"fake mp3"
FAKE_SRT = "fake srt"


class FakeUpload:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.was_read = False

    async def read(self, size: int) -> bytes:
        if self.was_read:
            return b""
        self.was_read = True
        return self.content


class FailingUpload:
    async def read(self, size: int) -> bytes:
        raise OSError("cannot read upload")


def patch_pipeline(
    monkeypatch,
    calls: list[tuple],
    *,
    subtitles: bool = False,
    ffmpeg_output: bytes | None = None,
) -> None:
    class FakeVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            calls.append(("voiceover", text, Path(source_video_path).read_bytes()))
            Path(output_audio_path).write_bytes(FAKE_AUDIO)

    monkeypatch.setattr("api.TTSProvider", lambda voice: object())
    monkeypatch.setattr("api.VoiceoverService", FakeVoiceoverService)

    if subtitles:
        class FakeSubtitleService:
            def __init__(self, whisper_provider) -> None:
                self.whisper_provider = whisper_provider

            def generate_srt_from_audio(self, audio_path, output_srt_path, language="pl") -> None:
                calls.append(("subtitles", Path(audio_path).read_bytes(), language))
                Path(output_srt_path).write_text(FAKE_SRT, encoding="utf-8")

        monkeypatch.setattr("api.WhisperProvider", lambda model_name: object())
        monkeypatch.setattr("api.SubtitleService", FakeSubtitleService)

    if ffmpeg_output is not None:
        def fake_merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full") -> None:
            subtitles_path = Path(subtitles_file)
            calls.append((
                "ffmpeg",
                Path(source_video).read_bytes(),
                Path(dubbed_audio).read_bytes(),
                subtitles_path.read_text(encoding="utf-8") if subtitles_path.exists() else None,
                variant,
            ))
            Path(output_path).write_bytes(ffmpeg_output)

        monkeypatch.setattr("api.FFmpegProvider.merge_videos", fake_merge_videos)


def run_render(variant: str, *, text: str = "Test", video: bytes = FAKE_VIDEO) -> tuple[int, str, bytes]:
    async def run_test() -> tuple[int, str, bytes]:
        response = await render(video=FakeUpload(video), text=text, variant=variant)
        try:
            return response.status_code, response.media_type, Path(response.path).read_bytes()
        finally:
            await response.background()

    return asyncio.run(run_test())


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_render_route_is_registered() -> None:
    assert any(route.path == "/render" and "POST" in route.methods for route in app.routes)


def test_variant_contract() -> None:
    assert set(VARIANTS) == {"voiceover", "subtitles", "dubbed", "subtitled", "full"}


def test_autolektor_error_handler_returns_n8n_friendly_json() -> None:
    response = asyncio.run(autolektor_error_handler(None, UnsupportedVariantError("bad")))

    assert response.status_code == 400
    assert json.loads(response.body) == {
        "error": "UNSUPPORTED_VARIANT",
        "detail": "unsupported variant: bad",
    }


def test_render_voiceover_returns_mp3(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    status_code, media_type, body = run_render("voiceover", text="  Test lektora  ")

    assert (status_code, media_type, body) == (200, "audio/mpeg", FAKE_AUDIO)
    assert calls == [("voiceover", "Test lektora", FAKE_VIDEO)]


def test_render_subtitles_returns_srt(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True)

    status_code, media_type, body = run_render("subtitles", text="Test napisow")

    assert (status_code, media_type, body) == (200, "application/x-subrip", FAKE_SRT.encode())
    assert calls == [
        ("voiceover", "Test napisow", FAKE_VIDEO),
        ("subtitles", FAKE_AUDIO, "pl"),
    ]


def test_render_dubbed_returns_mp4(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, ffmpeg_output=b"fake dubbed mp4")

    status_code, media_type, body = run_render("dubbed", text="Test dubbingu")

    assert (status_code, media_type, body) == (200, "video/mp4", b"fake dubbed mp4")
    assert calls == [
        ("voiceover", "Test dubbingu", FAKE_VIDEO),
        ("ffmpeg", FAKE_VIDEO, FAKE_AUDIO, None, "dubbed"),
    ]


def test_render_subtitled_returns_mp4(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True, ffmpeg_output=b"fake subtitled mp4")

    status_code, media_type, body = run_render("subtitled", text="Test napisow w filmie")

    assert (status_code, media_type, body) == (200, "video/mp4", b"fake subtitled mp4")
    assert calls == [
        ("voiceover", "Test napisow w filmie", FAKE_VIDEO),
        ("subtitles", FAKE_AUDIO, "pl"),
        ("ffmpeg", FAKE_VIDEO, FAKE_AUDIO, FAKE_SRT, "subtitles_only"),
    ]


def test_render_full_returns_mp4(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True, ffmpeg_output=b"fake full mp4")

    status_code, media_type, body = run_render("full", text="Test pelnego filmu")

    assert (status_code, media_type, body) == (200, "video/mp4", b"fake full mp4")
    assert calls == [
        ("voiceover", "Test pelnego filmu", FAKE_VIDEO),
        ("subtitles", FAKE_AUDIO, "pl"),
        ("ffmpeg", FAKE_VIDEO, FAKE_AUDIO, FAKE_SRT, "full"),
    ]


def test_render_requires_text() -> None:
    with pytest.raises(EmptyTextError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="   ", variant="voiceover"))

    assert exc_info.value.to_response() == {"error": "EMPTY_TEXT", "detail": "text is required"}


def test_render_rejects_unsupported_variant() -> None:
    with pytest.raises(UnsupportedVariantError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="bad"))

    assert exc_info.value.to_response() == {
        "error": "UNSUPPORTED_VARIANT",
        "detail": "unsupported variant: bad",
    }


def test_render_wraps_upload_failures() -> None:
    with pytest.raises(UploadSaveError) as exc_info:
        asyncio.run(render(video=FailingUpload(), text="Test", variant="voiceover"))

    assert exc_info.value.to_response() == {
        "error": "UPLOAD_SAVE_FAILED",
        "detail": "failed to save uploaded video",
    }


def test_render_wraps_voiceover_failures(monkeypatch) -> None:
    class FailingVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            raise RuntimeError("tts exploded")

    monkeypatch.setattr("api.TTSProvider", lambda voice: object())
    monkeypatch.setattr("api.VoiceoverService", FailingVoiceoverService)

    with pytest.raises(VoiceoverGenerationError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="voiceover"))

    assert exc_info.value.to_response() == {
        "error": "VOICEOVER_GENERATION_FAILED",
        "detail": "failed to generate voiceover",
    }


def test_render_wraps_subtitle_failures(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    class FailingSubtitleService:
        def __init__(self, whisper_provider) -> None:
            self.whisper_provider = whisper_provider

        def generate_srt_from_audio(self, audio_path, output_srt_path, language="pl") -> None:
            raise RuntimeError("whisper exploded")

    monkeypatch.setattr("api.WhisperProvider", lambda model_name: object())
    monkeypatch.setattr("api.SubtitleService", FailingSubtitleService)

    with pytest.raises(SubtitleGenerationError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="subtitles"))

    assert exc_info.value.to_response() == {
        "error": "SUBTITLE_GENERATION_FAILED",
        "detail": "failed to generate subtitles",
    }


def test_render_wraps_video_failures(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    def fake_merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full") -> None:
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr("api.FFmpegProvider.merge_videos", fake_merge_videos)

    with pytest.raises(VideoRenderError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="dubbed"))

    assert exc_info.value.to_response() == {
        "error": "VIDEO_RENDER_FAILED",
        "detail": "failed to render video",
    }
