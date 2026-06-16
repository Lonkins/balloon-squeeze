"""End-to-end mock game: deterministic, scored, and class-symmetric at baseline."""

from __future__ import annotations

import math
from statistics import mean

from bsq.engine import run_game
from bsq.models import GameConfig, Role


def test_game_is_deterministic() -> None:
    cfg = GameConfig()
    a = run_game(cfg, 123)
    b = run_game(cfg, 123)
    assert a.report.scored_claims == b.report.scored_claims
    assert a.report.by_seat[a.game.impostor_id] == b.report.by_seat[b.game.impostor_id]


def test_impostor_speaks_in_both_classes_and_panelists_are_honest() -> None:
    res = run_game(GameConfig(), 7)
    impostor = res.report.by_seat[res.game.impostor_id]
    assert impostor.checkable.n_asserted > 0
    assert impostor.uncheckable.n_asserted > 0
    for agent in res.game.participants:
        if agent.role is Role.PANELIST and agent.id in res.report.by_seat:
            seat = res.report.by_seat[agent.id]
            assert seat.checkable.n_false == 0
            assert seat.uncheckable.n_false == 0


def test_emits_lifecycle_events() -> None:
    kinds = [e.kind for e in run_game(GameConfig(), 1).events]
    assert "game_start" in kinds
    assert "claims_scored" in kinds


def test_baseline_is_class_symmetric() -> None:
    # Guardrail: on A0_off the mock impostor must lie equally across classes, or a later
    # phase would "recover" a displacement the mock invented. Fail the build if it leaks.
    c_rates: list[float] = []
    u_rates: list[float] = []
    for seed in range(400):
        res = run_game(GameConfig(), seed)
        impostor = res.report.by_seat[res.game.impostor_id]
        if not math.isnan(impostor.c):
            c_rates.append(impostor.c)
        if not math.isnan(impostor.u):
            u_rates.append(impostor.u)
    assert abs(mean(c_rates) - mean(u_rates)) < 0.05
