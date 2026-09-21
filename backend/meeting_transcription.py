"""Proveedor OpenAI para transcripción diarizada de reuniones."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx


class TranscriptionProviderUnavailable(RuntimeError):
    pass


class TranscriptionProviderDegraded(RuntimeError):
    pass


TranscriptionProviderError = TranscriptionProviderDegraded


@dataclass
class OpenAIDiarizedTranscriptionProvider:
    api_key: str | None
    endpoint: str | None
    model: str | None
    timeout_seconds: float = 180.0
    transport: httpx.AsyncBaseTransport | None = None
    provider_key: str = "openai_diarized"

    def configuration_error(self) -> str | None:
        if not self.api_key or not self.endpoint or not self.model:
            return "not_configured"
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            return "invalid_endpoint"
        if self.model != "gpt-4o-transcribe-diarize":
            return "unsupported_diarization_model"
        return None

    def is_configured(self) -> bool:
        return self.configuration_error() is None

    def status(self) -> dict:
        error = self.configuration_error()
        return {
            "status": "READY" if error is None else "BLOCKED",
            "provider": self.provider_key,
            "model": self.model if error is None else None,
            "error_code": error,
        }

    async def transcribe_path(self, path: Path, language: str = "es") -> dict:
        error = self.configuration_error()
        if error:
            raise TranscriptionProviderUnavailable(error)
        try:
            timeout = httpx.Timeout(self.timeout_seconds, connect=min(10.0, self.timeout_seconds))
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                with path.open("rb") as audio:
                    response = await client.post(
                        self.endpoint,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": (path.name, audio, "audio/mpeg")},
                        data={
                            "model": self.model,
                            "response_format": "diarized_json",
                            "chunking_strategy": "auto",
                            "language": language,
                        },
                    )
            response.raise_for_status()
            payload = response.json()
            segments = payload.get("segments") or []
            if not isinstance(payload, dict) or not isinstance(segments, list):
                raise ValueError("invalid_transcription_payload")
            return {
                "text": str(payload.get("text") or ""),
                "segments": segments,
                "language": payload.get("language") or language,
                "model": self.model,
            }
        except TranscriptionProviderUnavailable:
            raise
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise TranscriptionProviderDegraded(type(exc).__name__) from exc


def get_transcription_provider() -> OpenAIDiarizedTranscriptionProvider:
    timeout_raw = os.environ.get("OPENAI_STT_TIMEOUT_SECONDS")
    try:
        timeout = float(timeout_raw) if timeout_raw else 180.0
    except ValueError:
        timeout = 180.0
    return OpenAIDiarizedTranscriptionProvider(
        api_key=os.environ.get("OPENAI_STT_API_KEY"),
        endpoint=os.environ.get("OPENAI_TRANSCRIPTION_URL"),
        model=os.environ.get("OPENAI_STT_MODEL"),
        timeout_seconds=max(30.0, min(timeout, 600.0)),
    )