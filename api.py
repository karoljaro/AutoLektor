"""Minimal HTTP API entry point for AutoLektor."""

from pathlib import Path
import shutil
import tempfile
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from config import VOICE
from providers.tts_provider import TTSProvider
from services.voiceover_service import VoiceoverService

app = FastAPI(title="AutoLektor API")
CHUNK_SIZE = 1024 * 1024


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
    if variant != "voiceover":
        raise HTTPException(status_code=400, detail=f"unsupported variant: {variant}")

    work_dir = Path(tempfile.mkdtemp(prefix="autolektor-"))
    source_video = work_dir / "source.mp4"
    output_audio = work_dir / "voiceover.mp3"

    try:
        await save_upload(video, source_video)
        service = VoiceoverService(TTSProvider(voice=VOICE))
        await service.create_and_adjust_voiceover(
            text=cleaned_text,
            source_video_path=str(source_video),
            output_audio_path=str(output_audio),
        )
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise

    return FileResponse(
        output_audio,
        media_type="audio/mpeg",
        filename="voiceover.mp3",
        background=BackgroundTask(cleanup_work_dir, work_dir),
    )
