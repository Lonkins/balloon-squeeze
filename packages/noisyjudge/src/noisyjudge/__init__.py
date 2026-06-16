"""noisyjudge — class-stratified, judge-error-corrected contrast estimation (pure stdlib).

Measure how a binary rate changes between two arms when the labels come from a NOISY judge
(an LLM-as-judge or any imperfect classifier), stratified by a 2-class factor:

  1. ``quality_by_class`` — per-class detection recall + judge sensitivity/specificity from a
     labelled holdout (class-stratified; pooling reinjects the bias you are correcting).
  2. ``rogan_gladen`` — deconvolve an observed rate given that sensitivity/specificity.
  3. ``bootstrap_contrast`` / ``joint_regime`` — the corrected treatment-minus-baseline change
     per class with a bootstrap CI, and the joint two-class regime (one coherent resample;
     sens/spec shared across arms within a draw).
  4. ``required_units`` — analytic N per arm for a target minimum detectable effect.
  5. ``cross_class_recall_gap`` — the identifiability diagnostic (class-differential selection a
     misclassification correction cannot repair).

No third-party dependencies. See README.md for the recipe and a worked example.
"""

from __future__ import annotations

from noisyjudge.contrast import (
    ContrastCI,
    RegimeVerdict,
    bootstrap_contrast,
    joint_regime,
    rogan_gladen,
)
from noisyjudge.power import ArmClassStats, required_units, required_units_for_class, se_delta
from noisyjudge.quality import (
    ClassConfusion,
    ClassQuality,
    ScoredItem,
    class_quality,
    confusion_by_class,
    cross_class_recall_gap,
    quality_by_class,
)

__all__ = [
    "ArmClassStats",
    "ClassConfusion",
    "ClassQuality",
    "ContrastCI",
    "RegimeVerdict",
    "ScoredItem",
    "bootstrap_contrast",
    "class_quality",
    "confusion_by_class",
    "cross_class_recall_gap",
    "joint_regime",
    "quality_by_class",
    "required_units",
    "required_units_for_class",
    "rogan_gladen",
    "se_delta",
]
__version__ = "0.1.0"
