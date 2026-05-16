"""
Whisper Provider - wraps OpenAI Whisper library.
"""

import whisper


class WhisperProvider:
    """Provider for speech-to-text using Whisper."""

    def __init__(self, model_name="base"):
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

    def transcribe(self, audio_path, language="pl"):
        """
        Transcribe audio to text with timestamps.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "pl" for Polish)

        Returns:
            Whisper result dict with segments
        """
        model = self.load_model()
        result = model.transcribe(audio_path, language=language)
        return result

