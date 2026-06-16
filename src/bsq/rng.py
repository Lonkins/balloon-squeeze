"""Deterministic, namespaced random sub-streams.

Replaying a world across verifier arms (Phase 2) must not let one arm's extra RNG
draws desync everything downstream. So every consumer draws from its own sub-stream,
keyed by ``(world_seed, *namespace)`` and decoupled from the arm. Same key -> same
stream, always.
"""

from __future__ import annotations

import hashlib
import random


def substream(world_seed: int, *keys: object) -> random.Random:
    """Return a :class:`random.Random` seeded deterministically from the key path."""
    label = "|".join([str(world_seed), *(str(k) for k in keys)])
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))
