"""Proposition-ledger authoring.

Each topic yields a matched pair: one checkable and one uncheckable proposition. This
fully crosses class with topic, so the checkable/uncheckable distinction is never
confounded with topic. Truth values are balanced independently within each class to
exactly 50% true (equal marginals, no cross-class leak). A configurable share of topics
is flagged placebo-irrelevant — orthogonal to class — to serve as the zero-displacement
control.

Class is assigned per world as **engine-side metadata**, never carried by the text
(Architecture A). Surface forms are drawn — distinct, without replacement — from the
single frozen corpus (:mod:`bsq.corpus`), ``2 * n_topics`` per world from the ``ledger``
substream; then a *separate, arm-independent* ``class_assignment`` substream decides, per
topic, which of its two distinct forms is the checkable one. Because that coin is
independent of the form's content, the same string is checkable in one world and
uncheckable in another, so a blind classifier that sees only the string is at chance by
construction. Both draws are pure functions of ``world_seed``, so arm-swap replays stay
byte-identical and no two propositions in a world look alike.
"""

from __future__ import annotations

import random

from bsq.corpus import CORPUS_EVENTS
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
    if len(CORPUS_EVENTS) < 2 * cfg.n_topics:
        raise ValueError(
            f"corpus too small for n_topics={cfg.n_topics}: {len(CORPUS_EVENTS)} events, "
            f"need {2 * cfg.n_topics}"
        )

    n = cfg.n_topics
    rng = substream(world_seed, "ledger")
    n_placebo = round(n * cfg.placebo_fraction)
    placebo_topics = set(rng.sample(range(n), n_placebo)) if n_placebo else set()

    checkable_truth = _balanced_truth(n, rng)
    uncheckable_truth = _balanced_truth(n, rng)

    # Opaque ids, shuffled so an id value tracks neither topic order nor class.
    id_pool = [f"p{i:03d}" for i in range(2 * n)]
    rng.shuffle(id_pool)
    pool = iter(id_pool)

    # 2n distinct surface forms drawn without replacement from the single pool.
    forms = [CORPUS_EVENTS[i] for i in rng.sample(range(len(CORPUS_EVENTS)), 2 * n)]

    # Per-world class assignment from a DEDICATED, arm-independent substream: for each
    # topic, a content-independent coin picks which of its two distinct forms is checkable.
    # Kept separate from the 'ledger' stream so it never perturbs the id/truth/placebo
    # draws above, and arm-independent so arm-swap replays stay byte-identical.
    cls_rng = substream(world_seed, "class_assignment")

    ledger: list[Proposition] = []
    for t in range(n):
        topic_id = f"t{t:03d}"
        is_placebo = t in placebo_topics
        first, second = forms[2 * t], forms[2 * t + 1]
        chk_form, unc_form = (first, second) if cls_rng.random() < 0.5 else (second, first)
        for cls, truth, verifiable, form in (
            (PropositionClass.CHECKABLE, checkable_truth[t], True, chk_form),
            (PropositionClass.UNCHECKABLE, uncheckable_truth[t], False, unc_form),
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
    forms_seen = [p.surface_form for p in ledger]
    if len(set(forms_seen)) != len(forms_seen):  # sampling w/o replacement => unreachable
        raise ValueError("corpus draw produced duplicate surface forms")
    return ledger
