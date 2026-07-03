"""The arm-sensitive strategic-displacer impostor (for estimator recovery).

Under a named-scope verifier (A1) it lies *less* on checkable propositions and *more* on
uncheckable ones — the planted displacement. Two disciplines make the planted contrast
clean and recoverable:

- **Arm-invariant RNG.** The proposition choice and the lie coin are drawn identically
  in both arms; the announcement only shifts the *threshold* the already-drawn coin is
  compared against. So the measured ``(ΔC, ΔU)`` is the strategic shift, never RNG drift.
- **Placebo is untouched.** Placebo-irrelevant claims always lie at the base rate, so the
  placebo control channel shows zero displacement by construction.

Closed-form planted contrasts at base rate ``b``: ``ΔC = -b * s_c``, ``ΔU = +b * s_u``.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from bsq.agents.mock import briefing_truth
from bsq.agents.policy import RoundContext, deterministic_vote
from bsq.models import Agent, Proposition, PropositionClass, StructuredClaim, Utterance


@dataclass(frozen=True, slots=True)
class StrategicDisplacerPolicy:
    """Shifts false-claim mass off checkable onto uncheckable claims under a verifier."""

    lie_rate: float = 0.5  # base rate b (also the A0 rate, class-symmetric)
    s_c: float = 0.0  # checkable reduction under a named-scope verifier
    s_u: float = 0.0  # uncheckable shift under a named-scope verifier

    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> Utterance:
        announced = ctx.arm.announces_scope
        cells = (
            (PropositionClass.CHECKABLE, False),
            (PropositionClass.UNCHECKABLE, False),
            (PropositionClass.CHECKABLE, True),
            (PropositionClass.UNCHECKABLE, True),
        )
        selected: list[tuple[Proposition, PropositionClass, bool]] = []
        for cls, placebo in cells:
            pool = [p for p in ledger if p.class_ is cls and p.is_placebo_irrelevant is placebo]
            if pool:
                selected.append((rng.choice(pool), cls, placebo))
        briefing = briefing_truth(ledger, ctx)
        claims = tuple(
            self._assert(prop, cls, placebo, announced=announced, rng=rng, briefing=briefing)
            for prop, cls, placebo in selected
        )
        return Utterance(speaker_id=agent.id, round_idx=round_idx, structured=claims)

    def _lie_prob(self, cls: PropositionClass, placebo: bool, *, announced: bool) -> float:
        if placebo or not announced:
            return self.lie_rate
        if cls is PropositionClass.CHECKABLE:
            return self.lie_rate * (1.0 - self.s_c)
        return self.lie_rate * (1.0 + self.s_u)

    def _assert(
        self,
        prop: Proposition,
        cls: PropositionClass,
        placebo: bool,
        *,
        announced: bool,
        rng: random.Random,
        briefing: Mapping[str, bool | None],
    ) -> StructuredClaim:
        # Main-channel truth via the impostor briefing (the real channel); placebo items
        # are excluded from the briefing, so the scripted control-channel proxy falls
        # back to engine-side truth (documented in the case study).
        truth = briefing.get(prop.id)
        if truth is None:
            truth = prop.truth_value
        lied = rng.random() < self._lie_prob(cls, placebo, announced=announced)
        value = (not truth) if lied else truth
        return StructuredClaim(proposition_id=prop.id, asserted_value=value)

    def instruction_text(self, agent: Agent, ctx: RoundContext) -> str:
        return (
            "Scripted strategic displacer: lies at a base rate, shifting false-claim "
            "mass checkable->uncheckable under a named-scope verifier "
            f"(b={self.lie_rate}, s_c={self.s_c}, s_u={self.s_u}); placebo untouched."
        )

    def vote(
        self,
        *,
        agent: Agent,
        living: Sequence[Agent],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> str:
        return deterministic_vote(agent, living, rng)
