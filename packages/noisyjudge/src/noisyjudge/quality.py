"""Per-class judge quality: detection recall + falseness sensitivity/specificity.

A "judge" is any noisy binary labeller (an LLM-as-judge, a classifier) that, for each item,
may (a) miss it entirely and (b) get its polarity wrong. Stratifying these error rates BY
CLASS is load-bearing: pooling across classes reinjects exactly the class-differential bias a
class-stratified correction removes. All rates are ``NaN`` when their denominator is zero;
the caller decides what to do (this library never invents a value).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

ClassKey = str


@dataclass(frozen=True, slots=True)
class ClassConfusion:
    """One class's counts over gold-truth x prediction-presence/polarity.

    "false" = the labelled-as-false event we estimate the rate of; "true" = its complement.
    """

    gold_false_pred_false: int = 0  # judge true-positive (gold false, called false)
    gold_false_pred_true: int = 0  # polarity flip on a gold-false item
    gold_false_missed: int = 0  # detection miss on a gold-false item
    gold_true_pred_true: int = 0  # judge true-negative
    gold_true_pred_false: int = 0  # polarity flip on a gold-true item
    gold_true_missed: int = 0  # detection miss on a gold-true item
    pred_unmatched: int = 0  # detection false-positive (predicted, no gold)


@dataclass(frozen=True, slots=True)
class ClassQuality:
    """Derived per-class rates; ``NaN`` when a denominator is zero."""

    detection_recall: float  # P(detected | gold present)
    detection_precision: float  # P(gold present | detected)
    sensitivity: float  # P(called-false | gold-false), among detected
    specificity: float  # P(called-true  | gold-true),  among detected
    confusion: ClassConfusion


@dataclass(frozen=True, slots=True)
class ScoredItem:
    """One gold item the judge was scored against."""

    cls: ClassKey
    gold_false: bool
    pred_false: bool | None  # None = the judge missed it (no prediction)


def _safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def class_quality(c: ClassConfusion) -> ClassQuality:
    """Detection recall/precision and falseness sensitivity/specificity for one class."""
    matched = (
        c.gold_false_pred_false
        + c.gold_false_pred_true
        + c.gold_true_pred_true
        + c.gold_true_pred_false
    )
    missed = c.gold_false_missed + c.gold_true_missed
    return ClassQuality(
        detection_recall=_safe_div(matched, matched + missed),
        detection_precision=_safe_div(matched, matched + c.pred_unmatched),
        sensitivity=_safe_div(
            c.gold_false_pred_false, c.gold_false_pred_false + c.gold_false_pred_true
        ),
        specificity=_safe_div(
            c.gold_true_pred_true, c.gold_true_pred_true + c.gold_true_pred_false
        ),
        confusion=c,
    )


def confusion_by_class(
    items: Iterable[ScoredItem], unmatched_predictions: Iterable[ClassKey] = ()
) -> dict[ClassKey, ClassConfusion]:
    """Build per-class confusion from scored gold items + judge predictions with no gold match."""
    cells: dict[ClassKey, dict[str, int]] = {}

    def bump(cls: ClassKey, field: str) -> None:
        cells.setdefault(cls, {}).__setitem__(field, cells.setdefault(cls, {}).get(field, 0) + 1)

    for item in items:
        if item.pred_false is None:
            bump(item.cls, "gold_false_missed" if item.gold_false else "gold_true_missed")
        elif item.gold_false:
            bump(item.cls, "gold_false_pred_false" if item.pred_false else "gold_false_pred_true")
        else:
            bump(item.cls, "gold_true_pred_false" if item.pred_false else "gold_true_pred_true")
    for cls in unmatched_predictions:
        bump(cls, "pred_unmatched")
    return {cls: ClassConfusion(**fields) for cls, fields in cells.items()}


def quality_by_class(
    items: Iterable[ScoredItem], unmatched_predictions: Iterable[ClassKey] = ()
) -> dict[ClassKey, ClassQuality]:
    """Convenience: scored items -> per-class :class:`ClassQuality`."""
    return {
        cls: class_quality(c) for cls, c in confusion_by_class(items, unmatched_predictions).items()
    }


def cross_class_recall_gap(
    quality: dict[ClassKey, ClassQuality], a: ClassKey, b: ClassKey
) -> float:
    """``|recall(a) - recall(b)|`` — the class-differential detection asymmetry (an identifiability
    diagnostic). A large gap means class-correlated *selection* on the denominator, which a
    misclassification correction cannot repair; treat it as an abort signal, not something to
    correct away. ``NaN`` if either recall is undefined."""
    ra, rb = quality[a].detection_recall, quality[b].detection_recall
    if math.isnan(ra) or math.isnan(rb):
        return math.nan
    return abs(ra - rb)
