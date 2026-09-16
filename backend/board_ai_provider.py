"""Proveedor IA portable y opcional para borradores de Junta Directiva."""
import json
import os
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


class BoardAIProviderUnavailable(RuntimeError):
    pass


class BoardAIProviderDegraded(RuntimeError):
    pass


@dataclass
class BoardAIProvider:
    endpoint_url: str | None
    api_key: str | None
    model: str | None
    timeout_seconds: float = 30.0
    transport: httpx.AsyncBaseTransport | None = None
    provider_key: str = "openai_compatible_http"

    def configuration_error(self) -> str | None:
        if not self.endpoint_url or not self.api_key or not self.model:
            return "not_configured"
        parsed = urlparse(self.endpoint_url)
        if parsed.scheme != "https" or not parsed.hostname:
            return "invalid_endpoint"
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

    async def generate_json(self, system_message: str, prompt: str) -> dict:
        error = self.configuration_error()
        if error:
            raise BoardAIProviderUnavailable(error)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            timeout = httpx.Timeout(self.timeout_seconds, connect=min(5.0, self.timeout_seconds))
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                response = await client.post(
                    self.endpoint_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                if not isinstance(result, dict):
                    raise ValueError("provider_payload_not_object")
                return result
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BoardAIProviderDegraded(type(exc).__name__) from exc


def get_board_ai_provider() -> BoardAIProvider:
    timeout_raw = os.environ.get("BOARD_AI_TIMEOUT_SECONDS")
    try:
        timeout = float(timeout_raw) if timeout_raw else 30.0
    except ValueError:
        timeout = 30.0
    return BoardAIProvider(
        endpoint_url=os.environ.get("BOARD_AI_ENDPOINT_URL"),
        api_key=os.environ.get("BOARD_AI_API_KEY"),
        model=os.environ.get("BOARD_AI_MODEL"),
        timeout_seconds=max(5.0, min(timeout, 120.0)),
    )