from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from exceptions import EmptyTextError, SubtitleGenerationError, UnsupportedVariantError, VideoRenderError
from pipeline import VARIANTS, render_variant

FAKE_AUDIO = b"fake mp3"
FAKE_SRT = "fake srt"
FAKE_VIDEO = b"fake video"


def patch_pipeline(
    monkeypatch,
    calls: list[tuple],
    *,
    subtitles: bool = False,
    ffmpeg_output: bytes | None = None,
) -> None:
    class FakeTTSProvider:
        def __init__(self, voice) -> None:
            self.voice = voice

    class FakeVoiceoverService:
        def __init__(self, tts_provider) -> None:
            self.tts_provider = tts_provider

        async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path) -> None:
            calls.append(("voiceover", text, Path(source_video_path), Path(output_audio_path), self.tts_provider.voice))
            Path(output_audio_path).write_bytes(FAKE_AUDIO)

    monkeypatch.setattr("pipeline.TTSProvider", FakeTTSProvider)
    monkeypatch.setattr("pipeline.VoiceoverService", FakeVoiceoverService)

    if subtitles:
        class FakeWhisperProvider:
            def __init__(self, model_name) -> None:
                self.model_name = model_name

        class FakeSubtitleService:
            def __init__(self, whisper_provider) -> None:
                self.whisper_provider = whisper_provider

            def generate_srt_from_audio(self, audio_path, output_srt_path, language="pl") -> None:
                calls.append(("subtitles", Path(audio_path), Path(output_srt_path), language))
                Path(output_srt_path).write_text(FAKE_SRT, encoding="utf-8")

        monkeypatch.setattr("pipeline.WhisperProvider", FakeWhisperProvider)
        monkeypatch.setattr("pipeline.SubtitleService", FakeSubtitleService)

    if ffmpeg_output is not None:
        def fake_merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full") -> None:
            calls.append((
                "ffmpeg",
                Path(source_video),
                Path(dubbed_audio),
                Path(subtitles_file),
                Path(output_path),
                variant,
            ))
            Path(output_path).write_bytes(ffmpeg_output)

        monkeypatch.setattr("pipeline.FFmpegProvider.merge_videos", fake_merge_videos)


def write_source_video(tmp_path: Path) -> Path:
    source_video = tmp_path / "input.mp4"
    source_video.write_bytes(FAKE_VIDEO)
    return source_video


def test_variant_contract() -> None:
    assert set(VARIANTS) == {"voiceover", "subtitles", "dubbed", "subtitled", "full"}


def test_render_variant_voiceover_writes_direct_output(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)
    source_video = write_source_video(tmp_path)
    output_path = tmp_path / "voiceover.mp3"

    result = asyncio.run(
        render_variant(
            text="  Test lektora  ",
            source_video=source_video,
            output_path=output_path,
            variant="voiceover",
            work_dir=tmp_path / "work",
            voice="  en-US-AvaNeural  ",
        )
    )

    assert result == output_path
    assert output_path.read_bytes() == FAKE_AUDIO
    assert calls == [("voiceover", "Test lektora", source_video, output_path, "en-US-AvaNeural")]


def test_render_variant_subtitles_uses_work_audio_and_output_srt(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True)
    source_video = write_source_video(tmp_path)
    output_path = tmp_path / "subtitles.srt"
    work_dir = tmp_path / "work"

    result = asyncio.run(
        render_variant(
            text="Test napisow",
            source_video=source_video,
            output_path=output_path,
            variant="subtitles",
            work_dir=work_dir,
            language="  en  ",
        )
    )

    assert result == output_path
    assert output_path.read_text(encoding="utf-8") == FAKE_SRT
    assert calls == [
        ("voiceover", "Test napisow", source_video, work_dir / "voiceover.mp3", "pl-PL-ZofiaNeural"),
        ("subtitles", work_dir / "voiceover.mp3", output_path, "en"),
    ]


def test_render_variant_dubbed_renders_mp4_without_subtitles(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, ffmpeg_output=b"fake dubbed mp4")
    source_video = write_source_video(tmp_path)
    output_path = tmp_path / "dubbed.mp4"
    work_dir = tmp_path / "work"

    result = asyncio.run(
        render_variant(
            text="Test dubbingu",
            source_video=source_video,
            output_path=output_path,
            variant="dubbed",
            work_dir=work_dir,
        )
    )

    assert result == output_path
    assert output_path.read_bytes() == b"fake dubbed mp4"
    assert calls == [
        ("voiceover", "Test dubbingu", source_video, work_dir / "voiceover.mp3", "pl-PL-ZofiaNeural"),
        ("ffmpeg", source_video, work_dir / "voiceover.mp3", work_dir / "subtitles.srt", output_path, "dubbed"),
    ]


def test_render_variant_full_generates_subtitles_and_video(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True, ffmpeg_output=b"fake full mp4")
    source_video = write_source_video(tmp_path)
    output_path = tmp_path / "full.mp4"
    work_dir = tmp_path / "work"

    result = asyncio.run(
        render_variant(
            text="Test full",
            source_video=source_video,
            output_path=output_path,
            variant="full",
            work_dir=work_dir,
        )
    )

    assert result == output_path
    assert output_path.read_bytes() == b"fake full mp4"
    assert calls == [
        ("voiceover", "Test full", source_video, work_dir / "voiceover.mp3", "pl-PL-ZofiaNeural"),
        ("subtitles", work_dir / "voiceover.mp3", work_dir / "subtitles.srt", "pl"),
        ("ffmpeg", source_video, work_dir / "voiceover.mp3", work_dir / "subtitles.srt", output_path, "full"),
    ]


def test_render_variant_subtitled_uses_subtitles_only_ffmpeg_variant(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls, subtitles=True, ffmpeg_output=b"fake subtitled mp4")
    source_video = write_source_video(tmp_path)
    output_path = tmp_path / "subtitled.mp4"
    work_dir = tmp_path / "work"

    result = asyncio.run(
        render_variant(
            text="Test subtitled",
            source_video=source_video,
            output_path=output_path,
            variant="subtitled",
            work_dir=work_dir,
        )
    )

    assert result == output_path
    assert output_path.read_bytes() == b"fake subtitled mp4"
    assert calls == [
        ("voiceover", "Test subtitled", source_video, work_dir / "voiceover.mp3", "pl-PL-ZofiaNeural"),
        ("subtitles", work_dir / "voiceover.mp3", work_dir / "subtitles.srt", "pl"),
        ("ffmpeg", source_video, work_dir / "voiceover.mp3", work_dir / "subtitles.srt", output_path, "subtitles_only"),
    ]


def test_render_variant_rejects_empty_text(tmp_path: Path) -> None:
    with pytest.raises(EmptyTextError):
        asyncio.run(
            render_variant(
                text="   ",
                source_video=write_source_video(tmp_path),
                output_path=tmp_path / "out.mp3",
                variant="voiceover",
                work_dir=tmp_path / "work",
            )
        )


def test_render_variant_rejects_unknown_variant(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedVariantError):
        asyncio.run(
            render_variant(
                text="Test",
                source_video=write_source_video(tmp_path),
                output_path=tmp_path / "out.mp3",
                variant="bad",
                work_dir=tmp_path / "work",
            )
        )


def test_render_variant_wraps_subtitle_failures(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    class FailingSubtitleService:
        def __init__(self, whisper_provider) -> None:
            self.whisper_provider = whisper_provider

        def generate_srt_from_audio(self, audio_path, output_srt_path, language="pl") -> None:
            raise RuntimeError("whisper failed")

    monkeypatch.setattr("pipeline.WhisperProvider", lambda model_name: object())
    monkeypatch.setattr("pipeline.SubtitleService", FailingSubtitleService)

    with pytest.raises(SubtitleGenerationError):
        asyncio.run(
            render_variant(
                text="Test",
                source_video=write_source_video(tmp_path),
                output_path=tmp_path / "out.srt",
                variant="subtitles",
                work_dir=tmp_path / "work",
            )
        )


def test_render_variant_wraps_video_failures(monkeypatch, tmp_path: Path) -> None:
    calls = []
    patch_pipeline(monkeypatch, calls)

    def fake_merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full") -> None:
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr("pipeline.FFmpegProvider.merge_videos", fake_merge_videos)

    with pytest.raises(VideoRenderError):
        asyncio.run(
            render_variant(
                text="Test",
                source_video=write_source_video(tmp_path),
                output_path=tmp_path / "out.mp4",
                variant="dubbed",
                work_dir=tmp_path / "work",
            )
        )
