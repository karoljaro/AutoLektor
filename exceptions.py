"""Domain exceptions exposed by the AutoLektor API."""

from http import HTTPStatus


class AutoLektorError(Exception):
    """Base class for expected API errors."""

    error_name = "AUTOLEKTOR_ERROR"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    stage = "unknown"
    retryable = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_response(self) -> dict[str, str | bool]:
        return {
            "error": self.error_name,
            "detail": self.message,
            "stage": self.stage,
            "retryable": self.retryable,
        }


class EmptyTextError(AutoLektorError):
    error_name = "EMPTY_TEXT"
    status_code = HTTPStatus.BAD_REQUEST
    stage = "input"

    def __init__(self) -> None:
        super().__init__("text is required")


class UnsupportedVariantError(AutoLektorError):
    error_name = "UNSUPPORTED_VARIANT"
    status_code = HTTPStatus.BAD_REQUEST
    stage = "input"

    def __init__(self, variant: str) -> None:
        super().__init__(f"unsupported variant: {variant}")


class TextInputConflictError(AutoLektorError):
    error_name = "TEXT_INPUT_CONFLICT"
    status_code = HTTPStatus.BAD_REQUEST
    stage = "input"

    def __init__(self) -> None:
        super().__init__("provide either text or text_file, not both")


class TextFileReadError(AutoLektorError):
    error_name = "TEXT_FILE_READ_FAILED"
    status_code = HTTPStatus.BAD_REQUEST
    stage = "input"

    def __init__(self) -> None:
        super().__init__("failed to read text_file as UTF-8 text")


class UploadSaveError(AutoLektorError):
    error_name = "UPLOAD_SAVE_FAILED"
    stage = "upload"
    retryable = True

    def __init__(self) -> None:
        super().__init__("failed to save uploaded video")


class VoiceoverGenerationError(AutoLektorError):
    error_name = "VOICEOVER_GENERATION_FAILED"
    stage = "voiceover"
    retryable = True

    def __init__(self) -> None:
        super().__init__("failed to generate voiceover")


class SubtitleGenerationError(AutoLektorError):
    error_name = "SUBTITLE_GENERATION_FAILED"
    stage = "subtitles"
    retryable = True

    def __init__(self) -> None:
        super().__init__("failed to generate subtitles")


class VideoRenderError(AutoLektorError):
    error_name = "VIDEO_RENDER_FAILED"
    stage = "video_render"
    retryable = True

    def __init__(self) -> None:
        super().__init__("failed to render video")
