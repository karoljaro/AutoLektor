"""Domain exceptions exposed by the AutoLektor API."""

from http import HTTPStatus


class AutoLektorError(Exception):
    """Base class for expected API errors."""

    error_name = "AUTOLEKTOR_ERROR"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_response(self) -> dict[str, str]:
        return {"error": self.error_name, "detail": self.message}


class EmptyTextError(AutoLektorError):
    error_name = "EMPTY_TEXT"
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self) -> None:
        super().__init__("text is required")


class UnsupportedVariantError(AutoLektorError):
    error_name = "UNSUPPORTED_VARIANT"
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self, variant: str) -> None:
        super().__init__(f"unsupported variant: {variant}")


class UploadSaveError(AutoLektorError):
    error_name = "UPLOAD_SAVE_FAILED"

    def __init__(self) -> None:
        super().__init__("failed to save uploaded video")


class VoiceoverGenerationError(AutoLektorError):
    error_name = "VOICEOVER_GENERATION_FAILED"

    def __init__(self) -> None:
        super().__init__("failed to generate voiceover")


class SubtitleGenerationError(AutoLektorError):
    error_name = "SUBTITLE_GENERATION_FAILED"

    def __init__(self) -> None:
        super().__init__("failed to generate subtitles")


class VideoRenderError(AutoLektorError):
    error_name = "VIDEO_RENDER_FAILED"

    def __init__(self) -> None:
        super().__init__("failed to render video")
