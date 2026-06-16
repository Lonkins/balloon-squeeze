"""Variance model + N derivation."""

from __future__ import annotations

import pytest

from bsq.models import PropositionClass
from bsq.power import ArmClassStats, required_games, required_games_for_class, se_delta

# Balanced, perfectly-extracted baseline: o=0.5, 4 claims/game, no clustering, sens=spec=1.
_BASE = ArmClassStats(observed_false_rate=0.5, claims_per_game=4.0)


def test_n_is_in_a_sane_range() -> None:
    n = required_games_for_class(_BASE, _BASE, mde=0.2)
    assert 25 <= n <= 35


def test_n_scales_inversely_with_mde_squared() -> None:
    n_coarse = required_games_for_class(_BASE, _BASE, mde=0.2)
    n_fine = required_games_for_class(_BASE, _BASE, mde=0.1)
    assert n_fine > n_coarse
    assert 3.7 <= n_fine / n_coarse <= 4.3  # halving the MDE quadruples N


def test_imperfect_extraction_raises_n() -> None:
    noisy = ArmClassStats(observed_false_rate=0.5, claims_per_game=4.0, sens=0.8, spec=0.8)
    assert required_games_for_class(noisy, noisy, mde=0.2) > required_games_for_class(
        _BASE, _BASE, mde=0.2
    )


def test_clustering_raises_n() -> None:
    clustered = ArmClassStats(observed_false_rate=0.5, claims_per_game=4.0, icc=0.3)
    assert required_games_for_class(clustered, clustered, mde=0.2) > required_games_for_class(
        _BASE, _BASE, mde=0.2
    )


def test_unidentifiable_raises() -> None:
    singular = ArmClassStats(observed_false_rate=0.5, claims_per_game=4.0, sens=0.5, spec=0.5)
    with pytest.raises(ValueError, match="unidentifiable"):
        required_games_for_class(singular, singular, mde=0.2)


def test_non_positive_mde_raises() -> None:
    with pytest.raises(ValueError, match="mde"):
        required_games_for_class(_BASE, _BASE, mde=0.0)


def test_se_delta_shrinks_with_n() -> None:
    assert se_delta(_BASE, _BASE, n_games=10) > se_delta(_BASE, _BASE, n_games=40)
    ratio = se_delta(_BASE, _BASE, n_games=10) / se_delta(_BASE, _BASE, n_games=40)
    assert abs(ratio - 2.0) < 1e-9  # SE ~ 1/sqrt(N)


def test_required_games_takes_the_worst_class() -> None:
    easy = ArmClassStats(observed_false_rate=0.5, claims_per_game=8.0)  # more claims -> lower N
    hard = ArmClassStats(observed_false_rate=0.5, claims_per_game=2.0)  # fewer claims -> higher N
    by_class = {
        PropositionClass.CHECKABLE: (easy, easy),
        PropositionClass.UNCHECKABLE: (hard, hard),
    }
    assert required_games(by_class, mde=0.2) == required_games_for_class(hard, hard, mde=0.2)


def test_empty_by_class_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        required_games({}, mde=0.2)
