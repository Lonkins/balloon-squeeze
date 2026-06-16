"""Offline, deterministic mock provider.

Produces seeded, reproducible output with no network and no key, so the full
pipeline (and, later, estimator-recovery) can run and be tested offline. The mock
validates plumbing and recovery ONLY — it is never a power calibration.
"""

from __future__ import annotations

import hashlib
import json

from bsq.llm.base import ChatTurn, ProviderConfig

# Small, fixed banter pool. Selection is a deterministic function of (seed, inputs),
# so a given seed reproduces the same line for the same context.
_TALK_POOL: tuple[str, ...] = (
    "I was nowhere near that vote last round, for what it's worth.",
    "Let's be precise about who actually said what before we accuse anyone.",
    "Honestly? I'd rather be wrong out loud than quietly complicit.",
    "Two things can be true: I'm careful, and I'm not the one you want.",
    "If we're counting tells, hesitation isn't one. People hesitate.",
    "I'll stake my standing on it — check the record, not the vibe.",
)


class MockClient:
    """A deterministic, offline ``LLMClient``."""

    def __init__(self, cfg: ProviderConfig) -> None:
        self._cfg = cfg

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
        effective_seed = seed if seed is not None else (self._cfg.seed or 0)
        key = json.dumps(
            {
                "seed": effective_seed,
                "system": system,
                "messages": [(m.role, m.content) for m in messages],
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(_TALK_POOL)
        return _TALK_POOL[index]
