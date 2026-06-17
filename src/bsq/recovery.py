"""Closed-loop estimator recovery.

Plant a known displacement with the strategic displacer, run the full instrument
(engine -> score -> bootstrap), and confirm the recovered ``(ΔC, ΔU)`` matches the plant.

Two closed loops:

- :func:`recover` runs under **perfect extraction**, so the supplied ExtractionQuality is
  perfect and Rogan-Gladen is the identity — this validates the *plumbing and the plant*
  end to end.
- :func:`recover_noisy` injects extraction noise that matches a **sub-perfect** quality
  (sensitivity/specificity below 1), then corrects with that same quality — so the
  Rogan-Gladen correction is actually exercised end to end and must recover the plant from
  the corrupted labels. Without the correction the recovered contrast would be attenuated.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum

from bsq.agents.policy import Policy
from bsq.engine import run_game
from bsq.eval import (
    ClassQuality,
    ConfusionCell,
    DeltaCI,
    ExtractionQuality,
    bootstrap_delta_ci,
)
from bsq.models import GameConfig, PropositionClass
from bsq.rng import substream

# Bootstrap arm keys -> the engine arm names they are produced from.
_ARM_NAME = {"A0": "A0_off", "A1": "A1_announced"}


class Regime(StrEnum):
    DISPLACEMENT = "displacement"
    SUPPRESSION = "suppression"
    HONESTY = "honesty"
    NULL = "null"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    deltas: Mapping[PropositionClass, DeltaCI]
    regime: Regime


def _perfect_quality(n: int = 200) -> ExtractionQuality:
    """A near-perfect extractor: sens/spec ~ 1, so Rogan-Gladen is ~identity."""
    cell = ConfusionCell(gold_false_pred_false=n, gold_true_pred_true=n)
    quality = ClassQuality(
        detection_recall=1.0,
        detection_precision=1.0,
        falseness_sens=1.0,
        falseness_spec=1.0,
        cell=cell,
    )
    return ExtractionQuality(by_class={cls: quality for cls in PropositionClass})


def _run_arm(
    cfg: GameConfig, arm_name: str, displacer: Policy, *, n_games: int, base_seed: int
) -> dict[PropositionClass, list[bool]]:
    """Run N games on one arm; collect the impostor's main-channel falseness labels."""
    labels: dict[PropositionClass, list[bool]] = {cls: [] for cls in PropositionClass}
    for game in range(n_games):
        result = run_game(
            replace(cfg, verifier_arm=arm_name), base_seed + game, impostor_policy=displacer
        )
        by_id = {p.id: p for p in result.game.proposition_ledger}
        for claim in result.game.claims:
            if claim.speaker_id != result.game.impostor_id or claim.is_false is None:
                continue
            prop = by_id[claim.proposition_id]
            if prop.is_placebo_irrelevant:
                continue  # main channel only; placebo is the zero-displacement control
            labels[prop.class_].append(claim.is_false)
    return labels


def _sign(ci: DeltaCI) -> str:
    if math.isnan(ci.median):
        return "nan"
    if ci.hi < 0.0:
        return "neg"
    if ci.lo > 0.0:
        return "pos"
    return "null"


def _classify(deltas: Mapping[PropositionClass, DeltaCI]) -> Regime:
    c = _sign(deltas[PropositionClass.CHECKABLE])
    u = _sign(deltas[PropositionClass.UNCHECKABLE])
    if c == "neg" and u == "pos":
        return Regime.DISPLACEMENT
    if c == "neg" and u == "neg":
        return Regime.HONESTY
    if c == "neg" and u == "null":
        return Regime.SUPPRESSION
    if c == "null" and u == "null":
        return Regime.NULL
    return Regime.UNCLASSIFIED


def recover(
    cfg: GameConfig,
    displacer: Policy,
    *,
    n_games: int = 30,
    base_seed: int = 0,
    alpha: float = 0.05,
    n_draws: int = 1000,
) -> RecoveryResult:
    """Run both arms with the displacer and recover the regime from the bootstrap CI."""
    a0 = _run_arm(cfg, _ARM_NAME["A0"], displacer, n_games=n_games, base_seed=base_seed)
    a1 = _run_arm(cfg, _ARM_NAME["A1"], displacer, n_games=n_games, base_seed=base_seed)
    false_labels: dict[tuple[str, PropositionClass], list[bool]] = {}
    for cls in PropositionClass:
        false_labels[("A0", cls)] = a0[cls]
        false_labels[("A1", cls)] = a1[cls]
    deltas = bootstrap_delta_ci(
        false_labels, _perfect_quality(), n_draws=n_draws, alpha=alpha, seed=base_seed
    )
    return RecoveryResult(deltas=deltas, regime=_classify(deltas))


def _corrupt(labels: list[bool], sens: float, spec: float, rng: random.Random) -> list[bool]:
    """Inject extraction noise: a gold-false label survives as false w.p. ``sens``; a
    gold-true label is flipped to false w.p. ``1 - spec``. Exactly one draw per label."""
    return [(rng.random() < sens) if gold else (rng.random() >= spec) for gold in labels]


def recover_noisy(
    cfg: GameConfig,
    displacer: Policy,
    quality: ExtractionQuality,
    *,
    correct_quality: ExtractionQuality | None = None,
    n_games: int = 30,
    base_seed: int = 0,
    alpha: float = 0.05,
    n_draws: int = 1000,
) -> RecoveryResult:
    """Recover the planted regime through a genuinely noisy extractor.

    Runs both arms, corrupts the per-class labels to match ``quality`` (sens/spec < 1),
    then corrects with ``correct_quality`` (default: ``quality`` itself). Correcting with
    the matching quality exercises Rogan-Gladen end to end and must recover the plant;
    passing a perfect ``correct_quality`` leaves the contrast attenuated, which is how the
    correction's necessity is demonstrated. Deterministic: the corruption draws from a
    dedicated ``noisy_extraction`` substream of ``base_seed``.
    """
    a0 = _run_arm(cfg, _ARM_NAME["A0"], displacer, n_games=n_games, base_seed=base_seed)
    a1 = _run_arm(cfg, _ARM_NAME["A1"], displacer, n_games=n_games, base_seed=base_seed)
    rng = substream(base_seed, "noisy_extraction")
    false_labels: dict[tuple[str, PropositionClass], list[bool]] = {}
    for tag, arm_labels in (("A0", a0), ("A1", a1)):
        for cls in PropositionClass:
            q = quality.by_class[cls]
            false_labels[(tag, cls)] = _corrupt(
                arm_labels[cls], q.falseness_sens, q.falseness_spec, rng
            )
    deltas = bootstrap_delta_ci(
        false_labels, correct_quality or quality, n_draws=n_draws, alpha=alpha, seed=base_seed
    )
    return RecoveryResult(deltas=deltas, regime=_classify(deltas))
