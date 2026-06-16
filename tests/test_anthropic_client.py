"""Native Anthropic client: request mapping + guards, verified offline with a fake SDK.

No network, no API key, and no real ``anthropic`` import — a fake client records the
kwargs and returns canned content blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bsq.llm.anthropic_client import AnthropicClient
from bsq.llm.base import ChatTurn, ProviderConfig


@dataclass
class _Block:
    type: str
    text: str = ""


@dataclass
class _Response:
    content: list[_Block]
    stop_reason: str = "end_turn"


@dataclass
class _Messages:
    response: _Response
    captured: dict[str, Any] = field(default_factory=dict)

    def create(self, **kwargs: Any) -> _Response:
        self.captured = kwargs
        return self.response


@dataclass
class _FakeSDK:
    messages: _Messages


def _client(response: _Response) -> tuple[AnthropicClient, _Messages]:
    sdk = _FakeSDK(messages=_Messages(response=response))
    cfg = ProviderConfig(provider="anthropic", api_key="k", model="test-model")
    return AnthropicClient(cfg, client=sdk), sdk.messages


def test_complete_returns_first_text_block() -> None:
    client, _ = _client(_Response(content=[_Block("text", "hello")]))
    assert client.complete(system="s", messages=[ChatTurn("user", "hi")]) == "hello"


def test_skips_thinking_block_before_text() -> None:
    client, _ = _client(_Response(content=[_Block("thinking", "..."), _Block("text", "answer")]))
    assert client.complete(system="s", messages=[ChatTurn("user", "hi")]) == "answer"


def test_request_mapping_and_no_seed() -> None:
    client, messages = _client(_Response(content=[_Block("text", "ok")]))
    client.complete(
        system="sys", messages=[ChatTurn("user", "u")], temperature=0.0, seed=7, stop=["END"]
    )
    captured = messages.captured
    assert captured["model"] == "test-model"
    assert "seed" not in captured  # Messages API has no seed
    assert captured["temperature"] == 0.0
    assert captured["stop_sequences"] == ["END"]
    assert captured["messages"] == [{"role": "user", "content": "u"}]
    # system is a cache-control block carrying the frozen prefix
    assert captured["system"][0]["text"] == "sys"
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_requires_model() -> None:
    sdk = _FakeSDK(messages=_Messages(response=_Response(content=[_Block("text", "ok")])))
    with pytest.raises(ValueError, match="BSQ_MODEL"):
        AnthropicClient(ProviderConfig(provider="anthropic", api_key="k"), client=sdk)


def test_truncated_response_raises() -> None:
    client, _ = _client(_Response(content=[_Block("text", "{partial")], stop_reason="max_tokens"))
    with pytest.raises(ValueError, match="truncated"):
        client.complete(system="s", messages=[ChatTurn("user", "hi")])


def test_no_text_block_raises() -> None:
    client, _ = _client(_Response(content=[_Block("thinking", "...")]))
    with pytest.raises(ValueError, match="no text block"):
        client.complete(system="s", messages=[ChatTurn("user", "hi")])


def test_real_client_requires_explicit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Build the REAL sdk path (no injected fake). An ambient ANTHROPIC_API_KEY in the shell
    # must NOT let an empty BSQ_API_KEY spend: construction fails closed before any SDK call.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ambient-must-not-be-used")
    with pytest.raises(ValueError, match="BSQ_API_KEY"):
        AnthropicClient(ProviderConfig(provider="anthropic", model="test-model"))
