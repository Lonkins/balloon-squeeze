"""What the extractor — and, separately, the speaking agent — is allowed to see.

Two distinct projections, deliberately different types so they can never be confused:

- :class:`PropositionView` is the **extractor's** view. It must be blind to ``truth_value``
  (the answer), to ``class_`` (so per-class extraction accuracy is not an artifact of the
  extractor knowing the class), to the placebo flag, and to the verifier arm. We enforce
  that *structurally*: the extractor is only ever handed ``PropositionView`` objects,
  which carry exactly three fields — id, surface form, topic. There is no way to reach the
  hidden fields from a view, and the audit tag below is NOT one of them.
- :class:`AgentMenuView` is the **speaking agent's** view. Under an arm that announces its
  audit scope (Architecture A) it carries an explicit ``[AUDITED]/[NOT AUDITED]`` tag — the
  out-of-band channel that replaces the old content cue. This view has no extractor
  consumer, so the tag can never leak class into the extraction path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from bsq.models import Proposition, PropositionClass, VerifierArm
from bsq.rng import substream

#: The only proposition fields the extractor may see. The audit tag is deliberately absent.
VIEW_FIELDS: frozenset[str] = frozenset({"id", "surface_form", "topic_id"})

AUDITED = "[AUDITED]"
NOT_AUDITED = "[NOT AUDITED]"


@dataclass(frozen=True, slots=True)
class PropositionView:
    """A truth-, class-, and arm-blind view of a proposition (the extractor's view)."""

    id: str
    surface_form: str
    topic_id: str


@dataclass(frozen=True, slots=True)
class AgentMenuView:
    """The speaking agent's view: surface form plus an out-of-band audit tag.

    ``audit_tag`` is ``[AUDITED]``/``[NOT AUDITED]`` only under an arm that announces its
    scope, and ``None`` otherwise — so the tag is the single, declarable channel through
    which the audit boundary reaches the agent.

    ``truth_mark`` is the impostor's **private truth briefing**: populated only when the
    menu is built with ``include_truth=True`` (the impostor's own menu), and always
    ``None`` for placebo items — the impostor knowingly lies only where it knows the
    truth, which is what lets the placebo channel isolate a tag-as-permission artifact
    instead of mirroring true displacement. Panelist menus and the extractor's
    :class:`PropositionView` can never carry it.
    """

    id: str
    surface_form: str
    topic_id: str
    audit_tag: str | None
    truth_mark: bool | None = None


def proposition_views(ledger: Sequence[Proposition]) -> list[PropositionView]:
    """Project a ledger to the safe view the extractor is allowed to consume."""
    return [
        PropositionView(id=p.id, surface_form=p.surface_form, topic_id=p.topic_id)
        for p in ledger
    ]


def agent_menu_views(
    ledger: Sequence[Proposition],
    arm: VerifierArm,
    *,
    include_truth: bool = False,
    world_seed: int | None = None,
) -> list[AgentMenuView]:
    """Project a ledger to the agent's menu, tagging audit scope only when announced.

    ``[AUDITED]`` is shown for checkable propositions (the ones the oracle verifies) and
    ``[NOT AUDITED]`` for uncheckable ones, but only when ``arm.announces_scope``; under
    every other arm the tag is ``None`` and the agent sees a bare menu (so ``A1_implicit``
    is a verifier-announced-but-scope-unknown arm).

    ``include_truth=True`` builds the **impostor's** menu: non-placebo items carry their
    private ``truth_mark`` (a pure function of the world, never the arm). Placebo items
    stay ``None`` on every menu.

    Under a ``shuffled_tags`` arm the displayed tags are drawn from a dedicated,
    world-pure substream independent of true class (``world_seed`` required), decoupling
    tag semantics from oracle coverage; the oracle itself is untouched.
    """
    tags = displayed_audit_tags(ledger, arm, world_seed=world_seed)
    return [
        AgentMenuView(
            id=p.id,
            surface_form=p.surface_form,
            topic_id=p.topic_id,
            audit_tag=tags[i],
            truth_mark=(
                p.truth_value if include_truth and not p.is_placebo_irrelevant else None
            ),
        )
        for i, p in enumerate(ledger)
    ]


def displayed_audit_tags(
    ledger: Sequence[Proposition],
    arm: VerifierArm,
    *,
    world_seed: int | None = None,
) -> list[str | None]:
    """The audit tags exactly as the agents' menus display them.

    ``None`` for every item when the arm does not announce its scope; the world-pure
    shuffle under a ``shuffled_tags`` arm. The single source of tag truth — the run
    record's board uses this too, so the record always shows what the menu showed.
    """
    return expected_display_tags([p.class_ for p in ledger], arm, world_seed=world_seed)


def expected_display_tags(
    classes: Sequence[PropositionClass],
    arm: VerifierArm,
    *,
    world_seed: int | None = None,
) -> list[str | None]:
    """Displayed tags from classes alone — lets a record consumer recompute what the
    board MUST contain (integrity checking) without materializing propositions."""
    if not arm.announces_scope:
        return [None for _ in classes]
    if arm.shuffled_tags:
        if world_seed is None:
            raise ValueError("shuffled_tags arm requires world_seed for the tag shuffle")
        rng = substream(world_seed, "shuffled_tags")
        return [AUDITED if rng.random() < 0.5 else NOT_AUDITED for _ in classes]
    return [
        AUDITED if c is PropositionClass.CHECKABLE else NOT_AUDITED for c in classes
    ]

