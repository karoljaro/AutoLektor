"""Shared rendering pipeline for API and CLI entry points."""

from dataclasses import dataclass
from pathlib import Path

from config import TRANSCRIPTION_LANGUAGE, VOICE, WHISPER_MODEL
from exceptions import (
    EmptyTextError,
    SubtitleGenerationError,
    UnsupportedVariantError,
    VideoRenderError,
    VoiceoverGenerationError,
)
from helpers.preflight import ensure_parent_dirs_exist
from providers.ffmpeg_provider import FFmpegProvider
from providers.tts_provider import TTSProvider
from providers.whisper_provider import WhisperProvider
from services.subtitle_service import SubtitleService
from services.voiceover_service import VoiceoverService


@dataclass(frozen=True)
class VariantSpec:
    filename: str
    media_type: str
    needs_subtitles: bool = False
    ffmpeg_variant: str | None = None


VARIANTS = {
    "voiceover": VariantSpec(filename="voiceover.mp3", media_type="audio/mpeg"),
    "subtitles": VariantSpec(filename="subtitles.srt", media_type="application/x-subrip", needs_subtitles=True),
    "dubbed": VariantSpec(filename="dubbed.mp4", media_type="video/mp4", ffmpeg_variant="dubbed"),
    "subtitled": VariantSpec(
        filename="subtitled.mp4",
        media_type="video/mp4",
        needs_subtitles=True,
        ffmpeg_variant="subtitles_only",
    ),
    "full": VariantSpec(
        filename="full.mp4",
        media_type="video/mp4",
        needs_subtitles=True,
        ffmpeg_variant="full",
    ),
}


def resolve_voice(voice: str | None) -> str:
    return (voice or "").strip() or VOICE


def resolve_language(language: str | None) -> str:
    return (language or "").strip() or TRANSCRIPTION_LANGUAGE


def get_variant(variant: str) -> VariantSpec:
    variant_spec = VARIANTS.get(variant)
    if variant_spec is None:
        raise UnsupportedVariantError(variant)
    return variant_spec


async def create_voiceover(text: str, source_video: Path, output_audio: Path, voice: str) -> None:
    try:
        voiceover_service = VoiceoverService(TTSProvider(voice=voice))
        await voiceover_service.create_and_adjust_voiceover(
            text=text,
            source_video_path=str(source_video),
            output_audio_path=str(output_audio),
        )
    except Exception as exc:
        raise VoiceoverGenerationError() from exc


def create_subtitles(audio_path: Path, output_srt: Path, language: str) -> None:
    try:
        subtitle_service = SubtitleService(WhisperProvider(model_name=WHISPER_MODEL))
        subtitle_service.generate_srt_from_audio(
            audio_path=str(audio_path),
            output_srt_path=str(output_srt),
            language=language,
        )
    except Exception as exc:
        raise SubtitleGenerationError() from exc


def create_video(
    source_video: Path,
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
    variant: VariantSpec,
) -> None:
    if variant.ffmpeg_variant is None:
        return
    try:
        FFmpegProvider.merge_videos(
            source_video=str(source_video),
            dubbed_audio=str(audio_path),
            subtitles_file=str(subtitles_path),
            output_path=str(output_path),
            variant=variant.ffmpeg_variant,
        )
    except Exception as exc:
        raise VideoRenderError() from exc


async def render_variant(
    *,
    text: str,
    source_video: Path,
    output_path: Path,
    variant: str,
    work_dir: Path,
    voice: str | None = None,
    language: str | None = None,
) -> Path:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise EmptyTextError()

    variant_spec = get_variant(variant)
    source_video = Path(source_video)
    output_path = Path(output_path)
    work_dir = Path(work_dir)

    work_dir.mkdir(parents=True, exist_ok=True)
    ensure_parent_dirs_exist(str(output_path))

    audio_path = output_path if variant == "voiceover" else work_dir / "voiceover.mp3"
    subtitles_path = output_path if variant == "subtitles" else work_dir / "subtitles.srt"

    await create_voiceover(cleaned_text, source_video, audio_path, resolve_voice(voice))
    if variant_spec.needs_subtitles:
        create_subtitles(audio_path, subtitles_path, resolve_language(language))
    create_video(source_video, audio_path, subtitles_path, output_path, variant_spec)

    return output_path
