from __future__ import annotations

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

from providers.ffmpeg_provider import FFmpegProvider
from providers.tts_provider import TTSProvider
from providers.whisper_provider import WhisperProvider


def test_tts_provider_omits_rate_when_none() -> None:
    provider = TTSProvider("pl-PL-ZofiaNeural")

    async def run() -> None:
        with patch("providers.tts_provider.edge_tts.Communicate") as communicate_cls:
            communicate_cls.return_value.save = AsyncMock()

            await provider.generate_voiceover("test", "/tmp/out.mp3")

            communicate_cls.assert_called_once_with("test", "pl-PL-ZofiaNeural")
            communicate_cls.return_value.save.assert_awaited_once_with("/tmp/out.mp3")

    asyncio.run(run())


def test_tts_provider_passes_rate_when_string() -> None:
    provider = TTSProvider("pl-PL-ZofiaNeural")

    async def run() -> None:
        with patch("providers.tts_provider.edge_tts.Communicate") as communicate_cls:
            communicate_cls.return_value.save = AsyncMock()

            await provider.generate_voiceover("test", "/tmp/out.mp3", rate="+10%")

            communicate_cls.assert_called_once_with("test", "pl-PL-ZofiaNeural", rate="+10%")

    asyncio.run(run())


def test_tts_provider_rejects_non_string_rate() -> None:
    provider = TTSProvider("pl-PL-ZofiaNeural")

    async def run() -> None:
        try:
            await provider.generate_voiceover("test", "/tmp/out.mp3", rate=10)  # type: ignore[arg-type]
        except TypeError as exc:
            assert "rate must be a string" in str(exc)
        else:
            raise AssertionError("Expected TypeError for non-string rate")

    asyncio.run(run())


def test_whisper_provider_loads_model_once_and_transcribes(monkeypatch) -> None:
    fake_model = MagicMock(name="fake-model")
    fake_model.device = "cpu"
    load_model_mock = MagicMock(return_value=fake_model)
    transcribe_mock = MagicMock(return_value={"segments": []})

    monkeypatch.setattr("providers.whisper_provider.whisper.load_model", load_model_mock)
    monkeypatch.setattr("providers.whisper_provider.whisper.transcribe", transcribe_mock)

    provider = WhisperProvider(model_name="base")

    assert provider.load_model() is fake_model
    assert provider.load_model() is fake_model
    load_model_mock.assert_called_once_with("base")

    result = provider.transcribe("audio.mp3", language="pl")
    assert result == {"segments": []}
    transcribe_mock.assert_called_once_with(
        fake_model,
        audio="audio.mp3",
        language="pl",
        fp16=False,
    )


def test_whisper_provider_keeps_default_fp16_behavior_for_cuda(monkeypatch) -> None:
    fake_model = MagicMock(name="fake-model")
    fake_model.device = "cuda:0"
    transcribe_mock = MagicMock(return_value={"segments": []})

    monkeypatch.setattr(
        "providers.whisper_provider.whisper.load_model",
        MagicMock(return_value=fake_model),
    )
    monkeypatch.setattr("providers.whisper_provider.whisper.transcribe", transcribe_mock)

    provider = WhisperProvider(model_name="base")

    result = provider.transcribe("audio.mp3", language="pl")
    assert result == {"segments": []}
    transcribe_mock.assert_called_once_with(fake_model, audio="audio.mp3", language="pl")


def test_ffmpeg_provider_detects_video_fps_from_ffprobe(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"streams":[{"avg_frame_rate":"30000/1001","r_frame_rate":"30/1"}]}',
            stderr="",
        )

    monkeypatch.setattr("providers.ffmpeg_provider.ensure_commands_available", lambda *args: None)
    monkeypatch.setattr("providers.ffmpeg_provider.subprocess.run", fake_run)

    assert FFmpegProvider.detect_video_fps("in.mp4") == "30000/1001"


def test_ffmpeg_provider_detect_video_fps_falls_back_to_r_frame_rate(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"streams":[{"avg_frame_rate":"0/0","r_frame_rate":"25/1"}]}',
            stderr="",
        )

    monkeypatch.setattr("providers.ffmpeg_provider.ensure_commands_available", lambda *args: None)
    monkeypatch.setattr("providers.ffmpeg_provider.subprocess.run", fake_run)

    assert FFmpegProvider.detect_video_fps("in.mp4") == "25"


def test_ffmpeg_provider_builds_expected_commands(monkeypatch) -> None:
    cases = {
        "full": ["-c:v", "libx264", "-c:a", "aac"],
        "dubbed": ["-c:v", "copy", "-c:a", "aac"],
        "subtitles_only": ["-c:v", "libx264", "-c:a", "copy"],
    }

    for variant, expected_snippet in cases.items():
        monkeypatch.setattr("providers.ffmpeg_provider.FFmpegProvider.detect_video_fps", lambda path: "24000/1001")
        with patch("providers.ffmpeg_provider.subprocess.run") as run_mock:
            FFmpegProvider.merge_videos("in.mp4", "dub.mp3", "sub.srt", "out.mp4", variant=variant)

        command = run_mock.call_args.args[0]
        for token in expected_snippet:
            assert token in command
        if variant != "dubbed":
            assert "fps=24000/1001,subtitles=sub.srt" in command


def test_ffmpeg_provider_raises_for_unknown_variant() -> None:
    try:
        FFmpegProvider.merge_videos("in.mp4", "dub.mp3", "sub.srt", "out.mp4", variant="bad")
    except ValueError as exc:
        assert "Unknown variant" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid variant")


def test_ffmpeg_provider_wraps_subprocess_errors(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd="ffmpeg", output="", stderr="ffmpeg exploded")

    monkeypatch.setattr("providers.ffmpeg_provider.subprocess.run", fake_run)

    try:
        FFmpegProvider.merge_videos("in.mp4", "dub.mp3", "sub.srt", "out.mp4", variant="dubbed")
    except RuntimeError as exc:
        assert "FFmpeg command failed: ffmpeg exploded" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when ffmpeg fails")
