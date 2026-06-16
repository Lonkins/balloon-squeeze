"""The extraction seam: an utterance becomes claims.

On the mock path this is a trivial pass-through of already-structured claims. The
Phase-3 real-model extractor (free text -> claims) slots in behind this same
signature, so the engine never changes. Both paths produce :class:`Claim` objects;
scoring stays blind to which path produced them.
"""

from __future__ import annotations

from collections.abc import Sequence

from bsq.models import Claim, Proposition, Utterance


def extract_claims(utterance: Utterance, ledger: Sequence[Proposition]) -> list[Claim]:
    """Turn an utterance into scored-but-not-yet-judged claims.

    ``ledger`` is unused on the mock path; it is part of the signature so the Phase-3
    extractor can resolve free text against the proposition set without an engine change.
    """
    del ledger  # used by the real-model extractor (Phase 3), not the mock pass-through
    return [
        Claim(
            round_idx=utterance.round_idx,
            speaker_id=utterance.speaker_id,
            proposition_id=sc.proposition_id,
            asserted_value=sc.asserted_value,
            extractor_conf=1.0,
        )
        for sc in utterance.structured
    ]
