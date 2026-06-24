"""FFmpeg Provider - wraps FFmpeg command-line tools."""

import json
import subprocess
from collections.abc import Sequence
from fractions import Fraction

from config import AUDIO_CODEC, VIDEO_CODEC
from helpers.preflight import ensure_commands_available, escape_ffmpeg_filter_path


class FFmpegProvider:
    """Provider for video operations using FFmpeg."""

    @staticmethod
    def _run_ffmpeg(command: Sequence[str]) -> None:
        """Run FFmpeg command and re-raise readable errors."""
        ensure_commands_available("ffmpeg")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "unknown ffmpeg error").strip()
            raise RuntimeError(f"FFmpeg command failed: {details}") from exc

    @staticmethod
    def _run_ffprobe(command: Sequence[str]) -> str:
        """Run FFprobe command and return stdout."""
        ensure_commands_available("ffprobe")
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            return result.stdout
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "unknown ffprobe error").strip()
            raise RuntimeError(f"FFprobe command failed: {details}") from exc

    @staticmethod
    def _normalize_fps(raw_fps: object) -> str | None:
        if not isinstance(raw_fps, str) or not raw_fps.strip():
            return None
        try:
            fps = Fraction(raw_fps.strip())
        except (ValueError, ZeroDivisionError):
            return None
        if fps <= 0:
            return None
        if fps.denominator == 1:
            return str(fps.numerator)
        return f"{fps.numerator}/{fps.denominator}"

    @staticmethod
    def detect_video_fps(source_video: str) -> str:
        """Detect source video FPS as an FFmpeg-compatible value."""
        output = FFmpegProvider._run_ffprobe([
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate,r_frame_rate",
            "-of", "json",
            source_video,
        ])
        try:
            data = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FFprobe returned invalid JSON while detecting video FPS") from exc

        streams = data.get("streams")
        if not isinstance(streams, list) or not streams:
            raise RuntimeError("FFprobe did not return a video stream while detecting video FPS")

        stream = streams[0]
        if not isinstance(stream, dict):
            raise RuntimeError("FFprobe returned invalid video stream data while detecting video FPS")

        for field in ("avg_frame_rate", "r_frame_rate"):
            fps = FFmpegProvider._normalize_fps(stream.get(field))
            if fps is not None:
                return fps

        raise RuntimeError("Could not determine source video FPS")

    @staticmethod
    def _subtitles_filter(source_video: str, subtitles_file: str) -> str:
        fps = FFmpegProvider.detect_video_fps(source_video)
        return f"fps={fps},subtitles={escape_ffmpeg_filter_path(subtitles_file)}"

    @staticmethod
    def merge_videos(
            source_video: str,
            dubbed_audio: str,
            subtitles_file: str,
            output_path: str,
            variant: str = "full",
    ) -> None:
        """
        Merge video, audio, and optionally subtitles using FFmpeg.

        Args:
            source_video: Path to source video file
            dubbed_audio: Path to dubbed audio (MP3/AAC)
            subtitles_file: Path to SRT subtitles file
            output_path: Where to save the output video
            variant: "full" (video+audio+subtitles), "dubbed" (video+audio), or "subtitles_only"
        """
        match variant:
            case "full":
                command = [
                    "ffmpeg", "-hide_banner", "-nostdin", "-y",
                    "-i", source_video,
                    "-i", dubbed_audio,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-vf", FFmpegProvider._subtitles_filter(source_video, subtitles_file),
                    "-c:v", VIDEO_CODEC,
                    "-c:a", AUDIO_CODEC,
                    output_path
                ]
            case "dubbed":
                command = [
                    "ffmpeg", "-hide_banner", "-nostdin", "-y",
                    "-i", source_video,
                    "-i", dubbed_audio,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", AUDIO_CODEC,
                    output_path
                ]
            case "subtitles_only":
                command = [
                    "ffmpeg", "-hide_banner", "-nostdin", "-y",
                    "-i", source_video,
                    "-map", "0:v:0",
                    "-map", "0:a:0",
                    "-vf", FFmpegProvider._subtitles_filter(source_video, subtitles_file),
                    "-c:v", VIDEO_CODEC,
                    "-c:a", "copy",
                    output_path
                ]
            case _:
                raise ValueError(f"Unknown variant: {variant}")

        FFmpegProvider._run_ffmpeg(command)
