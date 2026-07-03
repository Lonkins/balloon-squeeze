"""Interactive mode: history visibility, voting, elimination, determinism.

The contract under test (contracts/cli.md, research D3):
- every turn from round two onward receives the full prior discussion (and earlier
  speakers of the current round) via ``ctx.history``; monologue mode always receives ();
- each interactive round closes with a vote from every living participant; a strict
  plurality eliminates, a tie eliminates nobody, and an eliminated impostor ends the game;
- eliminated agents neither speak nor vote afterwards;
- determinism and arm-swap identity (for arm-insensitive policies) are preserved —
  vote RNG draws from a dedicated, arm-independent substream.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from bsq.agents.policy import ABSTAIN, RoundContext, deterministic_vote
from bsq.canonical import canonical_claim_stream
from bsq.engine import plurality_elimination, run_game
from bsq.models import (
    Agent,
    GameConfig,
    Proposition,
    StructuredClaim,
    Utterance,
    VoteCast,
)


@dataclass
class SpyPolicy:
    """Truthful speaker that records the history length it saw on every turn."""

    seen: list[tuple[int, str, int]] = field(default_factory=list)  # (round, agent, len)

    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> Utterance:
        self.seen.append((round_idx, agent.id, len(ctx.history)))
        prop = ledger[0]
        claim = StructuredClaim(proposition_id=prop.id, asserted_value=prop.truth_value)
        return Utterance(speaker_id=agent.id, round_idx=round_idx, structured=(claim,))

    def instruction_text(self, agent: Agent, ctx: RoundContext) -> str:
        return "Spy policy: records observed history length."

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


@dataclass(frozen=True)
class FixedVotePolicy:
    """Truthful speaker that always votes for one fixed target (if still living)."""

    target: str

    def act(
        self,
        *,
        agent: Agent,
        ledger: Sequence[Proposition],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> Utterance:
        prop = ledger[0]
        claim = StructuredClaim(proposition_id=prop.id, asserted_value=prop.truth_value)
        return Utterance(speaker_id=agent.id, round_idx=round_idx, structured=(claim,))

    def instruction_text(self, agent: Agent, ctx: RoundContext) -> str:
        return "Fixed-vote policy."

    def vote(
        self,
        *,
        agent: Agent,
        living: Sequence[Agent],
        round_idx: int,
        rng: random.Random,
        ctx: RoundContext,
    ) -> str:
        if agent.id == self.target or all(a.id != self.target for a in living):
            return ABSTAIN
        return self.target


def _interactive_cfg(**overrides: object) -> GameConfig:
    base: dict[str, object] = {
        "n_agents": 3,
        "rounds": 3,
        "n_topics": 4,
        "interactive": True,
        "eliminate_between_rounds": False,
    }
    base.update(overrides)
    return GameConfig(**base)  # type: ignore[arg-type]


def test_history_grows_monotonically_across_turns() -> None:
    spy = SpyPolicy()
    run_game(_interactive_cfg(), 7, impostor_policy=spy, panelist_policy=spy)
    lengths = [n for _, _, n in spy.seen]
    assert lengths == list(range(9))  # 3 agents x 3 rounds: every turn sees all prior turns


def test_monologue_mode_history_is_always_empty() -> None:
    spy = SpyPolicy()
    run_game(
        _interactive_cfg(interactive=False), 7, impostor_policy=spy, panelist_policy=spy
    )
    assert [n for _, _, n in spy.seen] == [0] * 9


def test_every_living_participant_votes_each_round() -> None:
    result = run_game(_interactive_cfg(), 7)
    assert len(result.rounds_votes) == 3
    for block in result.rounds_votes:
        assert len(block.votes) == 3  # nobody eliminated (eliminate_between_rounds=False)
        assert {v.voter_id for v in block.votes} == {"p0", "p1", "p2"}


def test_plurality_eliminates_and_tie_does_not() -> None:
    votes = [VoteCast("p0", "p2"), VoteCast("p1", "p2"), VoteCast("p2", "p0")]
    assert plurality_elimination(votes) == "p2"
    tie = [VoteCast("p0", "p1"), VoteCast("p1", "p0"), VoteCast("p2", ABSTAIN)]
    assert plurality_elimination(tie) is None
    assert plurality_elimination([VoteCast("p0", ABSTAIN)]) is None


def test_eliminated_agent_neither_speaks_nor_votes() -> None:
    cfg = _interactive_cfg(n_agents=4, eliminate_between_rounds=True)
    impostor_id = run_game(cfg, 11).game.impostor_id
    target = next(pid for pid in ("p0", "p1", "p2", "p3") if pid != impostor_id)
    fixed = FixedVotePolicy(target=target)
    result = run_game(cfg, 11, impostor_policy=fixed, panelist_policy=fixed)

    assert result.rounds_votes[0].eliminated == target
    assert not result.ended_early  # a panelist fell, the game continues
    later_speakers = {u.speaker_id for u in result.utterances if u.round_idx >= 1}
    assert target not in later_speakers
    for block in result.rounds_votes[1:]:
        assert all(v.voter_id != target for v in block.votes)


def test_impostor_elimination_ends_the_game() -> None:
    cfg = _interactive_cfg(n_agents=4, eliminate_between_rounds=True)
    impostor_id = run_game(cfg, 11).game.impostor_id
    fixed = FixedVotePolicy(target=impostor_id)
    result = run_game(cfg, 11, impostor_policy=fixed, panelist_policy=fixed)

    assert result.ended_early
    assert result.rounds_votes[0].eliminated == impostor_id
    assert len(result.rounds_votes) == 1
    assert {u.round_idx for u in result.utterances} == {0}


def test_interactive_runs_are_deterministic() -> None:
    cfg = _interactive_cfg(n_agents=5, eliminate_between_rounds=True)
    a, b = run_game(cfg, 42), run_game(cfg, 42)
    assert canonical_claim_stream(a.report.scored_claims) == canonical_claim_stream(
        b.report.scored_claims
    )
    assert a.rounds_votes == b.rounds_votes
    assert a.ended_early == b.ended_early


def test_arm_swap_identity_holds_for_arm_insensitive_policies() -> None:
    streams = []
    votes = []
    for arm in ("A0_off", "A1_announced", "A1_implicit", "A2_silent", "A3_placebo"):
        cfg = _interactive_cfg(n_agents=5, eliminate_between_rounds=True, verifier_arm=arm)
        result = run_game(cfg, 42)
        streams.append(canonical_claim_stream(result.report.scored_claims))
        votes.append(result.rounds_votes)
    assert all(s == streams[0] for s in streams)  # claim stream is arm-invariant
    assert all(v == votes[0] for v in votes)  # vote RNG is arm-independent
