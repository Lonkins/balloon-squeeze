"""Extraction-quality + Rogan-Gladen correction, verified on synthetic known answers."""

from __future__ import annotations

import math

from bsq.eval import (
    KNOWN_LIMITATION,
    ClassQuality,
    ConfusionCell,
    ExtractionQuality,
    RegimeVerdict,
    bootstrap_delta_ci,
    detection_recall_gap_by_arm,
    extraction_quality,
    joint_regime,
    per_arm_extraction_recall,
    recall_gap_abort,
    rogan_gladen,
)
from bsq.models import PropositionClass
from fixtures.synthetic_quality import LEDGER, claim

CHECKABLE = PropositionClass.CHECKABLE
UNCHECKABLE = PropositionClass.UNCHECKABLE


# --- extraction_quality (detection + falseness, class-stratified) -----------

def test_perfect_extraction_gives_unit_rates() -> None:
    gold = [
        claim("imp", 0, "p000", False),  # checkable gold-false
        claim("imp", 1, "p000", True),  # checkable gold-true
        claim("imp", 2, "p002", False),  # uncheckable gold-false
        claim("imp", 3, "p002", True),  # uncheckable gold-true
    ]
    q = extraction_quality(gold, gold, LEDGER)
    for cls in (CHECKABLE, UNCHECKABLE):
        cq = q.by_class[cls]
        assert cq.detection_recall == 1.0
        assert cq.falseness_sens == 1.0
        assert cq.falseness_spec == 1.0


def test_polarity_flip_lowers_sensitivity_exactly() -> None:
    gold = [claim("imp", r, "p000", False) for r in range(4)]  # 4 gold-false checkable
    predicted = [claim("imp", r, "p000", False) for r in range(3)]
    predicted.append(claim("imp", 3, "p000", True))  # one polarity flip
    q = extraction_quality(gold, predicted, LEDGER)
    assert q.by_class[CHECKABLE].falseness_sens == 0.75  # (k-1)/k
    assert q.by_class[CHECKABLE].detection_recall == 1.0  # all detected


def test_detection_miss_lowers_recall_exactly() -> None:
    gold = [claim("imp", r, "p000", True) for r in range(4)]
    predicted = gold[:3]  # one dropped
    q = extraction_quality(gold, predicted, LEDGER)
    assert q.by_class[CHECKABLE].detection_recall == 0.75


def test_empty_class_yields_nan_rates() -> None:
    gold = [claim("imp", 0, "p000", True)]  # checkable only
    q = extraction_quality(gold, gold, LEDGER)
    assert math.isnan(q.by_class[UNCHECKABLE].falseness_sens)
    assert math.isnan(q.by_class[UNCHECKABLE].detection_recall)


# --- rogan_gladen ----------------------------------------------------------

def test_rogan_gladen_known_value() -> None:
    assert rogan_gladen(0.6, 0.9, 0.9) == 0.625  # (0.6-0.1)/(0.9-0.1)


def test_rogan_gladen_singularity_is_nan() -> None:
    assert math.isnan(rogan_gladen(0.5, 0.6, 0.4))  # denom 0.6-(1-0.4) = 0
    assert math.isnan(rogan_gladen(0.5, math.nan, 1.0))


def test_rogan_gladen_does_not_clamp() -> None:
    # observed below the floor (1-spec) -> negative corrected rate, left unclamped
    assert rogan_gladen(0.0, 0.9, 0.9) < 0.0


# --- abort rule ------------------------------------------------------------

def test_abort_fires_on_low_and_asymmetric_recall() -> None:
    gold = [claim("imp", r, "p000", True) for r in range(2)]  # checkable, recall 1.0
    gold += [claim("imp", r, "p002", True) for r in range(5)]  # uncheckable
    predicted = [claim("imp", r, "p000", True) for r in range(2)]
    predicted += [claim("imp", r, "p002", True) for r in range(4)]  # drop 1 -> recall 0.8
    decision = recall_gap_abort(extraction_quality(gold, predicted, LEDGER))
    assert decision.aborted
    assert decision.reason is not None
    assert "recall below" in decision.reason
    assert "gap" in decision.reason


def test_no_abort_when_recall_balanced_and_high() -> None:
    gold = [claim("imp", r, "p000", True) for r in range(4)]
    gold += [claim("imp", r, "p002", True) for r in range(4)]
    decision = recall_gap_abort(extraction_quality(gold, gold, LEDGER))
    assert not decision.aborted


# --- per-arm diagnostic (the A1-extraction-confound flag) ------------------

def test_detection_recall_gap_by_arm_is_signed() -> None:
    gold_by_arm = {arm: [claim("imp", r, "p000", True) for r in range(4)] for arm in ("A0", "A1")}
    predicted_by_arm = {
        "A0": gold_by_arm["A0"],  # recall 1.0
        "A1": gold_by_arm["A1"][:2],  # recall 0.5
    }
    per_arm = per_arm_extraction_recall(gold_by_arm, predicted_by_arm, LEDGER)
    gap = detection_recall_gap_by_arm(per_arm)
    assert gap[CHECKABLE] == -0.5  # A1 - A0
    assert per_arm["A1"].known_limitation == KNOWN_LIMITATION


# --- bootstrap CI ----------------------------------------------------------

def _labels(p: float, n: int = 20) -> list[bool]:
    k = round(p * n)
    return [True] * k + [False] * (n - k)


def _perfect_quality(n: int = 50) -> ExtractionQuality:
    cell = ConfusionCell(gold_false_pred_false=n, gold_true_pred_true=n)
    cq = ClassQuality(1.0, 1.0, 1.0, 1.0, cell)
    return ExtractionQuality(by_class={CHECKABLE: cq, UNCHECKABLE: cq})


def test_bootstrap_ci_brackets_the_observed_contrast() -> None:
    false_labels = {
        ("A0", CHECKABLE): _labels(0.4),
        ("A1", CHECKABLE): _labels(0.6),  # observed ΔC ~ 0.2
        ("A0", UNCHECKABLE): _labels(0.3),
        ("A1", UNCHECKABLE): _labels(0.5),  # observed ΔU ~ 0.2
    }
    ci = bootstrap_delta_ci(false_labels, _perfect_quality(), n_draws=2000, seed=1)
    dc = ci[CHECKABLE]
    assert not math.isnan(dc.median)
    assert dc.lo <= 0.2 <= dc.hi
    assert dc.frac_unidentifiable < 0.05
    assert dc.n_effective > 1900


def test_bootstrap_marks_an_empty_arm_class_unidentifiable() -> None:
    false_labels = {
        ("A0", CHECKABLE): [],  # no A0 checkable assertions -> unidentifiable
        ("A1", CHECKABLE): _labels(0.5),
        ("A0", UNCHECKABLE): _labels(0.3),
        ("A1", UNCHECKABLE): _labels(0.5),
    }
    ci = bootstrap_delta_ci(false_labels, _perfect_quality(), n_draws=300, seed=3)
    assert math.isnan(ci[CHECKABLE].median)
    assert ci[CHECKABLE].frac_unidentifiable == 1.0
    assert not math.isnan(ci[UNCHECKABLE].median)


def test_bootstrap_is_deterministic() -> None:
    false_labels = {
        ("A0", CHECKABLE): _labels(0.4),
        ("A1", CHECKABLE): _labels(0.6),
        ("A0", UNCHECKABLE): _labels(0.3),
        ("A1", UNCHECKABLE): _labels(0.5),
    }
    a = bootstrap_delta_ci(false_labels, _perfect_quality(), n_draws=500, seed=7)
    b = bootstrap_delta_ci(false_labels, _perfect_quality(), n_draws=500, seed=7)
    assert a[CHECKABLE] == b[CHECKABLE]


# --- joint regime classifier (the primary estimand: H1/H2/H3/H4) -----------

def _world(
    c0: float, c1: float, u0: float, u1: float, n: int = 40
) -> dict[tuple[str, PropositionClass], list[bool]]:
    return {
        ("A0", CHECKABLE): _labels(c0, n),
        ("A1", CHECKABLE): _labels(c1, n),
        ("A0", UNCHECKABLE): _labels(u0, n),
        ("A1", UNCHECKABLE): _labels(u1, n),
    }


def test_joint_regime_detects_displacement() -> None:
    # ΔC < 0 (checkable false-rate falls), ΔU > 0 (uncheckable rises)
    v = joint_regime(_world(0.7, 0.2, 0.2, 0.7), _perfect_quality(), n_draws=3000, seed=1)
    assert isinstance(v, RegimeVerdict)
    assert v.regime == "displacement"
    assert v.p_displacement > 0.9
    assert v.delta_c.hi < 0 and v.delta_u.lo > 0


def test_joint_regime_detects_honesty() -> None:
    # both false-rates fall
    v = joint_regime(_world(0.7, 0.2, 0.7, 0.2), _perfect_quality(), n_draws=3000, seed=1)
    assert v.regime == "honesty"
    assert v.delta_c.hi < 0 and v.delta_u.hi < 0


def test_joint_regime_detects_suppression() -> None:
    # checkable falls, uncheckable unchanged
    v = joint_regime(_world(0.7, 0.2, 0.4, 0.4), _perfect_quality(), n_draws=3000, seed=1)
    assert v.regime == "suppression"
    assert v.delta_c.hi < 0
    assert v.delta_u.lo <= 0 <= v.delta_u.hi


def test_joint_regime_detects_null() -> None:
    # no arm effect on either class -> joint CI contains the origin
    v = joint_regime(_world(0.4, 0.4, 0.4, 0.4), _perfect_quality(), n_draws=3000, seed=1)
    assert v.regime == "null"
    assert v.delta_c.lo <= 0 <= v.delta_c.hi
    assert v.delta_u.lo <= 0 <= v.delta_u.hi
    assert v.displacement_upper_bound >= 0.0  # calibrated bound reported for H4


def test_joint_regime_unidentifiable_when_class_empty() -> None:
    labels = _world(0.4, 0.4, 0.4, 0.4)
    labels[("A0", CHECKABLE)] = []  # no A0 checkable assertions
    v = joint_regime(labels, _perfect_quality(), n_draws=300, seed=2)
    assert v.regime == "unidentifiable"


def test_joint_regime_quadrant_probs_sum_to_one() -> None:
    v = joint_regime(_world(0.7, 0.2, 0.2, 0.7), _perfect_quality(), n_draws=2000, seed=5)
    assert abs(sum(v.quadrant_probs.values()) - 1.0) < 1e-9


def test_joint_regime_is_deterministic() -> None:
    a = joint_regime(_world(0.7, 0.2, 0.2, 0.7), _perfect_quality(), n_draws=800, seed=9)
    b = joint_regime(_world(0.7, 0.2, 0.2, 0.7), _perfect_quality(), n_draws=800, seed=9)
    assert a == b
