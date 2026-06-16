"""Extraction-quality measurement + class-stratified Rogan-Gladen correction.

The extractor is imperfect, so the observed per-class false rate is a noisy estimate of
the true rate. This module measures the extractor's per-class **falseness**
sensitivity/specificity on a labeled holdout, deconvolves the rate with the Rogan-Gladen
estimator, and puts a bootstrap CI on the corrected ``(ΔC, ΔU)``. Everything here is a
pure function; the math is verified on a synthetic known-answer fixture.

Two disciplines are load-bearing (per the design review):

- **Class-stratified** sens/spec. Pooling across classes reinjects exactly the
  class-differential bias we are correcting — the silent invalidator.
- The **identifiability guard is a DIAGNOSTIC** here, not a correction. An announced
  verifier can make the impostor's text harder to extract; that per-arm detection-recall
  drop is a *selection* on the denominator, mechanically identical to displacement, and
  Rogan-Gladen (a *misclassification* correction) cannot recover claims that were never
  extracted. So we expose ``detection_recall_gap_by_arm`` and stamp every result with a
  KNOWN_LIMITATION; the live abort fires later on real per-arm text (Phase 7).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from bsq.models import Claim, Proposition, PropositionClass
from bsq.rng import substream

_SINGULAR_EPS = 1e-6
_MAX_RECALL_GAP = 0.10
_MIN_RECALL = 0.85
_MAX_UNIDENTIFIABLE = 0.20
KNOWN_LIMITATION = "arm-extraction-symmetry unverified offline"

_CELL_FIELDS = (
    "gold_false_pred_false",
    "gold_false_pred_true",
    "gold_false_missed",
    "gold_true_pred_true",
    "gold_true_pred_false",
    "gold_true_missed",
    "pred_unmatched",
)


@dataclass(frozen=True, slots=True)
class ConfusionCell:
    """One class's counts over gold-truth x prediction-presence/polarity."""

    gold_false_pred_false: int = 0  # falseness TP
    gold_false_pred_true: int = 0  # polarity flip on a gold-false claim
    gold_false_missed: int = 0  # detection FN on a gold-false claim
    gold_true_pred_true: int = 0  # falseness TN
    gold_true_pred_false: int = 0  # polarity flip on a gold-true claim
    gold_true_missed: int = 0  # detection FN on a gold-true claim
    pred_unmatched: int = 0  # detection FP


@dataclass(frozen=True, slots=True)
class ClassQuality:
    """Derived per-class rates; NaN when a denominator is zero."""

    detection_recall: float  # P(extracted | gold present) — drives the abort rule
    detection_precision: float
    falseness_sens: float  # P(pred-false | gold-false), among detected
    falseness_spec: float  # P(pred-true  | gold-true),  among detected
    cell: ConfusionCell


@dataclass(frozen=True, slots=True)
class ExtractionQuality:
    by_class: Mapping[PropositionClass, ClassQuality]
    known_limitation: str = KNOWN_LIMITATION


@dataclass(frozen=True, slots=True)
class AbortDecision:
    aborted: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class DeltaCI:
    """Corrected within-world contrast for one class; all-NaN if unidentifiable."""

    median: float
    lo: float
    hi: float
    frac_unidentifiable: float
    n_effective: int


def _safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def _key(claim: Claim) -> tuple[str, int, str]:
    # Identity at the (utterance, proposition) level; asserted_value is excluded so a
    # polarity flip MATCHES and is counted as a flip, not as FN + FP.
    return (claim.speaker_id, claim.round_idx, claim.proposition_id)


def _class_quality(counts: Mapping[str, int]) -> ClassQuality:
    cell = ConfusionCell(
        gold_false_pred_false=counts["gold_false_pred_false"],
        gold_false_pred_true=counts["gold_false_pred_true"],
        gold_false_missed=counts["gold_false_missed"],
        gold_true_pred_true=counts["gold_true_pred_true"],
        gold_true_pred_false=counts["gold_true_pred_false"],
        gold_true_missed=counts["gold_true_missed"],
        pred_unmatched=counts["pred_unmatched"],
    )
    matched = (
        cell.gold_false_pred_false
        + cell.gold_false_pred_true
        + cell.gold_true_pred_true
        + cell.gold_true_pred_false
    )
    missed = cell.gold_false_missed + cell.gold_true_missed
    return ClassQuality(
        detection_recall=_safe_div(matched, matched + missed),
        detection_precision=_safe_div(matched, matched + cell.pred_unmatched),
        falseness_sens=_safe_div(
            cell.gold_false_pred_false, cell.gold_false_pred_false + cell.gold_false_pred_true
        ),
        falseness_spec=_safe_div(
            cell.gold_true_pred_true, cell.gold_true_pred_true + cell.gold_true_pred_false
        ),
        cell=cell,
    )


def extraction_quality(
    gold: Sequence[Claim], predicted: Sequence[Claim], ledger: Sequence[Proposition]
) -> ExtractionQuality:
    """Class-stratified confusion + derived rates. The single source of sens/spec/recall."""
    info = {p.id: p for p in ledger}
    gold_map = {_key(c): c for c in gold}
    pred_map = {_key(c): c for c in predicted}
    counts: dict[PropositionClass, dict[str, int]] = {
        cls: dict.fromkeys(_CELL_FIELDS, 0) for cls in PropositionClass
    }
    for key, gold_claim in gold_map.items():
        prop = info[key[2]]
        cls = prop.class_
        gold_false = gold_claim.asserted_value != prop.truth_value
        pred_claim = pred_map.get(key)
        if pred_claim is None:
            counts[cls]["gold_false_missed" if gold_false else "gold_true_missed"] += 1
            continue
        pred_false = pred_claim.asserted_value != prop.truth_value
        if gold_false:
            counts[cls]["gold_false_pred_false" if pred_false else "gold_false_pred_true"] += 1
        else:
            counts[cls]["gold_true_pred_false" if pred_false else "gold_true_pred_true"] += 1
    for key in pred_map.keys() - gold_map.keys():
        counts[info[key[2]].class_]["pred_unmatched"] += 1
    return ExtractionQuality(by_class={cls: _class_quality(c) for cls, c in counts.items()})


def rogan_gladen(observed: float, sens: float, spec: float) -> float:
    """Deconvolve an observed rate given falseness sensitivity/specificity.

    Returns NaN at the singularity (``sens ~ 1 - spec``) and does NOT clamp — the caller
    decides, because clamping would invent a finite value from a singular estimate.
    """
    denom = sens - (1.0 - spec)
    if math.isnan(observed) or math.isnan(sens) or math.isnan(spec) or abs(denom) < _SINGULAR_EPS:
        return math.nan
    return (observed - (1.0 - spec)) / denom


def recall_gap_abort(quality: ExtractionQuality) -> AbortDecision:
    """Abort if cross-class detection recall is too asymmetric or too low."""
    rc = quality.by_class[PropositionClass.CHECKABLE].detection_recall
    ru = quality.by_class[PropositionClass.UNCHECKABLE].detection_recall
    reasons: list[str] = []
    if math.isnan(rc) or math.isnan(ru):
        reasons.append("detection recall undefined for a class")
    else:
        if min(rc, ru) < _MIN_RECALL:
            reasons.append(f"class recall below {_MIN_RECALL} (C={rc:.3f}, U={ru:.3f})")
        if abs(rc - ru) > _MAX_RECALL_GAP:
            reasons.append(f"cross-class recall gap {abs(rc - ru):.3f} exceeds {_MAX_RECALL_GAP}")
    return AbortDecision(aborted=bool(reasons), reason="; ".join(reasons) or None)


def per_arm_extraction_recall(
    gold_by_arm: Mapping[str, Sequence[Claim]],
    predicted_by_arm: Mapping[str, Sequence[Claim]],
    ledger: Sequence[Proposition],
) -> dict[str, ExtractionQuality]:
    """Per-arm extraction quality — never pool, since the announcement can shift recall."""
    return {
        arm: extraction_quality(gold_by_arm[arm], predicted_by_arm[arm], ledger)
        for arm in predicted_by_arm
    }


def detection_recall_gap_by_arm(
    per_arm: Mapping[str, ExtractionQuality], *, baseline: str = "A0", treatment: str = "A1"
) -> dict[PropositionClass, float]:
    """Signed recall[treatment] - recall[baseline] per class — the A1-extraction-confound flag."""
    base, treat = per_arm[baseline], per_arm[treatment]
    return {
        cls: treat.by_class[cls].detection_recall - base.by_class[cls].detection_recall
        for cls in PropositionClass
    }


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return math.nan
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_vals[low]
    frac = pos - low
    return sorted_vals[low] * (1.0 - frac) + sorted_vals[high] * frac


def bootstrap_delta_ci(
    false_labels: Mapping[tuple[str, PropositionClass], Sequence[bool]],
    quality: ExtractionQuality,
    *,
    n_draws: int = 10_000,
    alpha: float = 0.05,
    seed: int,
    eps: float = _SINGULAR_EPS,
    max_unidentifiable: float = _MAX_UNIDENTIFIABLE,
) -> dict[PropositionClass, DeltaCI]:
    """Bootstrap CI on the corrected within-world contrast ``(ΔC, ΔU)``.

    Per draw: resample the per-(arm, class) falseness labels with replacement; draw
    sens/spec per class from Jeffreys Beta on the holdout confusion, **shared across arms
    within the draw** (one extractor measures both arms). NaN draws (singular denominator
    or an empty arm/class) are dropped; their fraction is surfaced.
    """
    classes = (PropositionClass.CHECKABLE, PropositionClass.UNCHECKABLE)
    deltas: dict[PropositionClass, list[float]] = {cls: [] for cls in classes}
    for draw in range(n_draws):
        rng = substream(seed, "bootstrap", draw)
        sens_spec: dict[PropositionClass, tuple[float, float]] = {}
        for cls in classes:
            cell = quality.by_class[cls].cell
            sens = rng.betavariate(
                cell.gold_false_pred_false + 0.5, cell.gold_false_pred_true + 0.5
            )
            spec = rng.betavariate(
                cell.gold_true_pred_true + 0.5, cell.gold_true_pred_false + 0.5
            )
            sens_spec[cls] = (sens, spec)
        for cls in classes:
            sens, spec = sens_spec[cls]
            corrected: dict[str, float] = {}
            ok = abs(sens - (1.0 - spec)) >= eps
            for arm in ("A0", "A1"):
                labels = list(false_labels.get((arm, cls), ()))
                if not ok or not labels:
                    ok = False
                    break
                resampled = rng.choices(labels, k=len(labels))
                observed = sum(resampled) / len(resampled)
                value = rogan_gladen(observed, sens, spec)
                if math.isnan(value):
                    ok = False
                    break
                corrected[arm] = min(1.0, max(0.0, value))
            deltas[cls].append(corrected["A1"] - corrected["A0"] if ok else math.nan)

    result: dict[PropositionClass, DeltaCI] = {}
    for cls in classes:
        surviving = sorted(d for d in deltas[cls] if not math.isnan(d))
        frac_unidentifiable = 1.0 - len(surviving) / n_draws if n_draws else 1.0
        if not surviving or frac_unidentifiable > max_unidentifiable:
            result[cls] = DeltaCI(math.nan, math.nan, math.nan, frac_unidentifiable, len(surviving))
        else:
            result[cls] = DeltaCI(
                median=_percentile(surviving, 0.5),
                lo=_percentile(surviving, alpha / 2.0),
                hi=_percentile(surviving, 1.0 - alpha / 2.0),
                frac_unidentifiable=frac_unidentifiable,
                n_effective=len(surviving),
            )
    return result
