from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import main
from helpers.preflight import escape_ffmpeg_filter_path, ensure_commands_available, ensure_parent_dirs_exist


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


def test_preflight_checks_validates_required_inputs(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "input.mp4"
    text_path = tmp_path / "text.txt"
    output_path = tmp_path / "out" / "voiceover.mp3"

    monkeypatch.setattr("main.ensure_commands_available", lambda *args: None)
    monkeypatch.setattr("main.ensure_parent_dirs_exist", lambda *args: None)
    monkeypatch.setattr("main.file_exists", lambda path: Path(path) in {video_path, text_path})

    main.preflight_checks(video_path, output_path, text_path)


def test_preflight_checks_raises_for_missing_text_file(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "input.mp4"
    text_path = tmp_path / "missing.txt"
    output_path = tmp_path / "voiceover.mp3"

    monkeypatch.setattr("main.ensure_commands_available", lambda *args: None)
    monkeypatch.setattr("main.ensure_parent_dirs_exist", lambda *args: None)
    monkeypatch.setattr("main.file_exists", lambda path: Path(path) == video_path)

    try:
        main.preflight_checks(video_path, output_path, text_path)
    except FileNotFoundError as exc:
        assert "Text file not found" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing text file")

