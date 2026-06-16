"""The single LLM abstraction. No vendor SDK is imported anywhere else in the code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

#: Providers recognized by the configuration layer. Phase 0 ships only ``mock``;
#: the cloud/local providers are wired in later phases behind this same interface.
KNOWN_PROVIDERS: frozenset[str] = frozenset(
    {"mock", "anthropic", "openai-compatible", "ollama"}
)


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """One turn in a conversation handed to the model."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Immutable provider settings, normally built from the environment."""

    provider: str
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    seed: int | None = None
    temperature: float = 0.0


@runtime_checkable
class LLMClient(Protocol):
    """The only surface the engine talks to."""

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        max_tokens: int = 256,
        temperature: float = 0.0,
        stop: list[str] | None = None,
        seed: int | None = None,
    ) -> str:
        """Return the model's completion as text."""
        ...


def make_client(cfg: ProviderConfig) -> LLMClient:
    """Build the client for a provider. Phase 0 implements ``mock`` only."""
    if cfg.provider == "mock":
        from bsq.llm.mock_client import MockClient

        return MockClient(cfg)
    if cfg.provider == "openai-compatible":
        from bsq.llm.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient(cfg)
    if cfg.provider == "anthropic":
        from bsq.llm.anthropic_client import AnthropicClient

        return AnthropicClient(cfg)
    if cfg.provider in KNOWN_PROVIDERS:
        raise NotImplementedError(
            f"provider {cfg.provider!r} is not implemented yet"
        )
    raise ValueError(
        f"unknown provider {cfg.provider!r}; expected one of {sorted(KNOWN_PROVIDERS)}"
    )
