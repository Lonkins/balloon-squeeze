"""Native Anthropic provider client (the real-model path).

Wraps the official ``anthropic`` SDK behind the ``LLMClient`` protocol. Imported lazily
by ``make_client`` so the mock path never requires the SDK, and the SDK client itself is
constructed lazily so this module can be imported (and unit-tested with an injected fake)
without the package installed or a key present.

Cost discipline is built in: ``max_tokens`` stays tight, and the model name is never
hard-coded — it comes from ``BSQ_MODEL`` (keep it the cheapest capable model for cost).
Prompt caching is deliberately **not** used: the frozen ``system`` prefixes this instrument
sends are only a few dozen tokens — far below the provider's minimum cacheable prefix — so a
``cache_control`` block could never produce a cache read, and padding every request to clear
that floor would bill kilobytes of boilerplate on each call, a net cost increase. If a future
arm grows a genuinely large static shared prefix, put it in a cached ``system`` block, keep
volatile per-utterance content in ``messages`` after the breakpoint, and confirm the win with
``usage.cache_read_input_tokens > 0``. A real SDK client refuses to construct without an
explicit ``BSQ_API_KEY``, so an ambient ``ANTHROPIC_API_KEY`` in the shell can never be spent
by accident. The provider API has **no seed**, so ``seed`` is accepted and ignored. A
truncated response (``stop_reason == "max_tokens"``) returns its **partial** text and bumps
a ``truncations`` counter rather than raising: a truncated policy utterance is still usable
and a truncated extractor body is dropped to ``[]`` by the parser, so a single capped call
must not abort a whole multi-call run. The counter lets a run report how many calls capped.
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
    """An ``LLMClient`` backed by the Anthropic provider API."""

    def __init__(self, cfg: ProviderConfig, *, client: Any = None) -> None:
        if not cfg.model:
            raise ValueError("anthropic provider requires BSQ_MODEL")
        self._cfg = cfg
        self._model = cfg.model
        self._client: Any = client if client is not None else _make_sdk_client(cfg)
        self._truncations = 0

    @property
    def truncations(self) -> int:
        """How many responses were capped at ``max_tokens`` (tolerated, partial returned)."""
        return self._truncations

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        max_tokens: int = 256,
        temperature: float = 0.0,
        stop: list[str] | None = None,
        seed: int | None = None,  # accepted and ignored — the provider API has no seed
    ) -> str:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Plain string, not a cache-control block: the prefix is far below the provider's
            # cache minimum, so caching could never read (see the module docstring).
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if stop:
            request["stop_sequences"] = stop

        response = self._client.messages.create(**request)

        truncated = getattr(response, "stop_reason", None) == "max_tokens"
        if truncated:
            # Tolerated, not fatal: a capped call must never abort a multi-call run. The
            # partial text is returned (a shorter utterance is fine; the extractor's JSON
            # parser drops an unparseable body to []), and the cap is counted for reporting.
            self._truncations += 1
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text":
                text = block.text
                if not isinstance(text, str):
                    raise ValueError(f"expected string text content, got {type(text).__name__}")
                return text
        if truncated:
            return ""  # capped before emitting any text block
        raise ValueError("no text block in provider response")
