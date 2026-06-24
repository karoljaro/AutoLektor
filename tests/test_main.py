from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import main


def test_parse_args_accepts_minimal_text_file_call() -> None:
    args = main.parse_args(["input.mp4", "--text-file", "text.txt", "--variant", "full"])

    assert args.video == Path("input.mp4")
    assert args.text is None
    assert args.text_file == Path("text.txt")
    assert args.variant == "full"
    assert args.output is None


def test_parse_args_requires_variant() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.parse_args(["input.mp4", "--text-file", "text.txt"])

    assert exc_info.value.code == 2


def test_parse_args_requires_exactly_one_text_input() -> None:
    with pytest.raises(SystemExit) as missing_text:
        main.parse_args(["input.mp4", "--variant", "voiceover"])

    with pytest.raises(SystemExit) as conflicting_text:
        main.parse_args(["input.mp4", "--text", "Hello", "--text-file", "text.txt", "--variant", "voiceover"])

    assert missing_text.value.code == 2
    assert conflicting_text.value.code == 2


def test_default_output_path_uses_input_stem_variant_and_extension() -> None:
    assert main.default_output_path(Path("/tmp/input.mp4"), "voiceover") == Path("/tmp/input_voiceover.mp3")
    assert main.default_output_path(Path("/tmp/input.mp4"), "subtitles") == Path("/tmp/input_subtitles.srt")
    assert main.default_output_path(Path("/tmp/input.mp4"), "full") == Path("/tmp/input_full.mp4")


def test_resolve_cli_text_accepts_inline_text() -> None:
    assert main.resolve_cli_text("  Hello world  ", None) == "Hello world"


def test_resolve_cli_text_reads_text_file(monkeypatch) -> None:
    monkeypatch.setattr("main.read_text_from_file", lambda path: "Text from file")

    assert main.resolve_cli_text(None, Path("text.txt")) == "Text from file"


def test_run_cli_calls_pipeline_with_expected_arguments(monkeypatch, tmp_path: Path) -> None:
    calls = []
    video_path = tmp_path / "input.mp4"
    text_path = tmp_path / "text.txt"
    output_path = tmp_path / "out.mp4"
    video_path.write_bytes(b"video")
    text_path.write_text("Text from file", encoding="utf-8")

    async def fake_render_variant(**kwargs) -> Path:
        calls.append(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"output")
        return Path(kwargs["output_path"])

    monkeypatch.setattr("main.preflight_checks", lambda *args: None)
    monkeypatch.setattr("main.render_variant", fake_render_variant)
    args = main.parse_args([
        str(video_path),
        "--text-file",
        str(text_path),
        "--variant",
        "dubbed",
        "-o",
        str(output_path),
        "--voice",
        "en-US-AvaNeural",
    ])

    result = asyncio.run(main.run_cli(args))

    assert result == 0
    assert calls[0]["text"] == "Text from file"
    assert calls[0]["source_video"] == video_path
    assert calls[0]["output_path"] == output_path
    assert calls[0]["variant"] == "dubbed"
    assert calls[0]["voice"] == "en-US-AvaNeural"
    assert calls[0]["language"] is None
    assert calls[0]["work_dir"].name.startswith("autolektor-cli-")


def test_run_cli_uses_default_output_path(monkeypatch, tmp_path: Path) -> None:
    calls = []
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")

    async def fake_render_variant(**kwargs) -> Path:
        calls.append(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"output")
        return Path(kwargs["output_path"])

    monkeypatch.setattr("main.preflight_checks", lambda *args: None)
    monkeypatch.setattr("main.render_variant", fake_render_variant)
    args = main.parse_args([str(video_path), "--text", "Hello", "--variant", "voiceover", "--language", "pl"])

    result = asyncio.run(main.run_cli(args))

    assert result == 0
    assert calls[0]["output_path"] == tmp_path / "input_voiceover.mp3"
    assert calls[0]["text"] == "Hello"
    assert calls[0]["language"] == "pl"


def test_run_cli_returns_1_for_empty_text(monkeypatch, tmp_path: Path) -> None:
    calls = []
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"video")

    async def fake_render_variant(**kwargs) -> Path:
        calls.append(kwargs)
        return Path(kwargs["output_path"])

    monkeypatch.setattr("main.preflight_checks", lambda *args: None)
    monkeypatch.setattr("main.render_variant", fake_render_variant)
    args = main.parse_args([str(video_path), "--text", "   ", "--variant", "voiceover"])

    result = asyncio.run(main.run_cli(args))

    assert result == 1
    assert calls == []
