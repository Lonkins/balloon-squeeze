"""Judge-error-corrected paired contrast + the joint two-class regime read.

Given per-(arm, class) binary labels from a noisy judge and the judge's per-class quality, this
recovers the Rogan-Gladen-corrected per-class rate **change** between two arms (treatment minus
baseline), with a bootstrap CI, and classifies the joint two-class contrast into one of four
regimes. The judge's sensitivity/specificity are resampled (Jeffreys-Beta on the holdout
confusion) and **shared across arms within a draw** — one judge measures both arms — so the
contrast is not double-penalised for judge uncertainty.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from noisyjudge.quality import ClassKey, ClassQuality

ArmKey = str
_SINGULAR_EPS = 1e-6
_MAX_UNIDENTIFIABLE = 0.20


def rogan_gladen(observed: float, sens: float, spec: float) -> float:
    """Deconvolve an observed positive rate given judge sensitivity/specificity.

    Returns ``NaN`` at the singularity (``sens ~ 1 - spec``) and does NOT clamp — clamping would
    invent a finite value from a singular estimate.
    """
    denom = sens - (1.0 - spec)
    if math.isnan(observed) or math.isnan(sens) or math.isnan(spec) or abs(denom) < _SINGULAR_EPS:
        return math.nan
    return (observed - (1.0 - spec)) / denom


@dataclass(frozen=True, slots=True)
class ContrastCI:
    """Corrected treatment-minus-baseline change for one class; all-``NaN`` if unidentifiable."""

    median: float
    lo: float
    hi: float
    frac_unidentifiable: float
    n_effective: int


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return math.nan
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    low, high = math.floor(pos), math.ceil(pos)
    if low == high:
        return sorted_vals[low]
    frac = pos - low
    return sorted_vals[low] * (1.0 - frac) + sorted_vals[high] * frac


def _rng(seed: int, draw: int) -> random.Random:
    # A distinct, reproducible stream per bootstrap draw (no global state, no wall clock).
    return random.Random(seed * 1_000_003 + draw)


def _joint_draws(
    labels: Mapping[tuple[ArmKey, ClassKey], Sequence[bool]],
    quality: Mapping[ClassKey, ClassQuality],
    *,
    classes: Sequence[ClassKey],
    baseline: ArmKey,
    treatment: ArmKey,
    n_draws: int,
    seed: int,
    eps: float,
) -> list[dict[ClassKey, float]]:
    """Per draw, the corrected paired change ``{class: Δ or NaN}`` — the shared bootstrap core."""
    draws: list[dict[ClassKey, float]] = []
    for d in range(n_draws):
        rng = _rng(seed, d)
        sens_spec: dict[ClassKey, tuple[float, float]] = {}
        for cls in classes:
            c = quality[cls].confusion
            sens = rng.betavariate(c.gold_false_pred_false + 0.5, c.gold_false_pred_true + 0.5)
            spec = rng.betavariate(c.gold_true_pred_true + 0.5, c.gold_true_pred_false + 0.5)
            sens_spec[cls] = (sens, spec)
        per: dict[ClassKey, float] = {}
        for cls in classes:
            sens, spec = sens_spec[cls]
            corrected: dict[ArmKey, float] = {}
            ok = abs(sens - (1.0 - spec)) >= eps
            for arm in (baseline, treatment):
                obs_labels = list(labels.get((arm, cls), ()))
                if not ok or not obs_labels:
                    ok = False
                    break
                resampled = rng.choices(obs_labels, k=len(obs_labels))
                value = rogan_gladen(sum(resampled) / len(resampled), sens, spec)
                if math.isnan(value):
                    ok = False
                    break
                corrected[arm] = min(1.0, max(0.0, value))
            per[cls] = (corrected[treatment] - corrected[baseline]) if ok else math.nan
        draws.append(per)
    return draws


def _summarize(
    values: Sequence[float], *, n_draws: int, alpha: float, max_unidentifiable: float
) -> ContrastCI:
    surviving = sorted(v for v in values if not math.isnan(v))
    frac = 1.0 - len(surviving) / n_draws if n_draws else 1.0
    if not surviving or frac > max_unidentifiable:
        return ContrastCI(math.nan, math.nan, math.nan, frac, len(surviving))
    return ContrastCI(
        median=_percentile(surviving, 0.5),
        lo=_percentile(surviving, alpha / 2.0),
        hi=_percentile(surviving, 1.0 - alpha / 2.0),
        frac_unidentifiable=frac,
        n_effective=len(surviving),
    )


def bootstrap_contrast(
    labels: Mapping[tuple[ArmKey, ClassKey], Sequence[bool]],
    quality: Mapping[ClassKey, ClassQuality],
    *,
    classes: Sequence[ClassKey],
    baseline: ArmKey = "baseline",
    treatment: ArmKey = "treatment",
    n_draws: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
    eps: float = _SINGULAR_EPS,
    max_unidentifiable: float = _MAX_UNIDENTIFIABLE,
) -> dict[ClassKey, ContrastCI]:
    """Bootstrap CI on the corrected treatment-minus-baseline change, marginally per class."""
    draws = _joint_draws(
        labels,
        quality,
        classes=classes,
        baseline=baseline,
        treatment=treatment,
        n_draws=n_draws,
        seed=seed,
        eps=eps,
    )
    return {
        cls: _summarize(
            [d[cls] for d in draws],
            n_draws=n_draws,
            alpha=alpha,
            max_unidentifiable=max_unidentifiable,
        )
        for cls in classes
    }


_QUADRANTS = (
    "primary-neg_secondary-pos",
    "primary-neg_secondary-nonpos",
    "primary-nonneg_secondary-pos",
    "primary-nonneg_secondary-nonpos",
)


@dataclass(frozen=True, slots=True)
class RegimeVerdict:
    """The joint two-class regime, in the canonical "squeeze one channel" framing.

    ``primary`` is the pressured channel (expected to fall); ``secondary`` is the relief channel.
    ``regime``: ``displacement`` (Δprimary<0, Δsecondary>0), ``honesty`` (both fall),
    ``suppression`` (Δprimary<0, Δsecondary≈0), ``null`` (joint CI contains the origin), ``other``,
    or ``unidentifiable``. For a different framing read ``quadrant_probs`` + the marginals directly.
    """

    regime: str
    delta_primary: ContrastCI
    delta_secondary: ContrastCI
    quadrant_probs: Mapping[str, float]
    p_displacement: float
    secondary_upper_bound: float  # (1-alpha) quantile of Δsecondary — calibrated bound for a null
    frac_unidentifiable: float
    n_effective: int


def _classify(p: ContrastCI, s: ContrastCI) -> str:
    if math.isnan(p.median) or math.isnan(s.median):
        return "unidentifiable"
    p_neg, p_zero = p.hi < 0.0, p.lo <= 0.0 <= p.hi
    s_pos, s_neg, s_zero = s.lo > 0.0, s.hi < 0.0, s.lo <= 0.0 <= s.hi
    if p_zero and s_zero:
        return "null"
    if p_neg and s_pos:
        return "displacement"
    if p_neg and s_neg:
        return "honesty"
    if p_neg and s_zero:
        return "suppression"
    return "other"


def joint_regime(
    labels: Mapping[tuple[ArmKey, ClassKey], Sequence[bool]],
    quality: Mapping[ClassKey, ClassQuality],
    *,
    primary: ClassKey,
    secondary: ClassKey,
    baseline: ArmKey = "baseline",
    treatment: ArmKey = "treatment",
    n_draws: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
    eps: float = _SINGULAR_EPS,
    max_unidentifiable: float = _MAX_UNIDENTIFIABLE,
) -> RegimeVerdict:
    """Classify the joint two-class regime from one coherent bootstrap of both channels."""
    classes = (primary, secondary)
    draws = _joint_draws(
        labels,
        quality,
        classes=classes,
        baseline=baseline,
        treatment=treatment,
        n_draws=n_draws,
        seed=seed,
        eps=eps,
    )
    dp = _summarize(
        [d[primary] for d in draws],
        n_draws=n_draws,
        alpha=alpha,
        max_unidentifiable=max_unidentifiable,
    )
    ds = _summarize(
        [d[secondary] for d in draws],
        n_draws=n_draws,
        alpha=alpha,
        max_unidentifiable=max_unidentifiable,
    )
    paired = [
        (d[primary], d[secondary])
        for d in draws
        if not math.isnan(d[primary]) and not math.isnan(d[secondary])
    ]
    frac = 1.0 - len(paired) / n_draws if n_draws else 1.0

    counts = dict.fromkeys(_QUADRANTS, 0)
    for vp, vs in paired:
        if vp < 0.0 and vs > 0.0:
            counts["primary-neg_secondary-pos"] += 1
        elif vp < 0.0:
            counts["primary-neg_secondary-nonpos"] += 1
        elif vs > 0.0:
            counts["primary-nonneg_secondary-pos"] += 1
        else:
            counts["primary-nonneg_secondary-nonpos"] += 1
    total = len(paired)
    quadrant_probs = {k: (counts[k] / total if total else math.nan) for k in _QUADRANTS}
    s_sorted = sorted(vs for _, vs in paired)
    return RegimeVerdict(
        regime=_classify(dp, ds) if frac <= max_unidentifiable else "unidentifiable",
        delta_primary=dp,
        delta_secondary=ds,
        quadrant_probs=quadrant_probs,
        p_displacement=quadrant_probs["primary-neg_secondary-pos"],
        secondary_upper_bound=_percentile(s_sorted, 1.0 - alpha) if s_sorted else math.nan,
        frac_unidentifiable=frac,
        n_effective=total,
    )
