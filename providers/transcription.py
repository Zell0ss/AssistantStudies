"""Transcription provider with OpenAI Whisper implementation"""
from loguru import logger
from openai import OpenAI

from .base import BaseProvider
from .config import TranscriptionConfig


class TranscriptionProvider(BaseProvider):
    """OpenAI Whisper transcription provider (concrete, not abstract)"""

    def __init__(self, config: TranscriptionConfig):
        """Initialize Whisper transcription provider"""
        super().__init__(config)

        # Initialize OpenAI client
        self.client = OpenAI(api_key=config.api_key)

        logger.info("Initialized Whisper transcription provider")

    def health_check(self) -> bool:
        """Verify OpenAI API key is valid"""
        try:
            # Simple API check
            models = self.client.models.list()
            logger.info("Transcription provider health check passed")
            return True
        except Exception as e:
            logger.error(f"Transcription provider health check failed: {e}")
            raise

    def transcribe_audio(self, audio_file_path: str, language: str = None) -> str:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_file_path: Path to audio file
            language: Language code (e.g., 'es', 'en'), auto-detect if None

        Returns:
            Transcribed text
        """
        def _transcribe():
            with open(audio_file_path, 'rb') as audio_file:
                kwargs = {'file': audio_file, 'model': 'whisper-1'}
                if language:
                    kwargs['language'] = language

                transcript = self.client.audio.transcriptions.create(**kwargs)
                return transcript.text

        try:
            # Use retry wrapper for API call
            text = self._call_with_retry(_transcribe)
            logger.info(f"Transcribed audio: {audio_file_path} ({len(text)} chars)")
            return text
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            raise
