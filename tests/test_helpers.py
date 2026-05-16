from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from helpers.duration_helpers import get_duration
from helpers.file_helpers import file_exists, read_text_from_file
from helpers.time_helpers import format_time


def test_read_text_from_file_cleans_whitespace(tmp_path: Path) -> None:
    file_path = tmp_path / "input.txt"
    file_path.write_text("  Hello\n\n world\tfrom   pytest  ", encoding="utf-8")

    assert read_text_from_file(str(file_path)) == "Hello world from pytest"


def test_read_text_from_file_missing_returns_none(tmp_path: Path) -> None:
    assert read_text_from_file(str(tmp_path / "missing.txt")) is None


def test_read_text_from_file_empty_returns_none(tmp_path: Path) -> None:
    file_path = tmp_path / "empty.txt"
    file_path.write_text("\n \t \n", encoding="utf-8")

    assert read_text_from_file(str(file_path)) is None


def test_file_exists(tmp_path: Path) -> None:
    existing = tmp_path / "exists.txt"
    existing.write_text("x", encoding="utf-8")

    assert file_exists(str(existing)) is True
    assert file_exists(str(tmp_path / "missing.txt")) is False


def test_format_time() -> None:
    assert format_time(0.0) == "00:00:00,000"
    assert format_time(3.5) == "00:00:03,500"
    assert format_time(3661.25) == "01:01:01,250"


def test_get_duration_parses_ffprobe_output(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="12.75\n")

    monkeypatch.setattr("helpers.duration_helpers.subprocess.run", fake_run)

    assert get_duration("video.mp4") == 12.75


def test_get_duration_raises_on_ffprobe_failure(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd="ffprobe", output="", stderr="boom")

    monkeypatch.setattr("helpers.duration_helpers.subprocess.run", fake_run)

    try:
        get_duration("video.mp4")
    except RuntimeError as exc:
        assert "Could not read duration" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for ffprobe failure")



