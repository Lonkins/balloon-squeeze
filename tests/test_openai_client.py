"""OpenAI-compatible client: wire format verified offline via httpx.MockTransport."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from bsq.llm.base import ChatTurn, ProviderConfig
from bsq.llm.openai_compatible import OpenAICompatibleClient

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> OpenAICompatibleClient:
    cfg = ProviderConfig(
        provider="openai-compatible", base_url="http://x", model="m", api_key="k"
    )
    http = httpx.Client(base_url="http://x", transport=httpx.MockTransport(handler))
    return OpenAICompatibleClient(cfg, http_client=http)


def test_happy_path_returns_content() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    assert _client(handler).complete(system="s", messages=[ChatTurn("user", "hi")]) == "hello"


def test_request_carries_model_messages_seed_and_auth() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _client(handler).complete(system="sys", messages=[ChatTurn("user", "u")], seed=11)
    assert captured["model"] == "m"
    assert captured["seed"] == 11
    assert captured["temperature"] == 0.0
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["messages"][1] == {"role": "user", "content": "u"}
    assert captured["auth"] == "Bearer k"


def test_malformed_response_raises_value_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(ValueError):
        _client(handler).complete(system="s", messages=[ChatTurn("user", "hi")])


def test_http_error_propagates() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(httpx.HTTPStatusError):
        _client(handler).complete(system="s", messages=[ChatTurn("user", "hi")])


def test_requires_base_url_and_model() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleClient(ProviderConfig(provider="openai-compatible", model="m"))
    with pytest.raises(ValueError):
        OpenAICompatibleClient(ProviderConfig(provider="openai-compatible", base_url="http://x"))
