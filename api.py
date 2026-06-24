"""Minimal HTTP API entry point for AutoLektor."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from exceptions import (
    AutoLektorError,
    EmptyVideoError,
    EmptyTextError,
    InvalidVideoFileError,
    TextFileReadError,
    TextInputConflictError,
    UnsupportedVideoTypeError,
    UploadSaveError,
    VideoTooLargeError,
)
from pipeline import VARIANTS, VariantSpec, get_variant, render_variant
from providers.ffmpeg_provider import FFmpegProvider

app = FastAPI(title="AutoLektor API")
CHUNK_SIZE = 1024 * 1024
MAX_VIDEO_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024
SUPPORTED_VIDEO_CONTENT_TYPES = {"video/mp4"}
SUPPORTED_VIDEO_SUFFIXES = {".mp4"}


@dataclass(frozen=True)
class RenderWorkspace:
    root: Path
    source_video: Path

    @classmethod
    def create(cls) -> "RenderWorkspace":
        root = Path(tempfile.mkdtemp(prefix="autolektor-"))
        return cls(
            root=root,
            source_video=root / "source.mp4",
        )

    def response_path(self, variant: VariantSpec) -> Path:
        return self.root / variant.filename


@app.exception_handler(AutoLektorError)
async def autolektor_error_handler(_request: Request, exc: AutoLektorError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_response())


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple readiness signal for n8n and local checks."""
    return {"status": "ok"}


def validate_video_upload(upload: UploadFile) -> None:
    filename = getattr(upload, "filename", "") or ""
    suffix = Path(filename).suffix.lower()
    content_type = (getattr(upload, "content_type", "") or "").split(";")[0].strip().lower()

    if suffix not in SUPPORTED_VIDEO_SUFFIXES and content_type not in SUPPORTED_VIDEO_CONTENT_TYPES:
        raise UnsupportedVideoTypeError()


def validate_saved_video_file(video_path: Path) -> None:
    try:
        FFmpegProvider.detect_video_fps(str(video_path))
    except Exception as exc:
        raise InvalidVideoFileError() from exc


async def save_upload(upload: UploadFile, destination: Path) -> None:
    bytes_written = 0
    try:
        with destination.open("wb") as output_file:
            while chunk := await upload.read(CHUNK_SIZE):
                output_file.write(chunk)
                bytes_written += len(chunk)
                if bytes_written > MAX_VIDEO_UPLOAD_SIZE_BYTES:
                    raise VideoTooLargeError(MAX_VIDEO_UPLOAD_SIZE_BYTES)
    except AutoLektorError:
        raise
    except Exception as exc:
        raise UploadSaveError() from exc

    if bytes_written == 0:
        raise EmptyVideoError()


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
    language: Annotated[str | None, Form()] = None,
    text_file: Annotated[UploadFile | None, File()] = None,
) -> FileResponse:
    cleaned_text = await resolve_text_input(text, text_file)
    variant_spec = get_variant(variant)
    validate_video_upload(video)

    workspace = RenderWorkspace.create()
    output_path = workspace.response_path(variant_spec)

    try:
        await save_upload(video, workspace.source_video)
        validate_saved_video_file(workspace.source_video)
        await render_variant(
            text=cleaned_text,
            source_video=workspace.source_video,
            output_path=output_path,
            variant=variant,
            work_dir=workspace.root,
            voice=voice,
            language=language,
        )
    except Exception:
        shutil.rmtree(workspace.root, ignore_errors=True)
        raise

    return response_for_variant(workspace, variant_spec)
