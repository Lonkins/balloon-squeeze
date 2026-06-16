"""Pilot harness: stat aggregation on mock + full-run sizing (zero spend)."""

from __future__ import annotations

import pytest

from bsq.models import GameConfig, PropositionClass
from bsq.pilot import run_pilot


def test_pilot_aggregates_impostor_stats_on_mock() -> None:
    report = run_pilot(GameConfig(), n_games=30, base_seed=0)
    checkable = report.by_class[PropositionClass.CHECKABLE]
    assert checkable.n_games == 30
    assert checkable.claims_per_game == 4.0  # 1 non-placebo checkable per round x 4 rounds
    assert abs(checkable.observed_false_rate - 0.4) < 0.12  # the mock impostor's lie rate
    assert 0.0 <= checkable.icc < 0.99
    assert checkable.total_claims == 120


def test_pilot_sizes_the_full_run() -> None:
    report = run_pilot(GameConfig(), n_games=30, base_seed=0)
    n = report.required_games(mde=0.2)
    assert isinstance(n, int)
    assert 1 <= n <= 1000


def test_imperfect_extraction_raises_required_games() -> None:
    report = run_pilot(GameConfig(), n_games=30, base_seed=0)
    noisy = report.required_games(mde=0.2, sens=0.8, spec=0.8)
    perfect = report.required_games(mde=0.2)
    assert noisy > perfect


def test_pilot_is_deterministic_on_mock() -> None:
    a = run_pilot(GameConfig(), n_games=10, base_seed=0)
    b = run_pilot(GameConfig(), n_games=10, base_seed=0)
    assert a.by_class[PropositionClass.CHECKABLE] == b.by_class[PropositionClass.CHECKABLE]


def test_zero_games_raises() -> None:
    with pytest.raises(ValueError, match="n_games"):
        run_pilot(GameConfig(), n_games=0)
