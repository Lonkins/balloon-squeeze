"""Closed-loop estimator recovery: plant a known regime, confirm the instrument recovers it."""

from __future__ import annotations

from dataclasses import replace

from bsq.agents.displacer import StrategicDisplacerPolicy
from bsq.canonical import canonical_claim_stream
from bsq.engine import run_game
from bsq.models import GameConfig, PropositionClass
from bsq.recovery import RecoveryResult, Regime, recover
from bsq.replay import compare_streams

CHECKABLE = PropositionClass.CHECKABLE
UNCHECKABLE = PropositionClass.UNCHECKABLE

_BASE = 0.5  # base lie rate b


def _recover(s_c: float, s_u: float, *, n_games: int = 40) -> RecoveryResult:
    displacer = StrategicDisplacerPolicy(lie_rate=_BASE, s_c=s_c, s_u=s_u)
    return recover(GameConfig(), displacer, n_games=n_games, base_seed=0, n_draws=800)


# --- one test per planted regime (planted ΔC = -b*s_c, ΔU = +b*s_u) ---------

def test_recovers_displacement() -> None:
    result = _recover(s_c=0.5, s_u=0.5)  # planted (-0.25, +0.25)
    assert result.regime is Regime.DISPLACEMENT
    assert result.deltas[CHECKABLE].hi < 0.0
    assert result.deltas[UNCHECKABLE].lo > 0.0
    assert abs(result.deltas[CHECKABLE].median - (-0.25)) < 0.1
    assert abs(result.deltas[UNCHECKABLE].median - 0.25) < 0.1
    assert result.deltas[CHECKABLE].frac_unidentifiable < 0.02


def test_recovers_suppression() -> None:
    result = _recover(s_c=0.5, s_u=0.0)  # planted (-0.25, 0)
    assert result.regime is Regime.SUPPRESSION
    assert result.deltas[CHECKABLE].hi < 0.0
    assert result.deltas[UNCHECKABLE].lo <= 0.0 <= result.deltas[UNCHECKABLE].hi


def test_recovers_honesty() -> None:
    result = _recover(s_c=0.5, s_u=-0.5)  # planted (-0.25, -0.25)
    assert result.regime is Regime.HONESTY
    assert result.deltas[CHECKABLE].hi < 0.0
    assert result.deltas[UNCHECKABLE].hi < 0.0


def test_recovers_null() -> None:
    result = _recover(s_c=0.0, s_u=0.0)  # planted (0, 0)
    assert result.regime is Regime.NULL
    assert result.deltas[CHECKABLE].lo <= 0.0 <= result.deltas[CHECKABLE].hi
    assert result.deltas[UNCHECKABLE].lo <= 0.0 <= result.deltas[UNCHECKABLE].hi


# --- the displacer exercises the Phase-2 divergence detector (first non-synthetic use) ---

def test_displacer_makes_the_replay_diverge() -> None:
    displacer = StrategicDisplacerPolicy(lie_rate=_BASE, s_c=1.0, s_u=1.0)
    cfg = GameConfig(rounds=6)  # more checkable claims -> a reroute is near-certain
    a0 = run_game(replace(cfg, verifier_arm="A0_off"), 0, impostor_policy=displacer)
    a1 = run_game(replace(cfg, verifier_arm="A1_announced"), 0, impostor_policy=displacer)
    comparison = compare_streams(
        canonical_claim_stream(a0.game.claims), canonical_claim_stream(a1.game.claims)
    )
    assert not comparison.identical
    assert comparison.divergence_index < comparison.length
    assert comparison.prefix_similarity < 1.0


# --- the placebo channel must stay undisplaced (the control) ----------------

def test_displacer_leaves_placebo_channel_undisplaced() -> None:
    displacer = StrategicDisplacerPolicy(lie_rate=_BASE, s_c=0.8, s_u=0.8)
    cfg = GameConfig()

    def placebo_false_rate(arm: str) -> float:
        n_false = total = 0
        for game in range(30):
            result = run_game(replace(cfg, verifier_arm=arm), game, impostor_policy=displacer)
            by_id = {p.id: p for p in result.game.proposition_ledger}
            for claim in result.game.claims:
                if claim.speaker_id != result.game.impostor_id or claim.is_false is None:
                    continue
                if by_id[claim.proposition_id].is_placebo_irrelevant:
                    total += 1
                    n_false += int(claim.is_false)
        return n_false / total

    assert abs(placebo_false_rate("A0_off") - placebo_false_rate("A1_announced")) < 0.1
