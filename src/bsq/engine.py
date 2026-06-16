"""The deliberation loop.

Single writer of game state and the only thing that emits events. Each round, every
alive agent produces an utterance from its own namespaced RNG sub-stream; the engine
extracts claims and, at the end, scores them against the ledger. Fully deterministic:
the same ``(config, seed)`` reproduces the same game and the same per-class false-mass.
"""

from __future__ import annotations

from dataclasses import dataclass

from bsq.agents.mock import HonestPolicy, ImpostorPolicy
from bsq.agents.policy import Policy
from bsq.config import resolve_arm
from bsq.events import Event, EventBus
from bsq.extract import extract_claims
from bsq.ledger import author_ledger
from bsq.models import Agent, Game, GameConfig, Persona, Role
from bsq.rng import substream
from bsq.scoring import ScoreReport, score_claims

_NAMES = ("Ash", "Bree", "Cyrus", "Dale", "Esme", "Faye", "Gus", "Hana")


@dataclass(frozen=True, slots=True)
class GameResult:
    """The output of one game: state, the false-mass report, and the event log."""

    game: Game
    report: ScoreReport
    events: tuple[Event, ...]


def _build_participants(cfg: GameConfig, seed: int) -> list[Agent]:
    impostor_idx = substream(seed, "roles").randrange(cfg.n_agents)
    participants: list[Agent] = []
    for i in range(cfg.n_agents):
        name = _NAMES[i % len(_NAMES)]
        persona = Persona(id=f"persona-{i}", name=name, blurb=f"participant {name}", voice="plain")
        role = Role.IMPOSTOR if i == impostor_idx else Role.PANELIST
        participants.append(Agent(id=f"p{i}", persona=persona, role=role))
    return participants


def _policy_for(agent: Agent) -> Policy:
    return ImpostorPolicy() if agent.role is Role.IMPOSTOR else HonestPolicy()


def run_game(cfg: GameConfig, seed: int) -> GameResult:
    """Run a full, deterministic mock game and score its claims."""
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

    policies = {agent.id: _policy_for(agent) for agent in participants}
    all_claims = []
    for round_idx in range(cfg.rounds):
        bus.emit("round_start", round_idx=round_idx)
        for agent in participants:
            if not agent.alive:
                continue
            rng = substream(seed, "policy", agent.id, round_idx)
            utterance = policies[agent.id].act(
                agent=agent, ledger=ledger, round_idx=round_idx, rng=rng
            )
            bus.emit(
                "utterance",
                speaker=agent.id,
                round_idx=round_idx,
                n_claims=len(utterance.structured),
            )
            all_claims.extend(extract_claims(utterance, ledger))

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
    return GameResult(game=game, report=report, events=tuple(bus.events))
