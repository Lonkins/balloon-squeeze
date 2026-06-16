"""noisyjudge: the measurement recipe, verified on synthetic known answers."""

from __future__ import annotations

import math

import pytest

from noisyjudge import (
    ArmClassStats,
    ClassConfusion,
    ClassQuality,
    ScoredItem,
    bootstrap_contrast,
    class_quality,
    cross_class_recall_gap,
    joint_regime,
    quality_by_class,
    required_units,
    required_units_for_class,
    rogan_gladen,
    se_delta,
)

# --- rogan_gladen ----------------------------------------------------------


def test_rogan_gladen_known_value() -> None:
    assert rogan_gladen(0.6, 0.9, 0.9) == 0.625  # (0.6-0.1)/(0.9-0.1)


def test_rogan_gladen_singularity_is_nan() -> None:
    assert math.isnan(rogan_gladen(0.5, 0.6, 0.4))  # denom 0.6-(1-0.4) = 0
    assert math.isnan(rogan_gladen(0.5, math.nan, 1.0))


def test_rogan_gladen_does_not_clamp() -> None:
    assert rogan_gladen(0.0, 0.9, 0.9) < 0.0


# --- quality ---------------------------------------------------------------


def test_perfect_confusion_gives_unit_rates() -> None:
    q = class_quality(ClassConfusion(gold_false_pred_false=10, gold_true_pred_true=10))
    assert q.detection_recall == 1.0
    assert q.sensitivity == 1.0
    assert q.specificity == 1.0


def test_polarity_flip_lowers_sensitivity_exactly() -> None:
    q = class_quality(ClassConfusion(gold_false_pred_false=3, gold_false_pred_true=1))
    assert q.sensitivity == 0.75
    assert q.detection_recall == 1.0


def test_detection_miss_lowers_recall_exactly() -> None:
    q = class_quality(ClassConfusion(gold_true_pred_true=3, gold_true_missed=1))
    assert q.detection_recall == 0.75


def test_confusion_from_scored_items() -> None:
    items = [
        ScoredItem("C", gold_false=True, pred_false=True),  # judge TP
        ScoredItem("C", gold_false=True, pred_false=False),  # polarity flip
        ScoredItem("C", gold_false=False, pred_false=None),  # detection miss
    ]
    q = quality_by_class(items, unmatched_predictions=["C"])
    cell = q["C"].confusion
    assert cell.gold_false_pred_false == 1
    assert cell.gold_false_pred_true == 1
    assert cell.gold_true_missed == 1
    assert cell.pred_unmatched == 1


def test_cross_class_recall_gap() -> None:
    q = {
        "C": class_quality(ClassConfusion(gold_true_pred_true=4)),  # recall 1.0
        "U": class_quality(ClassConfusion(gold_true_pred_true=3, gold_true_missed=1)),  # 0.75
    }
    assert cross_class_recall_gap(q, "C", "U") == 0.25


# --- bootstrap contrast ----------------------------------------------------


def _labels(p: float, n: int = 40) -> list[bool]:
    k = round(p * n)
    return [True] * k + [False] * (n - k)


def _perfect_q() -> dict[str, ClassQuality]:
    cell = ClassConfusion(gold_false_pred_false=50, gold_true_pred_true=50)
    cq = class_quality(cell)
    return {"P": cq, "S": cq}


def _world(
    p0: float, p1: float, s0: float, s1: float, n: int = 40
) -> dict[tuple[str, str], list[bool]]:
    return {
        ("base", "P"): _labels(p0, n),
        ("treat", "P"): _labels(p1, n),
        ("base", "S"): _labels(s0, n),
        ("treat", "S"): _labels(s1, n),
    }


def test_bootstrap_brackets_observed_contrast() -> None:
    ci = bootstrap_contrast(
        _world(0.4, 0.6, 0.3, 0.5, n=20),
        _perfect_q(),
        classes=("P", "S"),
        baseline="base",
        treatment="treat",
        n_draws=2000,
        seed=1,
    )
    dp = ci["P"]
    assert not math.isnan(dp.median)
    assert dp.lo <= 0.2 <= dp.hi  # observed ΔP ~ +0.2
    assert dp.frac_unidentifiable < 0.05


def test_bootstrap_marks_empty_arm_class_unidentifiable() -> None:
    labels = _world(0.4, 0.4, 0.3, 0.5)
    labels[("base", "P")] = []
    ci = bootstrap_contrast(
        labels,
        _perfect_q(),
        classes=("P", "S"),
        baseline="base",
        treatment="treat",
        n_draws=300,
        seed=3,
    )
    assert math.isnan(ci["P"].median)
    assert not math.isnan(ci["S"].median)


def test_bootstrap_is_deterministic() -> None:
    a = bootstrap_contrast(
        _world(0.4, 0.6, 0.3, 0.5),
        _perfect_q(),
        classes=("P", "S"),
        baseline="base",
        treatment="treat",
        n_draws=500,
        seed=7,
    )
    b = bootstrap_contrast(
        _world(0.4, 0.6, 0.3, 0.5),
        _perfect_q(),
        classes=("P", "S"),
        baseline="base",
        treatment="treat",
        n_draws=500,
        seed=7,
    )
    assert a["P"] == b["P"]


# --- joint regime ----------------------------------------------------------


def _regime(p0: float, p1: float, s0: float, s1: float, seed: int = 1) -> str:
    return joint_regime(
        _world(p0, p1, s0, s1),
        _perfect_q(),
        primary="P",
        secondary="S",
        baseline="base",
        treatment="treat",
        n_draws=3000,
        seed=seed,
    ).regime


def test_joint_regime_displacement() -> None:
    assert _regime(0.7, 0.2, 0.2, 0.7) == "displacement"  # ΔP<0, ΔS>0


def test_joint_regime_honesty() -> None:
    assert _regime(0.7, 0.2, 0.7, 0.2) == "honesty"  # both fall


def test_joint_regime_suppression() -> None:
    assert _regime(0.7, 0.2, 0.4, 0.4) == "suppression"  # ΔP<0, ΔS≈0


def test_joint_regime_null() -> None:
    v = joint_regime(
        _world(0.4, 0.4, 0.4, 0.4),
        _perfect_q(),
        primary="P",
        secondary="S",
        baseline="base",
        treatment="treat",
        n_draws=3000,
        seed=1,
    )
    assert v.regime == "null"
    assert v.secondary_upper_bound >= 0.0  # calibrated bound still reported


def test_joint_regime_unidentifiable_when_class_empty() -> None:
    labels = _world(0.4, 0.4, 0.4, 0.4)
    labels[("base", "P")] = []
    v = joint_regime(
        labels,
        _perfect_q(),
        primary="P",
        secondary="S",
        baseline="base",
        treatment="treat",
        n_draws=300,
        seed=2,
    )
    assert v.regime == "unidentifiable"


def test_joint_regime_quadrant_probs_sum_to_one() -> None:
    v = joint_regime(
        _world(0.7, 0.2, 0.2, 0.7),
        _perfect_q(),
        primary="P",
        secondary="S",
        baseline="base",
        treatment="treat",
        n_draws=2000,
        seed=5,
    )
    assert abs(sum(v.quadrant_probs.values()) - 1.0) < 1e-9


# --- power -----------------------------------------------------------------

_BASE = ArmClassStats(observed_rate=0.5, labels_per_unit=4.0)


def test_required_units_in_a_sane_range() -> None:
    assert 25 <= required_units_for_class(_BASE, _BASE, mde=0.2) <= 35


def test_units_scale_inversely_with_mde_squared() -> None:
    coarse = required_units_for_class(_BASE, _BASE, mde=0.2)
    fine = required_units_for_class(_BASE, _BASE, mde=0.1)
    assert 3.7 <= fine / coarse <= 4.3


def test_imperfect_judge_raises_units() -> None:
    noisy = ArmClassStats(observed_rate=0.5, labels_per_unit=4.0, sens=0.8, spec=0.8)
    assert required_units_for_class(noisy, noisy, mde=0.2) > required_units_for_class(
        _BASE, _BASE, mde=0.2
    )


def test_clustering_raises_units() -> None:
    clustered = ArmClassStats(observed_rate=0.5, labels_per_unit=4.0, icc=0.3)
    assert required_units_for_class(clustered, clustered, mde=0.2) > required_units_for_class(
        _BASE, _BASE, mde=0.2
    )


def test_unidentifiable_raises() -> None:
    singular = ArmClassStats(observed_rate=0.5, labels_per_unit=4.0, sens=0.5, spec=0.5)
    with pytest.raises(ValueError, match="unidentifiable"):
        required_units_for_class(singular, singular, mde=0.2)


def test_required_units_takes_the_worst_class() -> None:
    easy = ArmClassStats(observed_rate=0.5, labels_per_unit=8.0)
    hard = ArmClassStats(observed_rate=0.5, labels_per_unit=2.0)
    by_class = {"C": (easy, easy), "U": (hard, hard)}
    assert required_units(by_class, mde=0.2) == required_units_for_class(hard, hard, mde=0.2)


def test_se_delta_shrinks_with_n() -> None:
    ratio = se_delta(_BASE, _BASE, n_units=10) / se_delta(_BASE, _BASE, n_units=40)
    assert abs(ratio - 2.0) < 1e-9
