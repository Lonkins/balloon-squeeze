"""What the extractor is allowed to see.

The extractor maps free text to propositions. It must be blind to ``truth_value`` (the
answer), to ``class_`` (so per-class extraction accuracy is not an artifact of the
extractor knowing the class), to the placebo flag, and to the verifier arm. We enforce
that *structurally*: the extractor is only ever handed ``PropositionView`` objects,
which carry exactly three fields — id, surface form, topic. There is no way to reach the
hidden fields from a view.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from bsq.models import Proposition

#: The only proposition fields the extractor may see.
VIEW_FIELDS: frozenset[str] = frozenset({"id", "surface_form", "topic_id"})


@dataclass(frozen=True, slots=True)
class PropositionView:
    """A truth-, class-, and arm-blind view of a proposition."""

    id: str
    surface_form: str
    topic_id: str


def proposition_views(ledger: Sequence[Proposition]) -> list[PropositionView]:
    """Project a ledger to the safe view the extractor is allowed to consume."""
    return [
        PropositionView(id=p.id, surface_form=p.surface_form, topic_id=p.topic_id)
        for p in ledger
    ]
