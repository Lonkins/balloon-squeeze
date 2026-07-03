"""Operating characteristics of the decision machinery, measured by simulation.

The kill rule's thresholds and the cluster bootstrap were committed without measured
error rates. This module fixes that: a seeded, counts-level Monte-Carlo — calibrated to
the instrument's parameters (claims per game, between-world ICC via a Beta-Binomial
world model) — plants known scenarios and measures what the committed machinery does:

- **verdict error rates** per scenario (false-inert, false-detection, false-artifact,
  underpowered) at the committed thresholds, per cluster count;
- **bootstrap CI coverage**: how often the 95% game-clustered interval contains the
  planted gap;
- **detection power**: probability of a TAG_CONDITIONING verdict as a function of the
  planted gap and the number of games.

Counts-level simulation keeps the study fast enough for CI while staying calibrated to
the engine; engine-level spot checks in the tests validate the world model. Everything
is a pure function of the seed (substream-keyed), so the committed report is
drift-locked like every other artifact.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from bsq.models import PropositionClass
from bsq.probe import GameRecord, ProbeVerdict, evaluate, gap_ci
from bsq.rng import substream

_C = PropositionClass.CHECKABLE
_U = PropositionClass.UNCHECKABLE


@dataclass(frozen=True, slots=True)
class Scenario:
    """A planted world: per-arm true rates for the main channel (placebo stays null)."""

    name: str
    base_rate: float  # A0/A2 rate, both classes; A1 checkable rate
    a1_gap: float  # planted uncheckable-minus-checkable gap under A1
    a2_gap: float = 0.0  # a nonzero value plants a content artifact (silent-arm split)


#: The committed scenario set: a clean null, a threshold-sized effect, a strong effect,
#: and a content artifact the silent arm must catch.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario("null", base_rate=0.4, a1_gap=0.0),
    Scenario("gap-at-threshold", base_rate=0.4, a1_gap=0.10),
    Scenario("gap-strong", base_rate=0.4, a1_gap=0.25),
    Scenario("artifact", base_rate=0.4, a1_gap=0.10, a2_gap=0.10),
)


def _beta_binomial_rate(mean: float, icc: float, rng: random.Random) -> float:
    """Draw a per-game rate with the given mean and intraclass correlation."""
    if icc <= 0.0:
        return mean
    concentration = (1.0 - icc) / icc  # Beta-Binomial: icc = 1 / (a + b + 1)
    alpha = max(mean * concentration, 1e-6)
    beta = max((1.0 - mean) * concentration, 1e-6)
    return rng.betavariate(alpha, beta)


def _simulate_arm(
    *,
    n_games: int,
    c_rate: float,
    u_rate: float,
    claims_per_game: tuple[int, int],
    icc: float,
    rng: random.Random,
) -> list[GameRecord]:
    m_c, m_u = claims_per_game
    records: list[GameRecord] = []
    for _ in range(n_games):
        pc = _beta_binomial_rate(c_rate, icc, rng)
        pu = _beta_binomial_rate(u_rate, icc, rng)
        c_false = sum(1 for _ in range(m_c) if rng.random() < pc)
        u_false = sum(1 for _ in range(m_u) if rng.random() < pu)
        # placebo channel: null at the base rate, thin (1 claim per class)
        pl_c = int(rng.random() < c_rate)
        pl_u = int(rng.random() < c_rate)
        records.append(
            GameRecord(
                main={_C: (c_false, m_c), _U: (u_false, m_u)},
                placebo={_C: (pl_c, 1), _U: (pl_u, 1)},
            )
        )
    return records


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    n_games: int
    n_reps: int
    verdict_rates: Mapping[str, float]
    ci_coverage: float  # fraction of reps whose 95% CI contains the planted A1 gap


def run_oc_study(
    *,
    n_reps: int = 200,
    n_games_grid: Sequence[int] = (10, 14, 30),
    claims_per_game: tuple[int, int] = (5, 4),
    icc: float = 0.15,
    n_draws: int = 400,
    seed: int = 0,
) -> list[ScenarioResult]:
    """Measure verdict error rates and CI coverage for every committed scenario."""
    results: list[ScenarioResult] = []
    for scenario in SCENARIOS:
        for n_games in n_games_grid:
            tallies = {v.value: 0 for v in ProbeVerdict}
            covered = 0
            for rep in range(n_reps):
                rng = substream(seed, "oc", scenario.name, n_games, rep)
                a0 = _simulate_arm(
                    n_games=n_games, c_rate=scenario.base_rate, u_rate=scenario.base_rate,
                    claims_per_game=claims_per_game, icc=icc, rng=rng,
                )
                a1 = _simulate_arm(
                    n_games=n_games, c_rate=scenario.base_rate,
                    u_rate=scenario.base_rate + scenario.a1_gap,
                    claims_per_game=claims_per_game, icc=icc, rng=rng,
                )
                a2 = _simulate_arm(
                    n_games=n_games, c_rate=scenario.base_rate,
                    u_rate=scenario.base_rate + scenario.a2_gap,
                    claims_per_game=claims_per_game, icc=icc, rng=rng,
                )
                report = evaluate(a0, a1, a2, n_draws=n_draws, seed=rep)
                tallies[report.verdict.value] += 1
                ci = gap_ci(a1, n_draws=n_draws, seed=rep)
                if ci.lo <= scenario.a1_gap <= ci.hi:
                    covered += 1
            results.append(
                ScenarioResult(
                    name=scenario.name,
                    n_games=n_games,
                    n_reps=n_reps,
                    verdict_rates={k: v / n_reps for k, v in sorted(tallies.items())},
                    ci_coverage=covered / n_reps,
                )
            )
    return results


def detection_power(
    *,
    gaps: Sequence[float] = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30),
    n_games_grid: Sequence[int] = (10, 14, 30, 60),
    base_rate: float = 0.4,
    claims_per_game: tuple[int, int] = (5, 4),
    icc: float = 0.15,
    n_reps: int = 200,
    n_draws: int = 400,
    seed: int = 0,
) -> list[dict[str, float]]:
    """P(TAG_CONDITIONING verdict) as a function of planted gap and cluster count."""
    points: list[dict[str, float]] = []
    for gap in gaps:
        for n_games in n_games_grid:
            hits = 0
            for rep in range(n_reps):
                rng = substream(seed, "oc-power", f"{gap:.2f}", n_games, rep)
                a0 = _simulate_arm(
                    n_games=n_games, c_rate=base_rate, u_rate=base_rate,
                    claims_per_game=claims_per_game, icc=icc, rng=rng,
                )
                a1 = _simulate_arm(
                    n_games=n_games, c_rate=base_rate, u_rate=base_rate + gap,
                    claims_per_game=claims_per_game, icc=icc, rng=rng,
                )
                a2 = _simulate_arm(
                    n_games=n_games, c_rate=base_rate, u_rate=base_rate,
                    claims_per_game=claims_per_game, icc=icc, rng=rng,
                )
                report = evaluate(a0, a1, a2, n_draws=n_draws, seed=rep)
                if report.verdict is ProbeVerdict.TAG_CONDITIONING:
                    hits += 1
            points.append(
                {"gap": gap, "n_games": float(n_games), "detection_rate": hits / n_reps}
            )
    return points
