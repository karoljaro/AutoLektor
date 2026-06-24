from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from api import VARIANTS, app, autolektor_error_handler, health, render, validate_saved_video_file
from exceptions import (
    EmptyVideoError,
    EmptyTextError,
    InvalidVideoFileError,
    SubtitleGenerationError,
    TextFileReadError,
    TextInputConflictError,
    UnsupportedVariantError,
    UnsupportedVideoTypeError,
    UploadSaveError,
    VideoTooLargeError,
    VideoRenderError,
    VoiceoverGenerationError,
)

FAKE_VIDEO = b"fake video"
FAKE_AUDIO = b"fake mp3"
FAKE_SRT = "fake srt"


class FakeUpload:
    def __init__(self, content: bytes, filename: str = "input.mp4", content_type: str = "video/mp4") -> None:
        self.content = content
        self.filename = filename
        self.content_type = content_type
        self.was_read = False

    async def read(self, size: int | None = None) -> bytes:
        if self.was_read:
            return b""
        self.was_read = True
        return self.content


class FailingUpload:
    filename = "input.mp4"
    content_type = "video/mp4"

    async def read(self, size: int | None = None) -> bytes:
        raise OSError("cannot read upload")


def error_response(error: str, detail: str, stage: str, retryable: bool = False) -> dict[str, str | bool]:
    return {
        "error": error,
        "detail": detail,
        "stage": stage,
        "retryable": retryable,
    }


def patch_pipeline(
    monkeypatch,
    calls: list[tuple],
    *,
    subtitles: bool = False,
    ffmpeg_output: bytes | None = None,
) -> None:
    async def fake_render_variant(
        *,
        text,
        source_video,
        output_path,
        variant,
        work_dir,
        voice=None,
        language=None,
    ) -> Path:
        calls.append((
            "render",
            text,
            Path(source_video).read_bytes(),
            variant,
            voice,
            language,
            Path(output_path).name,
        ))
        if variant == "voiceover":
            Path(output_path).write_bytes(FAKE_AUDIO)
        elif variant == "subtitles":
            Path(output_path).write_text(FAKE_SRT, encoding="utf-8")
        else:
            Path(output_path).write_bytes(ffmpeg_output if ffmpeg_output is not None else b"fake mp4")
        return Path(output_path)

    monkeypatch.setattr("api.render_variant", fake_render_variant)
    monkeypatch.setattr("api.validate_saved_video_file", lambda path: None)


def run_render(
    variant: str,
    *,
    text: str | None = "Test",
    text_file: bytes | None = None,
    video: bytes = FAKE_VIDEO,
    voice: str | None = None,
    language: str | None = None,
) -> tuple[int, str, bytes]:
    async def run_test() -> tuple[int, str, bytes]:
        response = await render(
            video=FakeUpload(video),
            text=text,
            variant=variant,
            voice=voice,
            language=language,
            text_file=FakeUpload(text_file) if text_file is not None else None,
        )
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
    assert json.loads(response.body) == error_response("UNSUPPORTED_VARIANT", "unsupported variant: bad", "input")


def test_render_voiceover_returns_mp3(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    status_code, media_type, body = run_render("voiceover", text="  Test lektora  ")

    assert (status_code, media_type, body) == (200, "audio/mpeg", FAKE_AUDIO)
    assert calls == [("render", "Test lektora", FAKE_VIDEO, "voiceover", None, None, "voiceover.mp3")]


def test_render_accepts_text_file(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    status_code, media_type, body = run_render("voiceover", text=None, text_file=b"  Tekst z pliku  ")

    assert (status_code, media_type, body) == (200, "audio/mpeg", FAKE_AUDIO)
    assert calls == [("render", "Tekst z pliku", FAKE_VIDEO, "voiceover", None, None, "voiceover.mp3")]


def test_render_accepts_voice_override(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    status_code, media_type, body = run_render("voiceover", text="Test", voice="  en-US-AvaNeural  ")

    assert (status_code, media_type, body) == (200, "audio/mpeg", FAKE_AUDIO)
    assert calls == [("render", "Test", FAKE_VIDEO, "voiceover", "  en-US-AvaNeural  ", None, "voiceover.mp3")]


def test_render_subtitles_returns_srt(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True)

    status_code, media_type, body = run_render("subtitles", text="Test napisow")

    assert (status_code, media_type, body) == (200, "application/x-subrip", FAKE_SRT.encode())
    assert calls == [("render", "Test napisow", FAKE_VIDEO, "subtitles", None, None, "subtitles.srt")]


def test_render_accepts_language_override_for_subtitles(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True)

    status_code, media_type, body = run_render("subtitles", text="Test subtitles", language="  en  ")

    assert (status_code, media_type, body) == (200, "application/x-subrip", FAKE_SRT.encode())
    assert calls == [("render", "Test subtitles", FAKE_VIDEO, "subtitles", None, "  en  ", "subtitles.srt")]


def test_render_dubbed_returns_mp4(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, ffmpeg_output=b"fake dubbed mp4")

    status_code, media_type, body = run_render("dubbed", text="Test dubbingu")

    assert (status_code, media_type, body) == (200, "video/mp4", b"fake dubbed mp4")
    assert calls == [("render", "Test dubbingu", FAKE_VIDEO, "dubbed", None, None, "dubbed.mp4")]


def test_render_subtitled_returns_mp4(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True, ffmpeg_output=b"fake subtitled mp4")

    status_code, media_type, body = run_render("subtitled", text="Test napisow w filmie")

    assert (status_code, media_type, body) == (200, "video/mp4", b"fake subtitled mp4")
    assert calls == [("render", "Test napisow w filmie", FAKE_VIDEO, "subtitled", None, None, "subtitled.mp4")]


def test_render_full_returns_mp4(monkeypatch) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True, ffmpeg_output=b"fake full mp4")

    status_code, media_type, body = run_render("full", text="Test pelnego filmu")

    assert (status_code, media_type, body) == (200, "video/mp4", b"fake full mp4")
    assert calls == [("render", "Test pelnego filmu", FAKE_VIDEO, "full", None, None, "full.mp4")]


def test_render_requires_text() -> None:
    with pytest.raises(EmptyTextError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="   ", variant="voiceover"))

    assert exc_info.value.to_response() == error_response("EMPTY_TEXT", "text is required", "input")


def test_render_rejects_text_and_text_file_together() -> None:
    with pytest.raises(TextInputConflictError) as exc_info:
        asyncio.run(
            render(
                video=FakeUpload(FAKE_VIDEO),
                text="Test",
                text_file=FakeUpload(b"Test z pliku"),
                variant="voiceover",
            )
        )

    assert exc_info.value.to_response() == error_response(
        "TEXT_INPUT_CONFLICT",
        "provide either text or text_file, not both",
        "input",
    )


def test_render_rejects_empty_text_file() -> None:
    with pytest.raises(EmptyTextError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text=None, text_file=FakeUpload(b" \n "), variant="voiceover"))

    assert exc_info.value.to_response() == error_response("EMPTY_TEXT", "text is required", "input")


def test_render_wraps_text_file_read_failures() -> None:
    with pytest.raises(TextFileReadError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text=None, text_file=FailingUpload(), variant="voiceover"))

    assert exc_info.value.to_response() == error_response(
        "TEXT_FILE_READ_FAILED",
        "failed to read text_file as UTF-8 text",
        "input",
    )


def test_render_rejects_non_utf8_text_file() -> None:
    with pytest.raises(TextFileReadError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text=None, text_file=FakeUpload(b"\xff"), variant="voiceover"))

    assert exc_info.value.to_response() == error_response(
        "TEXT_FILE_READ_FAILED",
        "failed to read text_file as UTF-8 text",
        "input",
    )


def test_render_rejects_unsupported_variant() -> None:
    with pytest.raises(UnsupportedVariantError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="bad"))

    assert exc_info.value.to_response() == error_response("UNSUPPORTED_VARIANT", "unsupported variant: bad", "input")


def test_render_rejects_unsupported_video_type() -> None:
    with pytest.raises(UnsupportedVideoTypeError) as exc_info:
        asyncio.run(
            render(
                video=FakeUpload(FAKE_VIDEO, filename="input.txt", content_type="text/plain"),
                text="Test",
                variant="voiceover",
            )
        )

    assert exc_info.value.to_response() == error_response(
        "UNSUPPORTED_VIDEO_TYPE",
        "unsupported video type: expected MP4 video",
        "input",
    )


def test_render_rejects_empty_video() -> None:
    with pytest.raises(EmptyVideoError) as exc_info:
        asyncio.run(render(video=FakeUpload(b""), text="Test", variant="voiceover"))

    assert exc_info.value.to_response() == error_response("EMPTY_VIDEO", "video file is empty", "input")


def test_render_rejects_video_over_size_limit(monkeypatch) -> None:
    monkeypatch.setattr("api.MAX_VIDEO_UPLOAD_SIZE_BYTES", len(FAKE_VIDEO) - 1)

    with pytest.raises(VideoTooLargeError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="voiceover"))

    assert exc_info.value.status_code == 413
    assert exc_info.value.to_response() == error_response(
        "VIDEO_TOO_LARGE",
        f"video file exceeds maximum size of {len(FAKE_VIDEO) - 1} bytes",
        "input",
    )


def test_validate_saved_video_file_wraps_ffprobe_failures(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(FAKE_VIDEO)

    def failing_detect_video_fps(path: str) -> str:
        raise RuntimeError("ffprobe failed")

    monkeypatch.setattr("api.FFmpegProvider.detect_video_fps", failing_detect_video_fps)

    with pytest.raises(InvalidVideoFileError) as exc_info:
        validate_saved_video_file(video_path)

    assert exc_info.value.to_response() == error_response(
        "INVALID_VIDEO_FILE",
        "invalid video file: expected a readable video stream",
        "input",
    )


def test_render_rejects_invalid_saved_video(monkeypatch) -> None:
    async def fake_render_variant(**kwargs) -> None:
        raise AssertionError("render_variant should not run for invalid video")

    def failing_validate_saved_video_file(path: Path) -> None:
        raise InvalidVideoFileError()

    monkeypatch.setattr("api.render_variant", fake_render_variant)
    monkeypatch.setattr("api.validate_saved_video_file", failing_validate_saved_video_file)

    with pytest.raises(InvalidVideoFileError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="voiceover"))

    assert exc_info.value.to_response() == error_response(
        "INVALID_VIDEO_FILE",
        "invalid video file: expected a readable video stream",
        "input",
    )


def test_render_wraps_upload_failures() -> None:
    with pytest.raises(UploadSaveError) as exc_info:
        asyncio.run(render(video=FailingUpload(), text="Test", variant="voiceover"))

    assert exc_info.value.to_response() == error_response(
        "UPLOAD_SAVE_FAILED",
        "failed to save uploaded video",
        "upload",
        retryable=True,
    )


def test_render_wraps_voiceover_failures(monkeypatch) -> None:
    async def failing_render_variant(**kwargs) -> None:
        raise VoiceoverGenerationError()

    monkeypatch.setattr("api.render_variant", failing_render_variant)
    monkeypatch.setattr("api.validate_saved_video_file", lambda path: None)

    with pytest.raises(VoiceoverGenerationError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="voiceover"))

    assert exc_info.value.to_response() == error_response(
        "VOICEOVER_GENERATION_FAILED",
        "failed to generate voiceover",
        "voiceover",
        retryable=True,
    )


def test_render_wraps_subtitle_failures(monkeypatch) -> None:
    async def failing_render_variant(**kwargs) -> None:
        raise SubtitleGenerationError()

    monkeypatch.setattr("api.render_variant", failing_render_variant)
    monkeypatch.setattr("api.validate_saved_video_file", lambda path: None)

    with pytest.raises(SubtitleGenerationError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="subtitles"))

    assert exc_info.value.to_response() == error_response(
        "SUBTITLE_GENERATION_FAILED",
        "failed to generate subtitles",
        "subtitles",
        retryable=True,
    )


def test_render_wraps_video_failures(monkeypatch) -> None:
    async def failing_render_variant(**kwargs) -> None:
        raise VideoRenderError()

    monkeypatch.setattr("api.render_variant", failing_render_variant)
    monkeypatch.setattr("api.validate_saved_video_file", lambda path: None)

    with pytest.raises(VideoRenderError) as exc_info:
        asyncio.run(render(video=FakeUpload(FAKE_VIDEO), text="Test", variant="dubbed"))

    assert exc_info.value.to_response() == error_response(
        "VIDEO_RENDER_FAILED",
        "failed to render video",
        "video_render",
        retryable=True,
    )
