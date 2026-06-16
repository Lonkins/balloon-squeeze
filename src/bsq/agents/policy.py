"""The policy seam.

A policy maps (agent, ledger, round, rng) to an :class:`Utterance`. The mock policies
emit structured claims directly; a future LLM-backed policy would call the model to
produce ``text`` and let the Phase-3 extractor turn it into claims. Either way the
engine only ever sees an utterance.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Protocol

from bsq.models import Agent, Proposition, Utterance


class Policy(Protocol):
    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
    ) -> Utterance:
        """Produce this agent's utterance for the round."""
        ...
