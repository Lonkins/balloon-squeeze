"""The policy seam.

A policy maps (agent, ledger, round, rng, ctx) to an :class:`Utterance`. The
``RoundContext`` carries the arm-conditioned state — the one thing that legitimately
differs across arms. Arm-insensitive policies accept it and ignore it; an arm-sensitive
policy (the strategic displacer) reads it to shift behaviour under an announced verifier.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from bsq.models import Agent, Proposition, Utterance, VerifierArm


@dataclass(frozen=True, slots=True)
class RoundContext:
    """Arm-conditioned context for a turn — the single channel through which the arm
    may influence behaviour."""

    arm: VerifierArm
    announcement: str | None


class Policy(Protocol):
    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> Utterance:
        """Produce this agent's utterance for the round."""
        ...
