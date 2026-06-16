"""Arm-swap replay harness.

Runs the same seeded world under several verifier arms and checks the within-world
identity contract: the agent claim stream must be byte-identical across arms (because
nothing reacts to the arm yet), and identical across repeated runs of the same
(seed, arm). The divergence detector reports the first differing claim and a prefix
similarity, so that once agents DO react (Phase 4) or run on a real model (Phase 3),
the legitimate post-announcement divergence is located and a similarity gate can
exclude worlds that diverge too early.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from bsq.canonical import canonical_claim_stream
from bsq.engine import run_game
from bsq.models import GameConfig


@dataclass(frozen=True, slots=True)
class Comparison:
    """The result of comparing two claim streams."""

    divergence_index: int  # index of the first differing claim; == length if identical
    length: int  # the longer of the two streams

    @property
    def identical(self) -> bool:
        return self.divergence_index == self.length

    @property
    def prefix_similarity(self) -> float:
        """Fraction of the (longer) stream that matches as an identical prefix."""
        return 1.0 if self.length == 0 else self.divergence_index / self.length


def compare_streams(a: Sequence[bytes], b: Sequence[bytes]) -> Comparison:
    """Locate the first byte-divergence between two ordered claim streams."""
    length = max(len(a), len(b))
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return Comparison(divergence_index=i, length=length)
    if len(a) == len(b):
        return Comparison(divergence_index=length, length=length)
    # one stream is a strict prefix of the other -> they diverge at the shorter length
    return Comparison(divergence_index=min(len(a), len(b)), length=length)


@dataclass(frozen=True, slots=True)
class ReplayRun:
    arm: str
    claim_stream: tuple[bytes, ...]


def replay_arm(cfg: GameConfig, seed: int, arm_name: str) -> ReplayRun:
    """Run the base world under one arm and capture its canonical claim stream."""
    result = run_game(replace(cfg, verifier_arm=arm_name), seed)
    return ReplayRun(arm=arm_name, claim_stream=canonical_claim_stream(result.game.claims))


def replay_across_arms(
    cfg: GameConfig, seed: int, arm_names: Sequence[str]
) -> dict[str, ReplayRun]:
    """Replay the same seeded world under each arm."""
    return {name: replay_arm(cfg, seed, name) for name in arm_names}


def arm_swap_is_identical(cfg: GameConfig, seed: int, arm_names: Sequence[str]) -> bool:
    """True iff every arm yields the identical agent claim stream (the Phase-2 invariant)."""
    runs = replay_across_arms(cfg, seed, arm_names)
    base = runs[arm_names[0]].claim_stream
    return all(
        compare_streams(base, runs[name].claim_stream).identical for name in arm_names[1:]
    )


def is_deterministic(cfg: GameConfig, seed: int, arm_name: str) -> bool:
    """True iff repeating the same (seed, arm) reproduces the identical claim stream."""
    first = replay_arm(cfg, seed, arm_name).claim_stream
    second = replay_arm(cfg, seed, arm_name).claim_stream
    return compare_streams(first, second).identical


def passes_similarity_gate(comparison: Comparison, threshold: float) -> bool:
    """Whether a comparison clears the trajectory-similarity exclusion threshold."""
    return comparison.prefix_similarity >= threshold
