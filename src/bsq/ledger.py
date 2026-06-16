"""Proposition-ledger authoring.

Each topic yields a matched pair: one checkable and one uncheckable proposition. This
fully crosses class with topic, so the checkable/uncheckable distinction is never
confounded with topic. Truth values are balanced independently within each class to
exactly 50% true (equal marginals, no cross-class leak). A configurable share of topics
is flagged placebo-irrelevant — orthogonal to class — to serve as the zero-displacement
control.

Two properties matter for the real-model extractor: proposition **ids are opaque**
(shuffled, never encoding class or truth) and **surface forms carry no class/truth cue**.
Surface forms are drawn — distinct, without replacement — from the frozen natural-language
corpus (:mod:`bsq.corpus`), ``n_topics`` per class per world from two disjoint pools; the
draw is a pure function of ``world_seed`` (the existing ``ledger`` substream), so arm-swap
replays stay byte-identical and no two propositions in a world look alike.
"""

from __future__ import annotations

import random

from bsq.corpus import CORPUS_CHECKABLE, CORPUS_UNCHECKABLE
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
    if len(CORPUS_CHECKABLE) < cfg.n_topics or len(CORPUS_UNCHECKABLE) < cfg.n_topics:
        raise ValueError(
            f"corpus too small for n_topics={cfg.n_topics}: "
            f"{len(CORPUS_CHECKABLE)} checkable, {len(CORPUS_UNCHECKABLE)} uncheckable"
        )

    rng = substream(world_seed, "ledger")
    n_placebo = round(cfg.n_topics * cfg.placebo_fraction)
    placebo_topics = set(rng.sample(range(cfg.n_topics), n_placebo)) if n_placebo else set()

    checkable_truth = _balanced_truth(cfg.n_topics, rng)
    uncheckable_truth = _balanced_truth(cfg.n_topics, rng)

    # Opaque ids, shuffled so an id value tracks neither topic order nor class.
    id_pool = [f"p{i:03d}" for i in range(2 * cfg.n_topics)]
    rng.shuffle(id_pool)
    pool = iter(id_pool)

    # Distinct surface forms drawn without replacement from each disjoint pool: no two
    # propositions in a world look alike (the fix for the pilot's duplicate-subject
    # artifact). Drawn after the id shuffle so id/truth/placebo assignments above are
    # unchanged; still a pure function of world_seed, so arm-swap replays stay identical.
    n = cfg.n_topics
    chk_forms = [CORPUS_CHECKABLE[i] for i in rng.sample(range(len(CORPUS_CHECKABLE)), n)]
    unc_forms = [CORPUS_UNCHECKABLE[i] for i in rng.sample(range(len(CORPUS_UNCHECKABLE)), n)]

    ledger: list[Proposition] = []
    for t in range(cfg.n_topics):
        topic_id = f"t{t:03d}"
        is_placebo = t in placebo_topics
        for cls, truth, verifiable, form in (
            (PropositionClass.CHECKABLE, checkable_truth[t], True, chk_forms[t]),
            (PropositionClass.UNCHECKABLE, uncheckable_truth[t], False, unc_forms[t]),
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
                    surface_form=form,
                )
            )
    forms = [p.surface_form for p in ledger]
    if len(set(forms)) != len(forms):  # disjoint pools + sampling w/o replacement => unreachable
        raise ValueError("corpus draw produced duplicate surface forms")
    return ledger
