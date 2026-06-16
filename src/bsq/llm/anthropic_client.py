"""Native Anthropic provider client (the real-model path).

Wraps the official ``anthropic`` SDK behind the ``LLMClient`` protocol. Imported lazily
by ``make_client`` so the mock path never requires the SDK, and the SDK client itself is
constructed lazily so this module can be imported (and unit-tested with an injected fake)
without the package installed or a key present.

Cost discipline is built in: ``max_tokens`` stays tight; the frozen ``system`` prefix is
sent as a cache-control block (harmless when the prefix is below the cache minimum). The
model name is never hard-coded — it comes from ``BSQ_MODEL`` (keep it the cheapest
capable model for cost). A real SDK client refuses to construct without an explicit
``BSQ_API_KEY``, so an ambient ``ANTHROPIC_API_KEY`` in the shell can never be spent by
accident. The Messages API has **no seed**, so ``seed`` is accepted and
ignored. A truncated response (``stop_reason == "max_tokens"``) is raised rather than
parsed — a half-written JSON body is the silent killer of the downstream claim counts.
"""

from __future__ import annotations

from typing import Any

from bsq.llm.base import ChatTurn, ProviderConfig


def _make_sdk_client(cfg: ProviderConfig) -> Any:
    # Fail closed. Without an explicit key the SDK silently adopts an ambient
    # ANTHROPIC_API_KEY from the shell and would spend on it. Require BSQ_API_KEY so a
    # real client cannot be built — and thus cannot spend — on an unintended credential.
    if not cfg.api_key:
        raise ValueError("anthropic provider requires an explicit BSQ_API_KEY")
    import anthropic  # lazy: only when we actually talk to the network

    kwargs: dict[str, Any] = {"api_key": cfg.api_key}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    return anthropic.Anthropic(**kwargs)


class AnthropicClient:
    """An ``LLMClient`` backed by the Anthropic Messages API."""

    def __init__(self, cfg: ProviderConfig, *, client: Any = None) -> None:
        if not cfg.model:
            raise ValueError("anthropic provider requires BSQ_MODEL")
        self._cfg = cfg
        self._model = cfg.model
        self._client: Any = client if client is not None else _make_sdk_client(cfg)

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        max_tokens: int = 256,
        temperature: float = 0.0,
        stop: list[str] | None = None,
        seed: int | None = None,  # accepted and ignored — Messages API has no seed
    ) -> str:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Frozen prefix as a cache-control block (no-op below the cache minimum).
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if stop:
            request["stop_sequences"] = stop

        response = self._client.messages.create(**request)

        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ValueError("response truncated (stop_reason=max_tokens); raise max_tokens")
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text":
                text = block.text
                if not isinstance(text, str):
                    raise ValueError(f"expected string text content, got {type(text).__name__}")
                return text
        raise ValueError("no text block in provider response")
