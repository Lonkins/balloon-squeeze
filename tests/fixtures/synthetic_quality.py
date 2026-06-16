"""A tiny hand-authored ledger + claim helper for known-answer eval tests.

SYNTHETIC ON PURPOSE: these labels verify the correction math only. They are never a
stand-in for a real human-labeled holdout (see tests/test_real_holdout_gate.py).
"""

from __future__ import annotations

from bsq.models import Claim, Proposition, PropositionClass

_C = PropositionClass.CHECKABLE
_U = PropositionClass.UNCHECKABLE

# Two checkable (p000 true, p001 false) and two uncheckable (p002 true, p003 false).
# (surface_form is irrelevant to the correction math, so it is left at its default.)
LEDGER = [
    Proposition("p000", _C, truth_value=True, topic_id="t000", agent_verifiable=True),
    Proposition("p001", _C, truth_value=False, topic_id="t001", agent_verifiable=True),
    Proposition("p002", _U, truth_value=True, topic_id="t000", agent_verifiable=False),
    Proposition("p003", _U, truth_value=False, topic_id="t001", agent_verifiable=False),
]

TRUTH = {p.id: p.truth_value for p in LEDGER}


def claim(speaker: str, round_idx: int, proposition_id: str, asserted: bool) -> Claim:
    """Build one claim. ``asserted`` is what the participant said about the proposition."""
    return Claim(
        round_idx=round_idx,
        speaker_id=speaker,
        proposition_id=proposition_id,
        asserted_value=asserted,
    )
