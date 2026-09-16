import asyncio

import httpx
import pytest

from board_ai_provider import (
    BoardAIProvider,
    BoardAIProviderDegraded,
    BoardAIProviderUnavailable,
)


def test_unconfigured_provider_is_blocked():
    provider = BoardAIProvider(endpoint_url=None, api_key=None, model=None)

    assert provider.status() == {
        "status": "BLOCKED",
        "provider": "openai_compatible_http",
        "model": None,
        "error_code": "not_configured",
    }
    with pytest.raises(BoardAIProviderUnavailable):
        asyncio.run(provider.generate_json("system", "prompt"))


def test_invalid_non_https_endpoint_is_blocked():
    provider = BoardAIProvider(endpoint_url="http://127.0.0.1/chat", api_key="secret", model="model")

    assert provider.status()["error_code"] == "invalid_endpoint"


def test_configured_provider_returns_structured_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"minute_draft": {"title": "Acta"}}'}}]},
        )

    provider = BoardAIProvider(
        endpoint_url="https://provider.example/v1/chat/completions",
        api_key="test-key",
        model="portable-model",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(provider.generate_json("system", "prompt"))

    assert result == {"minute_draft": {"title": "Acta"}}
    assert provider.status()["status"] == "READY"


def test_provider_failure_is_degraded_without_secret_leak():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="test-key must never be returned")

    provider = BoardAIProvider(
        endpoint_url="https://provider.example/v1/chat/completions",
        api_key="test-key",
        model="portable-model",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BoardAIProviderDegraded) as error:
        asyncio.run(provider.generate_json("system", "prompt"))
    assert "test-key" not in str(error.value)