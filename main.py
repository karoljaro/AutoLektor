"""Command-line entry point for AutoLektor."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
import tempfile
import warnings

from exceptions import AutoLektorError, EmptyTextError
from helpers import file_exists, read_text_from_file
from helpers.preflight import ensure_commands_available, ensure_parent_dirs_exist
from logger import get_logger
from pipeline import VARIANTS, render_variant

warnings.filterwarnings("ignore")

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate AutoLektor voiceover, subtitles or video variants.")
    parser.add_argument("video", type=Path, help="Source MP4 video path.")
    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Text to render into the output.")
    text_group.add_argument("--text-file", type=Path, help="UTF-8 text file to render into the output.")
    parser.add_argument("--variant", required=True, choices=sorted(VARIANTS), help="Output variant to generate.")
    parser.add_argument("-o", "--output", type=Path, help="Output path. Defaults to <input>_<variant>.<ext>.")
    parser.add_argument("--voice", help="Optional edge-tts voice. Defaults to config.VOICE.")
    parser.add_argument("--language", help="Optional subtitle language. Defaults to config.TRANSCRIPTION_LANGUAGE.")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def default_output_path(video_path: Path, variant: str) -> Path:
    suffix = Path(VARIANTS[variant].filename).suffix
    return video_path.with_name(f"{video_path.stem}_{variant}{suffix}")


def resolve_output_path(video_path: Path, output_path: Path | None, variant: str) -> Path:
    if output_path is not None:
        return resolve_path(output_path)
    return default_output_path(resolve_path(video_path), variant)


def resolve_cli_text(text: str | None, text_file: Path | None) -> str:
    if text is not None:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise EmptyTextError()
        return cleaned_text

    loaded_text = read_text_from_file(str(text_file))
    if not loaded_text:
        raise EmptyTextError()
    return loaded_text


def preflight_checks(video_path: Path, output_path: Path, text_file: Path | None = None) -> None:
    ensure_commands_available("ffmpeg", "ffprobe")
    if not file_exists(str(video_path)):
        raise FileNotFoundError(f"Source video not found: {video_path}")
    if text_file is not None and not file_exists(str(text_file)):
        raise FileNotFoundError(f"Text file not found: {text_file}")
    ensure_parent_dirs_exist(str(output_path))


async def run_cli(args: argparse.Namespace) -> int:
    video_path = resolve_path(args.video)
    text_file = resolve_path(args.text_file) if args.text_file is not None else None
    output_path = resolve_output_path(video_path, args.output, args.variant)

    try:
        preflight_checks(video_path, output_path, text_file)
        text = resolve_cli_text(args.text, text_file)
        with tempfile.TemporaryDirectory(prefix="autolektor-cli-") as temp_dir:
            await render_variant(
                text=text,
                source_video=video_path,
                output_path=output_path,
                variant=args.variant,
                work_dir=Path(temp_dir),
                voice=args.voice,
                language=args.language,
            )
        logger.info("Saved output: %s", output_path)
        return 0
    except AutoLektorError as exc:
        logger.error("CLI render failed: %s: %s", exc.error_name, exc.message)
        return 1
    except Exception as exc:
        logger.exception("CLI render failed: %s", exc)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(run_cli(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
