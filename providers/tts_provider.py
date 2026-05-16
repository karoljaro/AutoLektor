"""TTS Provider - wraps edge-tts library."""

import edge_tts


class TTSProvider:
    """Provider for Text-to-Speech using edge-tts."""

    def __init__(self, voice):
        """Initialize TTS provider.

        Args:
            voice: Voice identifier (e.g., "pl-PL-ZofiaNeural")
        """
        self.voice = voice

    async def generate_voiceover(self, text, output_path, rate=None):
        """Generate voiceover from text.

        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            rate: Optional speech rate (e.g., "+20%")
        """
        if rate is None:
            communicate = edge_tts.Communicate(text, self.voice)
        else:
            if not isinstance(rate, str):
                raise TypeError("rate must be a string like '+10%'")
            communicate = edge_tts.Communicate(text, self.voice, rate=rate)
        await communicate.save(output_path)

