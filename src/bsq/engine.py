"""The deliberation loop.

Single writer of game state and the only thing that emits events. Each round, every
alive agent produces an utterance from its own namespaced RNG sub-stream; the engine
extracts claims and, at the end, scores them against the ledger. Fully deterministic:
the same ``(config, seed)`` reproduces the same game and the same per-class false-mass.

Two deliberation modes:

- **Monologue** (``interactive=False``, the default): each agent speaks against the
  static statement menu with no visibility of other agents — the historical, measured
  configuration, kept byte-identical (guarded by ``tests/test_monologue_golden.py``).
- **Interactive** (``interactive=True``): each turn receives the full prior discussion
  via ``RoundContext.history`` (earlier rounds plus earlier speakers this round), and
  every round closes with a vote by all living agents. A strict plurality eliminates
  (when ``eliminate_between_rounds``); a tie eliminates nobody; eliminating the
  impostor ends the game. Vote RNG draws from a dedicated, arm-independent substream
  so arm-swap replay identity is preserved for arm-insensitive policies.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bsq.agents.mock import HonestPolicy, ImpostorPolicy
from bsq.agents.policy import ABSTAIN, Policy, RoundContext
from bsq.config import resolve_arm
from bsq.events import Event, EventBus
from bsq.extract import extract_claims
from bsq.ledger import author_ledger
from bsq.models import (
    Agent,
    Claim,
    Game,
    GameConfig,
    Persona,
    Proposition,
    Role,
    RoundVotes,
    Utterance,
    VoteCast,
)
from bsq.record import build_game_payload
from bsq.rng import substream
from bsq.scoring import ScoreReport, SeatScore, score_claims
from bsq.verifier import Verification, announcement_for, verify_checkable

#: A claim extractor: (utterance, ledger) -> claims. Default = the mock structured
#: pass-through; the real path injects an LLM extractor (free text -> claims) here.
Extractor = Callable[[Utterance, Sequence[Proposition]], list[Claim]]

_NAMES = ("Ash", "Bree", "Cyrus", "Dale", "Esme", "Faye", "Gus", "Hana")


@dataclass(frozen=True, slots=True)
class GameResult:
    """The output of one game: state, the false-mass report, and the event log."""

    game: Game
    report: ScoreReport
    events: tuple[Event, ...]
    verifications: tuple[Verification, ...] = ()
    utterances: tuple[Utterance, ...] = ()
    rounds_votes: tuple[RoundVotes, ...] = ()
    ended_early: bool = False
    #: The deterministic ``game`` payload of the run record (contract v1) — assembled
    #: for every run, so no code path can produce a game without its record.
    record_game: Mapping[str, Any] = field(default_factory=dict)


def plurality_elimination(votes: Iterable[VoteCast]) -> str | None:
    """The strict plurality target, or ``None`` on a tie or when everyone abstains."""
    counts = Counter(v.target_id for v in votes if v.target_id != ABSTAIN)
    if not counts:
        return None
    ranked = counts.most_common(2)
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def _build_participants(cfg: GameConfig, seed: int) -> list[Agent]:
    impostor_idx = substream(seed, "roles").randrange(cfg.n_agents)
    participants: list[Agent] = []
    for i in range(cfg.n_agents):
        name = _NAMES[i % len(_NAMES)]
        persona = Persona(id=f"persona-{i}", name=name, blurb=f"participant {name}", voice="plain")
        role = Role.IMPOSTOR if i == impostor_idx else Role.PANELIST
        participants.append(Agent(id=f"p{i}", persona=persona, role=role))
    return participants


def run_game(
    cfg: GameConfig,
    seed: int,
    *,
    impostor_policy: Policy | None = None,
    panelist_policy: Policy | None = None,
    extractor: Extractor | None = None,
) -> GameResult:
    """Run a full, deterministic game and score its claims.

    ``impostor_policy`` overrides the impostor seat (default: the arm-insensitive
    ``ImpostorPolicy``). The default keeps every replay-identity guarantee; an
    arm-sensitive policy (the strategic displacer) is injected only for recovery runs.
    """
    bus = EventBus()
    ledger = author_ledger(cfg, seed)
    participants = _build_participants(cfg, seed)
    impostor_id = next(a.id for a in participants if a.role is Role.IMPOSTOR)
    arm = resolve_arm(cfg.verifier_arm)
    game = Game(
        id=f"g-{seed}",
        seed=seed,
        arm=arm,
        participants=participants,
        impostor_id=impostor_id,
        proposition_ledger=ledger,
    )
    bus.emit("game_start", n_agents=len(participants), arm=arm.name, n_propositions=len(ledger))

    announcement = announcement_for(arm)
    round_ctx = RoundContext(arm=arm, announcement=announcement)
    speaker_names = tuple(
        (a.id, a.persona.name if a.persona else a.id) for a in participants
    )
    impostor = impostor_policy if impostor_policy is not None else ImpostorPolicy()
    panelist = panelist_policy if panelist_policy is not None else HonestPolicy()
    extract = extractor if extractor is not None else extract_claims
    policies: dict[str, Policy] = {
        agent.id: (impostor if agent.role is Role.IMPOSTOR else panelist)
        for agent in participants
    }
    bus.emit("verifier_announcement", arm=arm.name, announced=announcement is not None)

    instruction_ctx = RoundContext(
        arm=arm, announcement=announcement, speaker_names=speaker_names
    )
    instructions = {
        agent.id: policies[agent.id].instruction_text(agent, instruction_ctx)
        for agent in participants
    }

    all_claims: list[Claim] = []
    all_utterances: list[Utterance] = []
    claims_per_utterance: dict[int, int] = {}
    verifications: list[Verification] = []
    rounds_votes: list[RoundVotes] = []
    ended_early = False
    for round_idx in range(cfg.rounds):
        bus.emit("round_start", round_idx=round_idx)
        round_claims: list[Claim] = []
        for agent in participants:
            if not agent.alive:
                continue
            rng = substream(seed, "policy", agent.id, round_idx)
            ctx = (
                RoundContext(
                    arm=arm,
                    announcement=announcement,
                    history=tuple(all_utterances),
                    speaker_names=speaker_names,
                )
                if cfg.interactive
                else round_ctx
            )
            utterance = policies[agent.id].act(
                agent=agent, ledger=ledger, round_idx=round_idx, rng=rng, ctx=ctx
            )
            all_utterances.append(utterance)
            bus.emit(
                "utterance",
                speaker=agent.id,
                round_idx=round_idx,
                n_claims=len(utterance.structured),
            )
            extracted = extract(utterance, ledger)
            claims_per_utterance[len(all_utterances) - 1] = len(extracted)
            round_claims.extend(extracted)
        all_claims.extend(round_claims)
        if arm.runs_oracle:
            round_verdicts = verify_checkable(round_claims, ledger)
            verifications.extend(round_verdicts)
            for verdict in round_verdicts:
                bus.emit(
                    "verification",
                    round_idx=verdict.round_idx,
                    proposition=verdict.proposition_id,
                    correct=verdict.correct,
                )
        if cfg.interactive:
            eliminated = _run_vote(
                cfg,
                seed,
                round_idx,
                participants,
                policies,
                all_utterances,
                arm=arm,
                announcement=announcement,
                speaker_names=speaker_names,
                rounds_votes=rounds_votes,
                bus=bus,
            )
            if eliminated == impostor_id:
                ended_early = True
                break

    report = score_claims(all_claims, ledger)
    game.claims = list(report.scored_claims)
    seat = report.by_seat.get(impostor_id)
    bus.emit(
        "claims_scored",
        impostor=impostor_id,
        c_false=seat.checkable.n_false if seat else 0,
        c_asserted=seat.checkable.n_asserted if seat else 0,
        u_false=seat.uncheckable.n_false if seat else 0,
        u_asserted=seat.uncheckable.n_asserted if seat else 0,
    )
    record_game = build_game_payload(
        cfg=cfg,
        seed=seed,
        arm=arm,
        ledger=ledger,
        participants=participants,
        instructions=instructions,
        utterances=all_utterances,
        claims_per_utterance=claims_per_utterance,
        scored_claims=report.scored_claims,
        verifications=verifications,
        rounds_votes=rounds_votes,
        ended_early=ended_early,
        impostor_seat=report.by_seat.get(impostor_id, SeatScore()),
    )
    return GameResult(
        game=game,
        report=report,
        events=tuple(bus.events),
        verifications=tuple(verifications),
        utterances=tuple(all_utterances),
        rounds_votes=tuple(rounds_votes),
        ended_early=ended_early,
        record_game=record_game,
    )


def _run_vote(
    cfg: GameConfig,
    seed: int,
    round_idx: int,
    participants: Sequence[Agent],
    policies: dict[str, Policy],
    all_utterances: Sequence[Utterance],
    *,
    arm: object,
    announcement: str | None,
    speaker_names: tuple[tuple[str, str], ...],
    rounds_votes: list[RoundVotes],
    bus: EventBus,
) -> str | None:
    """Collect one round's votes, apply plurality elimination, record the block."""
    living = [a for a in participants if a.alive]
    ctx = RoundContext(
        arm=resolve_arm(cfg.verifier_arm),
        announcement=announcement,
        history=tuple(all_utterances),
        speaker_names=speaker_names,
    )
    votes: list[VoteCast] = []
    for agent in living:
        vote_rng = substream(seed, "votes", agent.id, round_idx)
        target = policies[agent.id].vote(
            agent=agent, living=living, round_idx=round_idx, rng=vote_rng, ctx=ctx
        )
        votes.append(VoteCast(voter_id=agent.id, target_id=target))
        bus.emit("vote_cast", voter=agent.id, round_idx=round_idx)
    eliminated = plurality_elimination(votes)
    if eliminated is not None and cfg.eliminate_between_rounds:
        for agent in participants:
            if agent.id == eliminated:
                agent.alive = False
        bus.emit("elimination", agent=eliminated, round_idx=round_idx)
    else:
        eliminated = None
    rounds_votes.append(RoundVotes(round_idx=round_idx, votes=tuple(votes), eliminated=eliminated))
    return eliminated
