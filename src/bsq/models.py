"""Core domain model.

The engine is the single source of truth: it holds ground truth for every claim —
including the ``uncheckable`` ones — and that ground truth never enters any prompt or
agent memory. See ``02-technical-architecture.md`` for the full design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PropositionClass(StrEnum):
    """Which side of the checkability boundary a proposition sits on."""

    CHECKABLE = "checkable"  # an oracle could confirm it
    UNCHECKABLE = "uncheckable"  # engine-knowable, but the agent cannot verify it


class Role(StrEnum):
    IMPOSTOR = "impostor"  # hidden seat with a deception incentive (engine-only)
    PANELIST = "panelist"


@dataclass(frozen=True, slots=True)
class Persona:
    """Authored content; immutable per game."""

    id: str
    name: str
    blurb: str
    voice: str
    quirks: tuple[str, ...] = ()
    avatar: str | None = None


@dataclass(frozen=True, slots=True)
class Proposition:
    """The unit of measurement. Engine authors it and holds its truth."""

    id: str  # opaque: never encodes class or truth
    class_: PropositionClass
    truth_value: bool
    topic_id: str
    agent_verifiable: bool  # True only for checkable propositions
    is_placebo_irrelevant: bool = False  # control set that must show zero displacement
    surface_form: str = ""  # class-blind, truth-independent; the only content the extractor sees


@dataclass(slots=True)
class Claim:
    """An agent assertion mapped to a proposition; scored later, blind to arm."""

    round_idx: int
    speaker_id: str
    proposition_id: str
    asserted_value: bool
    is_false: bool | None = None
    extractor_conf: float | None = None


@dataclass(frozen=True, slots=True)
class StructuredClaim:
    """A claim already mapped to a proposition (the mock path emits these directly)."""

    proposition_id: str
    asserted_value: bool


@dataclass(frozen=True, slots=True)
class Utterance:
    """What an agent says in a turn.

    The mock path fills ``structured``; a real model fills ``text`` and the Phase-3
    extractor turns it into claims. Both flow through ``extract_claims`` so the engine
    never depends on which path produced the utterance.
    """

    speaker_id: str
    round_idx: int
    structured: tuple[StructuredClaim, ...] = ()
    text: str | None = None


@dataclass(frozen=True, slots=True)
class VerifierArm:
    """An experimental arm — the manipulated variable. Differs only in announcement."""

    name: str
    announces_verifier: bool
    announces_scope: bool  # A1: agent menu tags each statement [AUDITED]/[NOT AUDITED]
    runs_oracle: bool  # whether checkable claims are actually verified in-band
    is_placebo_authority: bool = False  # A3: a moderator with no verification


#: The five core arms. Dose arms reuse ``A1_announced`` and vary the checkability
#: fraction (a game-level dial), so it is not duplicated on the arm.
STANDARD_ARMS: dict[str, VerifierArm] = {
    "A0_off": VerifierArm("A0_off", False, False, False),
    "A1_announced": VerifierArm("A1_announced", True, True, True),
    "A1_implicit": VerifierArm("A1_implicit", True, False, True),
    "A2_silent": VerifierArm("A2_silent", False, False, True),
    "A3_placebo": VerifierArm("A3_placebo", False, False, False, is_placebo_authority=True),
}


@dataclass(slots=True)
class Agent:
    """A participant. ``role`` is engine-only and never sent to any model."""

    id: str
    persona: Persona | None
    role: Role
    alive: bool = True


@dataclass(slots=True)
class GameConfig:
    n_agents: int = 5
    rounds: int = 4
    n_topics: int = 8  # ledger size: each topic yields one checkable + one uncheckable prop
    placebo_fraction: float = 0.25  # share of topics that are placebo-irrelevant controls
    checkability_fraction: float = 0.5  # phi: verifier coverage (used from Phase 2 on)
    verifier_arm: str = "A0_off"
    eliminate_between_rounds: bool = True
    topic_deck: tuple[str, ...] = ()


@dataclass(slots=True)
class Game:
    """A single seeded world. The ``seed`` is the replay key."""

    id: str
    seed: int
    arm: VerifierArm
    participants: list[Agent]
    impostor_id: str  # engine-only ground truth; never in a prompt
    proposition_ledger: list[Proposition] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    outcome: str | None = None
