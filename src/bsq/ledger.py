"""Proposition-ledger authoring.

Each topic yields a matched pair: one checkable and one uncheckable proposition. This
fully crosses class with topic, so the checkable/uncheckable distinction is never
confounded with topic. Truth values are balanced independently within each class to
exactly 50% true (equal marginals, no cross-class leak). A configurable share of topics
is flagged placebo-irrelevant — orthogonal to class — to serve as the zero-displacement
control.

Two properties matter for the real-model extractor (Phase 3): proposition **ids are
opaque** (shuffled, never encoding class or truth) and **surface forms are a pure
function of the id** (so they cannot leak class or truth either). The synthetic surface
forms here are placeholders; an authored natural-language corpus is a separate data
task.
"""

from __future__ import annotations

import hashlib
import random

from bsq.models import GameConfig, Proposition, PropositionClass
from bsq.rng import substream

# Neutral subjects so agents can speak naturally. None encode class or truth.
_SUBJECTS = (
    "the quarterly budget",
    "the warehouse shipment",
    "the rooftop garden",
    "the new hiring plan",
    "the weekend schedule",
    "the parking arrangement",
    "the catering order",
    "the office relocation",
)


def surface_form_for(proposition_id: str) -> str:
    """A class-blind, truth-independent statement form — a pure function of the id.

    Lightly naturalized so agents can talk about it, with the (opaque) id kept as a unique
    anchor the extractor maps back to. Depends only on the id, so it leaks neither class
    nor truth.
    """
    digest = hashlib.sha256(proposition_id.encode("utf-8")).hexdigest()
    subject = _SUBJECTS[int(digest[:8], 16) % len(_SUBJECTS)]
    return f"{subject} (item {proposition_id})"


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

    checkable_truth = _balanced_truth(cfg.n_topics, rng)
    uncheckable_truth = _balanced_truth(cfg.n_topics, rng)

    # Opaque ids, shuffled so an id value tracks neither topic order nor class.
    id_pool = [f"p{i:03d}" for i in range(2 * cfg.n_topics)]
    rng.shuffle(id_pool)
    pool = iter(id_pool)

    ledger: list[Proposition] = []
    for t in range(cfg.n_topics):
        topic_id = f"t{t:03d}"
        is_placebo = t in placebo_topics
        for cls, truth, verifiable in (
            (PropositionClass.CHECKABLE, checkable_truth[t], True),
            (PropositionClass.UNCHECKABLE, uncheckable_truth[t], False),
        ):
            pid = next(pool)
            ledger.append(
                Proposition(
                    id=pid,
                    class_=cls,
                    truth_value=truth,
                    topic_id=topic_id,
                    agent_verifiable=verifiable,
                    is_placebo_irrelevant=is_placebo,
                    surface_form=surface_form_for(pid),
                )
            )
    return ledger
