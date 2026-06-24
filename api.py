"""Minimal HTTP API entry point for AutoLektor."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from config import TRANSCRIPTION_LANGUAGE, VOICE, WHISPER_MODEL
from exceptions import (
    AutoLektorError,
    EmptyTextError,
    SubtitleGenerationError,
    TextFileReadError,
    TextInputConflictError,
    UnsupportedVariantError,
    UploadSaveError,
    VideoRenderError,
    VoiceoverGenerationError,
)
from providers.ffmpeg_provider import FFmpegProvider
from providers.tts_provider import TTSProvider
from providers.whisper_provider import WhisperProvider
from services.subtitle_service import SubtitleService
from services.voiceover_service import VoiceoverService

app = FastAPI(title="AutoLektor API")
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class VariantSpec:
    filename: str
    media_type: str
    needs_subtitles: bool = False
    ffmpeg_variant: str | None = None


@dataclass(frozen=True)
class RenderWorkspace:
    root: Path
    source_video: Path
    audio: Path
    subtitles: Path

    @classmethod
    def create(cls) -> "RenderWorkspace":
        root = Path(tempfile.mkdtemp(prefix="autolektor-"))
        return cls(
            root=root,
            source_video=root / "source.mp4",
            audio=root / "voiceover.mp3",
            subtitles=root / "subtitles.srt",
        )

    def response_path(self, variant: VariantSpec) -> Path:
        return self.root / variant.filename


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


@app.exception_handler(AutoLektorError)
async def autolektor_error_handler(_request: Request, exc: AutoLektorError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_response())


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple readiness signal for n8n and local checks."""
    return {"status": "ok"}


async def save_upload(upload: UploadFile, destination: Path) -> None:
    try:
        with destination.open("wb") as output_file:
            while chunk := await upload.read(CHUNK_SIZE):
                output_file.write(chunk)
    except Exception as exc:
        raise UploadSaveError() from exc


async def cleanup_work_dir(work_dir: Path) -> None:
    shutil.rmtree(work_dir, ignore_errors=True)


async def read_text_file(text_file: UploadFile) -> str:
    try:
        content = await text_file.read()
        return content.decode("utf-8")
    except Exception as exc:
        raise TextFileReadError() from exc


async def resolve_text_input(text: str | None, text_file: UploadFile | None) -> str:
    cleaned_text = (text or "").strip()
    if cleaned_text and text_file is not None:
        raise TextInputConflictError()
    if text_file is not None:
        cleaned_file_text = (await read_text_file(text_file)).strip()
        if not cleaned_file_text:
            raise EmptyTextError()
        return cleaned_file_text
    if not cleaned_text:
        raise EmptyTextError()
    return cleaned_text


def resolve_voice(voice: str | None) -> str:
    return (voice or "").strip() or VOICE


async def create_voiceover(text: str, workspace: RenderWorkspace, voice: str) -> None:
    try:
        voiceover_service = VoiceoverService(TTSProvider(voice=voice))
        await voiceover_service.create_and_adjust_voiceover(
            text=text,
            source_video_path=str(workspace.source_video),
            output_audio_path=str(workspace.audio),
        )
    except Exception as exc:
        raise VoiceoverGenerationError() from exc


def create_subtitles(workspace: RenderWorkspace) -> None:
    try:
        subtitle_service = SubtitleService(WhisperProvider(model_name=WHISPER_MODEL))
        subtitle_service.generate_srt_from_audio(
            audio_path=str(workspace.audio),
            output_srt_path=str(workspace.subtitles),
            language=TRANSCRIPTION_LANGUAGE,
        )
    except Exception as exc:
        raise SubtitleGenerationError() from exc


def create_video(workspace: RenderWorkspace, variant: VariantSpec) -> None:
    if variant.ffmpeg_variant is None:
        return
    try:
        FFmpegProvider.merge_videos(
            source_video=str(workspace.source_video),
            dubbed_audio=str(workspace.audio),
            subtitles_file=str(workspace.subtitles),
            output_path=str(workspace.response_path(variant)),
            variant=variant.ffmpeg_variant,
        )
    except Exception as exc:
        raise VideoRenderError() from exc


def response_for_variant(workspace: RenderWorkspace, variant: VariantSpec) -> FileResponse:
    return FileResponse(
        workspace.response_path(variant),
        media_type=variant.media_type,
        filename=variant.filename,
        background=BackgroundTask(cleanup_work_dir, workspace.root),
    )


@app.post("/render")
async def render(
    video: Annotated[UploadFile, File()],
    text: Annotated[str | None, Form()] = None,
    variant: Annotated[str, Form()] = "voiceover",
    voice: Annotated[str | None, Form()] = None,
    text_file: Annotated[UploadFile | None, File()] = None,
) -> FileResponse:
    cleaned_text = await resolve_text_input(text, text_file)
    selected_voice = resolve_voice(voice)
    variant_spec = VARIANTS.get(variant)
    if variant_spec is None:
        raise UnsupportedVariantError(variant)

    workspace = RenderWorkspace.create()

    try:
        await save_upload(video, workspace.source_video)
        await create_voiceover(cleaned_text, workspace, selected_voice)
        if variant_spec.needs_subtitles:
            create_subtitles(workspace)
        create_video(workspace, variant_spec)
    except Exception:
        shutil.rmtree(workspace.root, ignore_errors=True)
        raise

    return response_for_variant(workspace, variant_spec)
