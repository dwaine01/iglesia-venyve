"""Abstracción de STT para que Junta no dependa de un proveedor concreto."""
import os
from abc import ABC, abstractmethod

import httpx


class TranscriptionProviderUnavailable(RuntimeError):
    pass


class MeetingTranscriptionProvider(ABC):
    provider_key: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def transcribe(self, file_handle, filename: str, content_type: str) -> dict: ...


class OpenAIDiarizedTranscriptionProvider(MeetingTranscriptionProvider):
    provider_key = "openai_gpt4o_diarized"

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_STT_API_KEY"))

    async def transcribe(self, file_handle, filename: str, content_type: str) -> dict:
        if not self.is_configured():
            raise TranscriptionProviderUnavailable("STT diarizado: BLOCKED — external credential required")
        async with httpx.AsyncClient(timeout=900) as client:
            response = await client.post(
                os.environ["OPENAI_TRANSCRIPTION_URL"],
                headers={"Authorization": f"Bearer {os.environ['OPENAI_STT_API_KEY']}"},
                files={"file": (filename, file_handle, content_type)},
                data={"model": "gpt-4o-transcribe-diarize", "response_format": "diarized_json", "chunking_strategy": "auto"},
            )
            response.raise_for_status()
            return response.json()


def get_transcription_provider() -> MeetingTranscriptionProvider:
    return OpenAIDiarizedTranscriptionProvider()