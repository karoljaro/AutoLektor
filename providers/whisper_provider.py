"""
Whisper Provider - wraps OpenAI Whisper library.
"""

from typing import Any

import whisper


class WhisperProvider:
    """Provider for speech-to-text using Whisper."""

    def __init__(self, model_name: str = "base") -> None:
        """
        Initialize Whisper Provider.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_name = model_name
        self.model = None

    def load_model(self):
        """Load the Whisper model (lazy loading)."""
        if self.model is None:
            self.model = whisper.load_model(self.model_name)
        return self.model

    def transcribe(self, audio_path: str, language: str = "pl") -> dict[str, Any]:
        """
        Transcribe audio to text with timestamps.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "pl" for Polish)

        Returns:
            Whisper result dict with segments
        """
        model = self.load_model()
        device = str(getattr(model, "device", ""))
        options = {"fp16": False} if device.startswith("cpu") else {}
        result = whisper.transcribe(model, audio=audio_path, language=language, **options)
        return result
