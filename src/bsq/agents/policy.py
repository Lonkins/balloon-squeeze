"""The policy seam.

A policy maps (agent, ledger, round, rng, ctx) to an :class:`Utterance`. The
``RoundContext`` carries the arm-conditioned state — the one thing that legitimately
differs across arms — plus, in interactive mode, the discussion so far. Arm-insensitive
policies accept it and ignore it; an arm-sensitive policy (the strategic displacer)
reads it to shift behaviour under an announced verifier.

``history`` is always empty in monologue mode (the measured configuration), so policies
that ignore it are byte-identical to their pre-interactive behaviour. In interactive
mode it holds every prior utterance — earlier rounds plus earlier speakers this round —
at the moment the policy acts.

Policies also expose ``instruction_text`` (the exact instructions the agent operates
under, captured verbatim into run records) and ``vote`` (interactive mode: name one
living participant to accuse, or abstain). The engine supplies ``vote`` with an
arm-independent RNG substream so voting can never desync arm-swap replays.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from bsq.models import Agent, Proposition, Utterance, VerifierArm

#: A vote target that accuses nobody.
ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class RoundContext:
    """Arm-conditioned context for a turn — the single channel through which the arm
    (and, in interactive mode, the prior discussion) may influence behaviour."""

    arm: VerifierArm
    announcement: str | None
    history: tuple[Utterance, ...] = ()  # empty in monologue mode, always
    speaker_names: tuple[tuple[str, str], ...] = ()  # (agent_id, display name) pairs


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

    def instruction_text(self, agent: Agent, ctx: RoundContext) -> str:
        """The instructions this agent operates under, verbatim (for run records)."""
        ...

    def vote(
        self,
        *,
        agent: Agent,
        living: Sequence[Agent],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> str:
        """Interactive mode: return the id of one living *other* agent, or ABSTAIN."""
        ...


def deterministic_vote(agent: Agent, living: Sequence[Agent], rng: random.Random) -> str:
    """Shared scripted-vote rule: accuse a uniformly-drawn living other (or abstain).

    The RNG is the engine-supplied, arm-independent ``votes`` substream, so scripted
    policies vote identically across arms and arm-swap replay identity is preserved.
    """
    others = [a.id for a in living if a.id != agent.id]
    if not others:
        return ABSTAIN
    return rng.choice(others)
