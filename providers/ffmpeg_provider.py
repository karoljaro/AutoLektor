"""
FFmpeg Provider - wraps FFmpeg command-line tools.
"""

import subprocess


class FFmpegProvider:
    """Provider for video operations using FFmpeg."""

    @staticmethod
    def merge_videos(source_video, dubbed_audio, subtitles_file, output_path, variant="full"):
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
                    "ffmpeg", "-y",
                    "-i", source_video,
                    "-i", dubbed_audio,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-vf", f"fps=30,subtitles={subtitles_file}",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    output_path
                ]
            case "dubbed":
                command = [
                    "ffmpeg", "-y",
                    "-i", source_video,
                    "-i", dubbed_audio,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    output_path
                ]
            case "subtitles_only":
                command = [
                    "ffmpeg", "-y",
                    "-i", source_video,
                    "-map", "0:v:0",
                    "-map", "0:a:0",
                    "-vf", f"fps=30,subtitles={subtitles_file}",
                    "-c:v", "libx264",
                    "-c:a", "copy",
                    output_path
                ]
            case _:
                raise ValueError(f"Unknown variant: {variant}")

        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

