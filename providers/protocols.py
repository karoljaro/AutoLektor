"""Provider Protocols for dependency injection and static typing.

Defines Protocols for the external providers so services can depend on
interfaces rather than concrete implementations.
"""
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class TTSProtocol(Protocol):
    """Protocol for TTS providers."""

    async def generate_voiceover(self, text: str, output_path: str, rate: str | None = None) -> None:  # pragma: no cover
        ...


@runtime_checkable
class WhisperProtocol(Protocol):
    """Protocol for Whisper-like transcription providers."""

    def transcribe(self, audio_path: str, language: str = "pl") -> dict[str, Any]:  # pragma: no cover
        ...


@runtime_checkable
class FFmpegProtocol(Protocol):
    """Protocol for FFmpeg provider (optional)."""

    def merge_videos(self, source_video: str, dubbed_audio: str, subtitles_file: str, output_path: str, variant: str = "full") -> None:  # pragma: no cover
        ...

