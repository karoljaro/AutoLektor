"""Minimal HTTP API entry point for AutoLektor."""

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
SUPPORTED_VARIANTS = {"voiceover", "subtitles", "dubbed", "subtitled"}


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


@app.post("/render")
async def render(
    video: Annotated[UploadFile, File()],
    text: Annotated[str, Form()],
    variant: Annotated[str, Form()] = "voiceover",
) -> FileResponse:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise HTTPException(status_code=400, detail="text is required")
    if variant not in SUPPORTED_VARIANTS:
        raise HTTPException(status_code=400, detail=f"unsupported variant: {variant}")

    work_dir = Path(tempfile.mkdtemp(prefix="autolektor-"))
    source_video = work_dir / "source.mp4"
    output_audio = work_dir / "voiceover.mp3"
    output_srt = work_dir / "subtitles.srt"
    output_video = work_dir / f"{variant}.mp4"

    try:
        await save_upload(video, source_video)
        voiceover_service = VoiceoverService(TTSProvider(voice=VOICE))
        await voiceover_service.create_and_adjust_voiceover(
            text=cleaned_text,
            source_video_path=str(source_video),
            output_audio_path=str(output_audio),
        )
        if variant in {"subtitles", "subtitled"}:
            subtitle_service = SubtitleService(WhisperProvider(model_name=WHISPER_MODEL))
            subtitle_service.generate_srt_from_audio(
                audio_path=str(output_audio),
                output_srt_path=str(output_srt),
                language=TRANSCRIPTION_LANGUAGE,
            )
        if variant in {"dubbed", "subtitled"}:
            ffmpeg_variant = "subtitles_only" if variant == "subtitled" else "dubbed"
            FFmpegProvider.merge_videos(
                source_video=str(source_video),
                dubbed_audio=str(output_audio),
                subtitles_file=str(output_srt),
                output_path=str(output_video),
                variant=ffmpeg_variant,
            )
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise

    if variant == "subtitles":
        response_path = output_srt
        media_type = "application/x-subrip"
        filename = "subtitles.srt"
    elif variant in {"dubbed", "subtitled"}:
        response_path = output_video
        media_type = "video/mp4"
        filename = f"{variant}.mp4"
    else:
        response_path = output_audio
        media_type = "audio/mpeg"
        filename = "voiceover.mp3"

    return FileResponse(
        response_path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(cleanup_work_dir, work_dir),
    )
