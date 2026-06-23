"""Minimal HTTP API entry point for AutoLektor."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from config import TRANSCRIPTION_LANGUAGE, VOICE, WHISPER_MODEL
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


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple readiness signal for n8n and local checks."""
    return {"status": "ok"}


async def save_upload(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as output_file:
        while chunk := await upload.read(CHUNK_SIZE):
            output_file.write(chunk)


async def cleanup_work_dir(work_dir: Path) -> None:
    shutil.rmtree(work_dir, ignore_errors=True)


async def create_voiceover(text: str, workspace: RenderWorkspace) -> None:
    voiceover_service = VoiceoverService(TTSProvider(voice=VOICE))
    await voiceover_service.create_and_adjust_voiceover(
        text=text,
        source_video_path=str(workspace.source_video),
        output_audio_path=str(workspace.audio),
    )


def create_subtitles(workspace: RenderWorkspace) -> None:
    subtitle_service = SubtitleService(WhisperProvider(model_name=WHISPER_MODEL))
    subtitle_service.generate_srt_from_audio(
        audio_path=str(workspace.audio),
        output_srt_path=str(workspace.subtitles),
        language=TRANSCRIPTION_LANGUAGE,
    )


def create_video(workspace: RenderWorkspace, variant: VariantSpec) -> None:
    if variant.ffmpeg_variant is None:
        return
    FFmpegProvider.merge_videos(
        source_video=str(workspace.source_video),
        dubbed_audio=str(workspace.audio),
        subtitles_file=str(workspace.subtitles),
        output_path=str(workspace.response_path(variant)),
        variant=variant.ffmpeg_variant,
    )


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
    text: Annotated[str, Form()],
    variant: Annotated[str, Form()] = "voiceover",
) -> FileResponse:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=400, detail="text is required")
    variant_spec = VARIANTS.get(variant)
    if variant_spec is None:
        raise HTTPException(status_code=400, detail=f"unsupported variant: {variant}")

    workspace = RenderWorkspace.create()

    try:
        await save_upload(video, workspace.source_video)
        await create_voiceover(cleaned_text, workspace)
        if variant_spec.needs_subtitles:
            create_subtitles(workspace)
        create_video(workspace, variant_spec)
    except Exception:
        shutil.rmtree(workspace.root, ignore_errors=True)
        raise

    return response_for_variant(workspace, variant_spec)
