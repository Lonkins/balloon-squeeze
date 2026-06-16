"""Arm-swap replay: within-world identity, determinism, and divergence detection."""

from __future__ import annotations

from bsq.models import STANDARD_ARMS, GameConfig
from bsq.replay import (
    arm_swap_is_identical,
    compare_streams,
    is_deterministic,
    passes_similarity_gate,
    replay_arm,
)

ARMS = list(STANDARD_ARMS)


def test_arm_swap_yields_identical_claim_streams() -> None:
    cfg = GameConfig()
    for seed in range(20):
        assert arm_swap_is_identical(cfg, seed, ARMS)


def test_same_seed_same_arm_is_deterministic() -> None:
    cfg = GameConfig()
    for arm in ARMS:
        assert is_deterministic(cfg, 5, arm)


def test_claim_stream_is_nonempty() -> None:
    assert len(replay_arm(GameConfig(), 1, "A1_announced").claim_stream) > 0


def test_compare_reports_identical_streams() -> None:
    a = (b"x", b"y", b"z")
    comparison = compare_streams(a, a)
    assert comparison.identical
    assert comparison.divergence_index == 3
    assert comparison.prefix_similarity == 1.0


def test_compare_locates_a_synthetic_divergence() -> None:
    a = (b"x", b"y", b"z", b"w")
    b = (b"x", b"y", b"Q", b"w")  # differs at index 2
    comparison = compare_streams(a, b)
    assert not comparison.identical
    assert comparison.divergence_index == 2
    assert comparison.prefix_similarity == 0.5


def test_compare_handles_prefix_truncation() -> None:
    comparison = compare_streams((b"x", b"y", b"z"), (b"x", b"y"))
    assert not comparison.identical
    assert comparison.divergence_index == 2
    assert comparison.length == 3


def test_similarity_gate() -> None:
    identical = compare_streams((b"x",), (b"x",))
    assert passes_similarity_gate(identical, 1.0)
    diverged = compare_streams((b"Q", b"y"), (b"x", b"y"))  # diverges at index 0
    assert diverged.prefix_similarity == 0.0
    assert not passes_similarity_gate(diverged, 0.5)
