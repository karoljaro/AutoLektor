from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import main
from helpers.preflight import escape_ffmpeg_filter_path, ensure_commands_available, ensure_parent_dirs_exist
from services.video_service import VideoService


def test_escape_ffmpeg_filter_path_escapes_special_chars() -> None:
    escaped = escape_ffmpeg_filter_path(r"Video/subs,part:1\name.srt")
    assert "\\," in escaped
    assert "\\:" in escaped
    assert "\\\\" in escaped


def test_ensure_commands_available_raises_for_missing_commands(monkeypatch) -> None:
    monkeypatch.setattr("helpers.preflight.shutil.which", lambda cmd: None)

    try:
        ensure_commands_available("ffmpeg", "ffprobe")
    except RuntimeError as exc:
        assert "Missing required system commands" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing system commands")


def test_ensure_parent_dirs_exist_creates_nested_directories(tmp_path: Path) -> None:
    nested_file = tmp_path / "a" / "b" / "c" / "file.srt"
    ensure_parent_dirs_exist(str(nested_file))
    assert (tmp_path / "a" / "b" / "c").exists()


def test_preflight_checks_validates_required_inputs(monkeypatch) -> None:
    monkeypatch.setattr("main.ensure_commands_available", lambda *args: None)
    monkeypatch.setattr("main.ensure_parent_dirs_exist", lambda *args: None)
    monkeypatch.setattr("main.file_exists", lambda path: path == main.TEXT_FILE or path == main.SOURCE_VIDEO)

    main.preflight_checks()


def test_preflight_checks_raises_for_missing_text_file(monkeypatch) -> None:
    monkeypatch.setattr("main.ensure_commands_available", lambda *args: None)
    monkeypatch.setattr("main.ensure_parent_dirs_exist", lambda *args: None)
    monkeypatch.setattr("main.file_exists", lambda path: path == main.SOURCE_VIDEO)

    try:
        main.preflight_checks()
    except FileNotFoundError as exc:
        assert "Text file not found" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing text file")


def test_video_service_rejects_missing_output_keys(monkeypatch) -> None:
    monkeypatch.setattr("services.video_service.file_exists", lambda path: True)
    fake_ffmpeg = type("F", (), {"merge_videos": lambda *args, **kwargs: None})()
    monkeypatch.setattr("services.video_service.FFmpegProvider", lambda: fake_ffmpeg)

    service = VideoService()

    try:
        service.create_all_variants(
            source_video="video.mp4",
            dubbed_audio="audio.mp3",
            subtitles_file="subs.srt",
            output_paths={"full": "full.mp4", "dubbed": "dubbed.mp4"},
        )
    except ValueError as exc:
        assert "Missing output paths for variants" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing output variants")


