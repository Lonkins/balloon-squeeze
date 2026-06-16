"""Proposition-ledger authoring.

Each topic yields a matched pair: one checkable and one uncheckable proposition. This
fully crosses class with topic, so the checkable/uncheckable distinction is never
confounded with topic. Truth values are balanced *independently within each class* to
exactly 50% true, which forces equal truth marginals across classes without making one
class's truth predictable from the other's. A configurable share of topics is flagged
placebo-irrelevant — orthogonal to class — to serve as the zero-displacement control.
"""

from __future__ import annotations

import random

from bsq.models import GameConfig, Proposition, PropositionClass
from bsq.rng import substream


def _balanced_truth(n: int, rng: random.Random) -> list[bool]:
    """Exactly ``n // 2`` true values, shuffled, so the class truth marginal is ~50%."""
    truths = [True] * (n // 2) + [False] * (n - n // 2)
    rng.shuffle(truths)
    return truths


def author_ledger(cfg: GameConfig, world_seed: int) -> list[Proposition]:
    """Author a deterministic, topic-matched, truth-balanced proposition ledger."""
    if cfg.n_topics <= 0:
        raise ValueError(f"n_topics must be positive, got {cfg.n_topics}")
    if not 0.0 <= cfg.placebo_fraction <= 1.0:
        raise ValueError(f"placebo_fraction must be in [0, 1], got {cfg.placebo_fraction}")

    rng = substream(world_seed, "ledger")
    n_placebo = round(cfg.n_topics * cfg.placebo_fraction)
    placebo_topics = set(rng.sample(range(cfg.n_topics), n_placebo)) if n_placebo else set()

    # Truth balanced to 50% per class, independently — equal marginals, no cross-class leak.
    checkable_truth = _balanced_truth(cfg.n_topics, rng)
    uncheckable_truth = _balanced_truth(cfg.n_topics, rng)

    ledger: list[Proposition] = []
    for t in range(cfg.n_topics):
        topic_id = f"t{t:03d}"
        is_placebo = t in placebo_topics
        ledger.append(
            Proposition(
                id=f"{topic_id}-c",
                class_=PropositionClass.CHECKABLE,
                truth_value=checkable_truth[t],
                topic_id=topic_id,
                agent_verifiable=True,
                is_placebo_irrelevant=is_placebo,
            )
        )
        ledger.append(
            Proposition(
                id=f"{topic_id}-u",
                class_=PropositionClass.UNCHECKABLE,
                truth_value=uncheckable_truth[t],
                topic_id=topic_id,
                agent_verifiable=False,
                is_placebo_irrelevant=is_placebo,
            )
        )
    return ledger
