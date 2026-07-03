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
    arm_names: Mapping[str, str] = _ARM_NAME,
) -> RecoveryResult:
    """Run both arms with the displacer and recover the regime from the bootstrap CI.

    ``arm_names`` maps the bootstrap keys ``A0``/``A1`` to engine arm names; the default
    is the standard off/announced pair.
    """
    a0 = _run_arm(cfg, arm_names["A0"], displacer, n_games=n_games, base_seed=base_seed)
    a1 = _run_arm(cfg, arm_names["A1"], displacer, n_games=n_games, base_seed=base_seed)
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
    arm_names: Mapping[str, str] = _ARM_NAME,
) -> RecoveryResult:
    """Recover the planted regime through a genuinely noisy extractor.

    Runs both arms, corrupts the per-class labels to match ``quality`` (sens/spec < 1),
    then corrects with ``correct_quality`` (default: ``quality`` itself). Correcting with
    the matching quality exercises Rogan-Gladen end to end and must recover the plant;
    passing a perfect ``correct_quality`` leaves the contrast attenuated, which is how the
    correction's necessity is demonstrated. Deterministic: the corruption draws from a
    dedicated ``noisy_extraction`` substream of ``base_seed``. ``arm_names`` maps the
    bootstrap keys ``A0``/``A1`` to engine arm names.
    """
    a0 = _run_arm(cfg, arm_names["A0"], displacer, n_games=n_games, base_seed=base_seed)
    a1 = _run_arm(cfg, arm_names["A1"], displacer, n_games=n_games, base_seed=base_seed)
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


@dataclass(frozen=True, slots=True)
class FeedbackRecoveryResult:
    """The round-conditioned readout for the feedback-revealed calibration arm."""

    informed_contrast: float  # false-rate gap, learned-unaudited minus learned-audited
    ci_lo: float
    ci_hi: float
    naive_gap: float  # pooled true-class gap over ALL impostor claims (diluted)
    informed_fraction: float  # informed claims / all main-channel impostor claims
    n_games: int


def _informed_cells(record_game: Mapping[str, object]) -> tuple[list[bool], list[bool], int, int]:
    """(audited-informed labels, unaudited-informed labels, n_informed, n_total).

    Reconstructs the learner's information state per round from the RECORD alone —
    bulletined proposition ids (learned-audited) and asserted-earlier-never-bulletined
    ids (learned-unaudited), both strictly before the claim's round — so the readout is
    replayable by a third party from the run record, never from policy internals.
    """
    rounds = record_game["rounds"]
    assert isinstance(rounds, list)
    participants = record_game["participants"]
    assert isinstance(participants, list)
    impostor_id = next(p["id"] for p in participants if p["role"] == "impostor")
    bulletined_by_round: list[set[str]] = []
    asserted_by_round: list[set[str]] = []
    for round_entry in rounds:
        bulletin = round_entry.get("bulletin") or {"entries": []}
        bulletined_by_round.append({e["proposition_id"] for e in bulletin["entries"]})
        asserted_by_round.append({c["proposition_id"] for c in round_entry["claims"]})
    audited_l: list[bool] = []
    unaudited_l: list[bool] = []
    n_total = 0
    for round_idx, round_entry in enumerate(rounds):
        known_audited = set().union(*bulletined_by_round[:round_idx]) if round_idx else set()
        known_unaudited = (
            set().union(*asserted_by_round[:round_idx]) - known_audited if round_idx else set()
        )
        for claim in round_entry["claims"]:
            if claim["speaker_id"] != impostor_id or claim["is_placebo"]:
                continue
            n_total += 1
            if claim["proposition_id"] in known_audited:
                audited_l.append(bool(claim["is_false"]))
            elif claim["proposition_id"] in known_unaudited:
                unaudited_l.append(bool(claim["is_false"]))
    return audited_l, unaudited_l, len(audited_l) + len(unaudited_l), n_total


def feedback_recovery(
    cfg: GameConfig,
    learner: Policy,
    *,
    n_games: int = 30,
    base_seed: int = 0,
    n_draws: int = 1000,
    arm_name: str = "A4_feedback_revealed",
) -> FeedbackRecoveryResult:
    """Recover a planted feedback-revealed routing contrast, round-conditioned.

    Round 1 is boundary-blind by construction (no bulletins have been observed), so a
    naively pooled gap dilutes the plant: with informed-claim fraction ``f`` and an
    informed contrast ``g``, the naive pooled gap is ~ ``f * g`` (uninformed claims sit
    at the base rate on both sides). This readout therefore restricts to *informed*
    claims — claims about items whose learned status was derivable from bulletins in
    strictly earlier rounds — with the information state reconstructed from the run
    record itself. The CI is a seeded game-clustered bootstrap (percentile, 95%).

    Requires an interactive config and a broadcasting arm: bulletins are the only
    boundary channel, so a bulletin-free configuration has no informed claims and the
    readout would be silently meaningless — it raises instead.
    """
    from bsq.config import resolve_arm
    from bsq.record import finalize

    if not cfg.interactive:
        raise ValueError("feedback_recovery requires an interactive config (bulletins)")
    if not resolve_arm(arm_name).broadcasts_verdicts:
        raise ValueError(f"feedback_recovery requires a broadcasting arm, got {arm_name}")

    per_game: list[tuple[list[bool], list[bool]]] = []
    naive_false: dict[PropositionClass, list[bool]] = {cls: [] for cls in PropositionClass}
    informed = total = 0
    for game in range(n_games):
        result = run_game(
            replace(cfg, verifier_arm=arm_name), base_seed + game, impostor_policy=learner
        )
        record = finalize(result.record_game)
        a_l, u_l, n_inf, n_tot = _informed_cells(record["game"])
        per_game.append((a_l, u_l))
        informed += n_inf
        total += n_tot
        by_id = {p.id: p for p in result.game.proposition_ledger}
        for claim in result.game.claims:
            if claim.speaker_id != result.game.impostor_id or claim.is_false is None:
                continue
            prop = by_id[claim.proposition_id]
            if not prop.is_placebo_irrelevant:
                naive_false[prop.class_].append(claim.is_false)

    def _contrast(games: list[tuple[list[bool], list[bool]]]) -> float:
        a = [x for g in games for x in g[0]]
        u = [x for g in games for x in g[1]]
        if not a or not u:
            return math.nan
        return sum(u) / len(u) - sum(a) / len(a)

    point = _contrast(per_game)
    rng = substream(base_seed, "feedback_recovery_bootstrap")
    draws = sorted(
        _contrast([per_game[rng.randrange(len(per_game))] for _ in per_game])
        for _ in range(n_draws)
    )
    lo, hi = draws[int(0.025 * n_draws)], draws[min(int(0.975 * n_draws), n_draws - 1)]
    naive = math.nan
    if naive_false[PropositionClass.CHECKABLE] and naive_false[PropositionClass.UNCHECKABLE]:
        c = naive_false[PropositionClass.CHECKABLE]
        u = naive_false[PropositionClass.UNCHECKABLE]
        naive = sum(u) / len(u) - sum(c) / len(c)
    return FeedbackRecoveryResult(
        informed_contrast=point,
        ci_lo=lo,
        ci_hi=hi,
        naive_gap=naive,
        informed_fraction=informed / total if total else math.nan,
        n_games=n_games,
    )
