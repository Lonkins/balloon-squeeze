"""Analytic sample-size (N) derivation for the corrected per-class contrast.

Per arm and class the Rogan-Gladen-corrected rate has variance
``Var ~= Deff * o(1-o) / (N * c_bar * d^2)`` where ``o`` is the observed positive rate, ``c_bar``
the per-unit label count, ``Deff = 1 + (c_bar - 1) * rho`` the design effect for within-unit
clustering, and ``d = sens - (1 - spec)`` the identifiability denominator. With separate
baseline/treatment denominators ``SE(Δ)^2 = SE_base^2 + SE_treat^2``, and for a two-sided test
Bonferroni-split across the two classes ``N = z_sum^2 * (term_base + term_treat) / MDE^2`` with
``z_sum = z_{1 - alpha/4} + z_power``. N is the max over classes. Pure stdlib (``statistics``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist

from noisyjudge.quality import ClassKey

_STANDARD_NORMAL = NormalDist()


@dataclass(frozen=True, slots=True)
class ArmClassStats:
    """Pilot statistics for one arm x class."""

    observed_rate: float  # o in [0, 1]
    labels_per_unit: float  # c_bar: per-unit labels in this arm x class (> 0)
    icc: float = 0.0  # rho: between-unit correlation, in [0, 1)
    sens: float = 1.0  # judge sensitivity
    spec: float = 1.0  # judge specificity


def _z(p: float) -> float:
    return _STANDARD_NORMAL.inv_cdf(p)


def _arm_term(stats: ArmClassStats) -> float:
    """Per-arm contribution to ``N * SE(Δ)^2``; ``inf`` when unidentifiable."""
    denom = stats.sens - (1.0 - stats.spec)
    if abs(denom) < 1e-9:
        return math.inf
    design_effect = 1.0 + (stats.labels_per_unit - 1.0) * stats.icc
    variance = stats.observed_rate * (1.0 - stats.observed_rate)
    return design_effect * variance / (stats.labels_per_unit * denom * denom)


def se_delta(base: ArmClassStats, treat: ArmClassStats, *, n_units: int) -> float:
    """Standard error of the corrected contrast for one class at ``n_units`` per arm."""
    if n_units <= 0:
        raise ValueError("n_units must be positive")
    return math.sqrt((_arm_term(base) + _arm_term(treat)) / n_units)


def required_units_for_class(
    base: ArmClassStats,
    treat: ArmClassStats,
    *,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """Units per arm to detect ``mde`` on one class's contrast (Bonferroni over 2 classes)."""
    if mde <= 0.0:
        raise ValueError("mde must be positive")
    term = _arm_term(base) + _arm_term(treat)
    if not math.isfinite(term):
        raise ValueError("unidentifiable arm-class (sens ~= 1 - spec); cannot size N")
    z_sum = _z(1.0 - alpha / 4.0) + _z(power)
    return math.ceil(z_sum * z_sum * term / (mde * mde))


def required_units(
    by_class: Mapping[ClassKey, tuple[ArmClassStats, ArmClassStats]],
    *,
    mde: float,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """Units per arm for the joint contrast: the max over classes."""
    if not by_class:
        raise ValueError("by_class must not be empty")
    return max(
        required_units_for_class(base, treat, mde=mde, alpha=alpha, power=power)
        for base, treat in by_class.values()
    )
