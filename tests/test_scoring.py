"""Scoring: per-class false-mass on planted transcripts (the Phase 1 DoD test)."""

from __future__ import annotations

import math

import pytest

from bsq.models import Claim, Proposition, PropositionClass
from bsq.scoring import score_claims

CHECKABLE = PropositionClass.CHECKABLE
UNCHECKABLE = PropositionClass.UNCHECKABLE


def _prop(pid: str, cls: PropositionClass, truth: bool, *, placebo: bool = False) -> Proposition:
    return Proposition(
        id=pid,
        class_=cls,
        truth_value=truth,
        topic_id=pid,
        agent_verifiable=cls is CHECKABLE,
        is_placebo_irrelevant=placebo,
    )


def test_false_mass_counts_and_rates_are_exact() -> None:
    ledger = [
        _prop("c1", CHECKABLE, True),
        _prop("c2", CHECKABLE, True),
        _prop("u1", UNCHECKABLE, False),
    ]
    claims = [
        Claim(round_idx=0, speaker_id="imp", proposition_id="c1", asserted_value=True),  # truthful
        Claim(round_idx=0, speaker_id="imp", proposition_id="c2", asserted_value=False),  # false
        Claim(round_idx=0, speaker_id="imp", proposition_id="u1", asserted_value=True),  # false
    ]
    seat = score_claims(claims, ledger).by_seat["imp"]
    assert (seat.checkable.n_false, seat.checkable.n_asserted) == (1, 2)
    assert (seat.uncheckable.n_false, seat.uncheckable.n_asserted) == (1, 1)
    assert seat.c == 0.5
    assert seat.u == 1.0


def test_is_false_is_set_on_scored_claims() -> None:
    ledger = [_prop("c1", CHECKABLE, True)]
    claims = [Claim(round_idx=0, speaker_id="imp", proposition_id="c1", asserted_value=False)]
    scored = score_claims(claims, ledger).scored_claims
    assert scored[0].is_false is True


def test_empty_class_rate_is_nan_not_zero() -> None:
    ledger = [_prop("c1", CHECKABLE, True)]
    claims = [Claim(round_idx=0, speaker_id="imp", proposition_id="c1", asserted_value=True)]
    seat = score_claims(claims, ledger).by_seat["imp"]
    assert seat.c == 0.0
    assert math.isnan(seat.u)  # nothing asserted in the uncheckable class -> undefined


def test_placebo_is_kept_out_of_the_main_channel() -> None:
    ledger = [_prop("c1", CHECKABLE, True, placebo=True)]
    claims = [Claim(round_idx=0, speaker_id="imp", proposition_id="c1", asserted_value=False)]
    seat = score_claims(claims, ledger).by_seat["imp"]
    assert seat.checkable.n_asserted == 0
    assert (seat.placebo_checkable.n_false, seat.placebo_checkable.n_asserted) == (1, 1)


def test_unknown_proposition_raises() -> None:
    ghost = Claim(round_idx=0, speaker_id="imp", proposition_id="ghost", asserted_value=True)
    with pytest.raises(KeyError):
        score_claims([ghost], [])
