"""Pilot harness: run games, aggregate the statistics N needs, and size the full run.

A single-arm (``A0_off``) variance pilot. It runs ``n_games``, collects the impostor's
main-channel false labels per class, and reports the per-class statistics the power model
consumes (observed false rate, claims-per-game, and a clustering estimate). Provider-
agnostic: pass mock/structured policies for an offline dry run, or the LLM policy +
extractor for the real provider-backed run. The falseness sensitivity/specificity come from a
separate labeled holdout, not from the pilot games, so they are supplied to
``required_games`` rather than estimated here.

N is sized assuming the A1 variance resembles A0 (same model, similar rates) — the pilot
measures a single arm.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from dataclasses import dataclass, replace

from bsq.agents.policy import Policy
from bsq.engine import Extractor, run_game
from bsq.models import GameConfig, PropositionClass
from bsq.power import ArmClassStats, required_games


@dataclass(frozen=True, slots=True)
class ClassPilot:
    """Per-class pilot statistics for one arm."""

    n_games: int
    total_claims: int
    false_count: int
    observed_false_rate: float  # NaN if no claims in this class
    claims_per_game: float
    icc: float  # between-game (world) correlation estimate, clamped to [0, 0.99]


@dataclass(frozen=True, slots=True)
class PilotReport:
    arm: str
    by_class: Mapping[PropositionClass, ClassPilot]

    def required_games(
        self, *, mde: float, sens: float = 1.0, spec: float = 1.0, alpha: float = 0.05,
        power: float = 0.8,
    ) -> int:
        """Games per arm for the full run, using holdout sens/spec and A1~A0 variance."""
        by_class: dict[PropositionClass, tuple[ArmClassStats, ArmClassStats]] = {}
        for cls, pilot in self.by_class.items():
            stats = ArmClassStats(
                observed_false_rate=pilot.observed_false_rate,
                claims_per_game=pilot.claims_per_game,
                icc=pilot.icc,
                sens=sens,
                spec=spec,
            )
            by_class[cls] = (stats, stats)
        return required_games(by_class, mde=mde, alpha=alpha, power=power)


def _icc(games: list[tuple[int, int]], pbar: float) -> float:
    """Clamped moment estimator of the between-game intraclass correlation."""
    rates = [false / total for false, total in games if total]
    if len(rates) < 2 or pbar <= 0.0 or pbar >= 1.0:
        return 0.0
    between = statistics.pvariance(rates)
    within = statistics.mean(
        (false / total) * (1.0 - false / total) / total for false, total in games if total
    )
    base = pbar * (1.0 - pbar)
    return min(0.99, max(0.0, (between - within) / base))


def run_pilot(
    cfg: GameConfig,
    *,
    n_games: int,
    base_seed: int = 0,
    arm: str = "A0_off",
    impostor_policy: Policy | None = None,
    panelist_policy: Policy | None = None,
    extractor: Extractor | None = None,
) -> PilotReport:
    """Run ``n_games`` on one arm and aggregate the impostor's per-class false statistics."""
    if n_games <= 0:
        raise ValueError("n_games must be positive")
    per_game: dict[PropositionClass, list[tuple[int, int]]] = {cls: [] for cls in PropositionClass}
    for game in range(n_games):
        result = run_game(
            replace(cfg, verifier_arm=arm),
            base_seed + game,
            impostor_policy=impostor_policy,
            panelist_policy=panelist_policy,
            extractor=extractor,
        )
        by_id = {p.id: p for p in result.game.proposition_ledger}
        counts: dict[PropositionClass, list[int]] = {cls: [0, 0] for cls in PropositionClass}
        for claim in result.game.claims:
            if claim.speaker_id != result.game.impostor_id or claim.is_false is None:
                continue
            prop = by_id[claim.proposition_id]
            if prop.is_placebo_irrelevant:
                continue  # main channel only; placebo is the control
            cell = counts[prop.class_]
            cell[1] += 1
            cell[0] += int(claim.is_false)
        for cls in PropositionClass:
            per_game[cls].append((counts[cls][0], counts[cls][1]))

    by_class: dict[PropositionClass, ClassPilot] = {}
    for cls, games in per_game.items():
        total_false = sum(false for false, _ in games)
        total = sum(count for _, count in games)
        rate = total_false / total if total else math.nan
        by_class[cls] = ClassPilot(
            n_games=n_games,
            total_claims=total,
            false_count=total_false,
            observed_false_rate=rate,
            claims_per_game=total / n_games,
            icc=_icc(games, rate) if total else 0.0,
        )
    return PilotReport(arm=arm, by_class=by_class)
