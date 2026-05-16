"""Voiceover Service - orchestrates TTS and audio processing."""

import math

from helpers.duration_helpers import get_duration


class VoiceoverService:
    """Service for generating and adjusting voiceovers."""

    def __init__(self, tts_provider):
        """Initialize Voiceover service.

        Args:
            tts_provider: Instance of TTSProvider
        """
        self.tts_provider = tts_provider

    async def create_and_adjust_voiceover(self, text, source_video_path, output_audio_path):
        """Generate voiceover and automatically adjust speed if needed.

        Args:
            text: Text to convert to speech
            source_video_path: Path to source video (to match duration)
            output_audio_path: Where to save the audio file
        """
        print("\n[STEP 1/3] Generating the base voiceover...")

        # Generate initial voiceover
        await self.tts_provider.generate_voiceover(text, output_audio_path)

        # Check durations
        video_duration = get_duration(source_video_path)
        audio_duration = get_duration(output_audio_path)

        print(f"-> Video duration: {video_duration:.2f} s")
        print(f"-> Audio duration: {audio_duration:.2f} s")

        # Adjust speed if needed
        if audio_duration > video_duration:
            ratio = audio_duration / video_duration
            percent = math.ceil((ratio - 1) * 100)

            print(f"-> [ACTION] Audio is too long! Speeding up the voiceover automatically by +{percent}%...")

            new_rate = f"+{percent}%"
            await self.tts_provider.generate_voiceover(text, output_audio_path, rate=new_rate)
            print(f"-> Saved adjusted, sped-up version: {output_audio_path}")
        else:
            print("-> Audio fits within the video duration. Speed unchanged.")

