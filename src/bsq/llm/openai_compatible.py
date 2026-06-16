"""An OpenAI-compatible chat-completions client (OpenAI, Together, vLLM, LM Studio, …).

Imported lazily by ``make_client`` so the mock path never requires ``httpx``. The wire
format (request shape, seed/temperature passthrough, response parsing, error envelopes)
is fully unit-testable offline via ``httpx.MockTransport`` — which is why this is worth
building now, even though a live call needs a key.
"""

from __future__ import annotations

from typing import Any

import httpx

from bsq.llm.base import ChatTurn, ProviderConfig

_TIMEOUT_SECONDS = 60.0


class OpenAICompatibleClient:
    """Talks to any ``/chat/completions`` endpoint behind the ``LLMClient`` protocol."""

    def __init__(self, cfg: ProviderConfig, *, http_client: httpx.Client | None = None) -> None:
        if not cfg.base_url:
            raise ValueError("openai-compatible provider requires BSQ_BASE_URL")
        if not cfg.model:
            raise ValueError("openai-compatible provider requires BSQ_MODEL")
        self._cfg = cfg
        self._client = http_client or httpx.Client(base_url=cfg.base_url, timeout=_TIMEOUT_SECONDS)

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
        body: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        effective_seed = seed if seed is not None else self._cfg.seed
        if effective_seed is not None:
            body["seed"] = effective_seed
        if stop:
            body["stop"] = stop

        headers = {"Content-Type": "application/json"}
        if self._cfg.api_key:
            headers["Authorization"] = f"Bearer {self._cfg.api_key}"

        response = self._client.post("/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"unexpected response shape from provider: {data!r}") from exc
        if not isinstance(content, str):
            raise ValueError(f"expected string content, got {type(content).__name__}")
        return content
