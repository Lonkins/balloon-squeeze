"""Deterministic mock policies for the offline measurement path.

The impostor lies at a single, **class-symmetric** baseline rate — identical for
checkable, uncheckable, and placebo propositions. Phase 1 must NOT bake any
class asymmetry into the impostor, or a later phase's estimator would "recover" a
displacement that the mock invented. (Arm-sensitive strategic displacement is added
in Phase 4 for estimator-recovery, behind the verifier arms.)
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from bsq.models import (
    Agent,
    Proposition,
    PropositionClass,
    StructuredClaim,
    Utterance,
)


def _pool(
    ledger: Sequence[Proposition], cls: PropositionClass, *, placebo: bool
) -> list[Proposition]:
    return [p for p in ledger if p.class_ is cls and p.is_placebo_irrelevant is placebo]


@dataclass(frozen=True, slots=True)
class ImpostorPolicy:
    """Asserts one claim per (class x placebo) cell each round, lying at a fixed rate."""

    lie_rate: float = 0.4

    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
    ) -> Utterance:
        cells = [
            _pool(ledger, PropositionClass.CHECKABLE, placebo=False),
            _pool(ledger, PropositionClass.UNCHECKABLE, placebo=False),
            _pool(ledger, PropositionClass.CHECKABLE, placebo=True),
            _pool(ledger, PropositionClass.UNCHECKABLE, placebo=True),
        ]
        targets = [rng.choice(pool) for pool in cells if pool]
        claims = tuple(self._assert(prop, rng) for prop in targets)
        return Utterance(speaker_id=agent.id, round_idx=round_idx, structured=claims)

    def _assert(self, prop: Proposition, rng: random.Random) -> StructuredClaim:
        lied = rng.random() < self.lie_rate
        value = (not prop.truth_value) if lied else prop.truth_value
        return StructuredClaim(proposition_id=prop.id, asserted_value=value)


@dataclass(frozen=True, slots=True)
class HonestPolicy:
    """A panelist who asserts one truthful claim per round."""

    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
    ) -> Utterance:
        prop = rng.choice(list(ledger))
        claim = StructuredClaim(proposition_id=prop.id, asserted_value=prop.truth_value)
        return Utterance(speaker_id=agent.id, round_idx=round_idx, structured=(claim,))
