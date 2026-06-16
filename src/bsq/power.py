"""Variance model and sample-size (N) derivation for the (delta C, delta U) study.

Given per-(arm, class) pilot statistics, derive the games-per-arm N needed to detect a
target minimum detectable effect (MDE) on the within-world joint contrast at the planned
alpha and power. Pure stdlib (``statistics.NormalDist``); the bootstrap in ``eval.py`` is
the audit oracle for these analytic figures.

Per arm and class, the Rogan-Gladen-corrected rate has variance
``Var(p_hat) ~= Deff * o(1-o) / (N * c_bar * d^2)`` where ``o`` is the observed false
rate, ``c_bar`` the per-game claims in that arm-class, ``Deff = 1 + (c_bar - 1) * rho``
the design effect for within-game clustering, and ``d = sens - (1 - spec)`` the
identifiability denominator. With separate A0/A1 denominators,
``SE(delta)^2 = SE_A0^2 + SE_A1^2``, and for a two-sided test that is Bonferroni-split
across the two classes, ``N = z_sum^2 * (term_A0 + term_A1) / MDE^2`` with
``z_sum = z_{1 - alpha/4} + z_power``. N is the max over classes (the uncheckable class,
with fewer claims, usually dominates).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist

from bsq.models import PropositionClass

_STANDARD_NORMAL = NormalDist()


@dataclass(frozen=True, slots=True)
class ArmClassStats:
    """Pilot statistics for one arm x class."""

    observed_false_rate: float  # o in [0, 1]
    claims_per_game: float  # c_bar: per-game claims in this arm x class (> 0)
    icc: float = 0.0  # rho: between-game (world) correlation, in [0, 1)
    sens: float = 1.0  # falseness sensitivity
    spec: float = 1.0  # falseness specificity


def _z(p: float) -> float:
    return _STANDARD_NORMAL.inv_cdf(p)


def _arm_term(stats: ArmClassStats) -> float:
    """The per-arm contribution to ``N * SE(delta)^2``; ``inf`` when unidentifiable."""
    denom = stats.sens - (1.0 - stats.spec)
    if abs(denom) < 1e-9:
        return math.inf
    design_effect = 1.0 + (stats.claims_per_game - 1.0) * stats.icc
    variance = stats.observed_false_rate * (1.0 - stats.observed_false_rate)
    return design_effect * variance / (stats.claims_per_game * denom * denom)


def se_delta(a0: ArmClassStats, a1: ArmClassStats, *, n_games: int) -> float:
    """Standard error of the corrected within-world contrast for one class at ``n_games``."""
    if n_games <= 0:
        raise ValueError("n_games must be positive")
    return math.sqrt((_arm_term(a0) + _arm_term(a1)) / n_games)


def required_games_for_class(
    a0: ArmClassStats, a1: ArmClassStats, *, mde: float, alpha: float = 0.05, power: float = 0.8
) -> int:
    """Games per arm to detect ``mde`` on one class's contrast (Bonferroni over 2 classes)."""
    if mde <= 0.0:
        raise ValueError("mde must be positive")
    term = _arm_term(a0) + _arm_term(a1)
    if not math.isfinite(term):
        raise ValueError("unidentifiable arm-class (sens ~= 1 - spec); cannot size N")
    z_sum = _z(1.0 - alpha / 4.0) + _z(power)
    return math.ceil(z_sum * z_sum * term / (mde * mde))


def required_games(
    by_class: Mapping[PropositionClass, tuple[ArmClassStats, ArmClassStats]],
    *,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """Games per arm for the joint contrast: the max over classes."""
    if not by_class:
        raise ValueError("by_class must not be empty")
    return max(
        required_games_for_class(a0, a1, mde=mde, alpha=alpha, power=power)
        for a0, a1 in by_class.values()
    )
