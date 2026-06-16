"""Verifier arms: no ground-truth leak, oracle confined to the checkable side."""

from __future__ import annotations

from dataclasses import replace

from bsq.engine import run_game
from bsq.models import STANDARD_ARMS, GameConfig, PropositionClass
from bsq.verifier import announcement_for, verify_checkable


def test_announcement_is_a_pure_function_of_the_arm() -> None:
    for arm in STANDARD_ARMS.values():
        assert announcement_for(arm) == announcement_for(arm)


def test_announcement_leaks_no_ground_truth() -> None:
    for arm in STANDARD_ARMS.values():
        text = announcement_for(arm)
        if text is None:
            continue
        low = text.lower()
        assert "true" not in low
        assert "false" not in low
        assert not any(ch.isdigit() for ch in text)  # no counts, no proposition ids


def test_which_arms_announce() -> None:
    assert announcement_for(STANDARD_ARMS["A0_off"]) is None
    assert announcement_for(STANDARD_ARMS["A2_silent"]) is None
    assert announcement_for(STANDARD_ARMS["A1_announced"]) is not None
    assert announcement_for(STANDARD_ARMS["A1_implicit"]) is not None
    assert announcement_for(STANDARD_ARMS["A3_placebo"]) is not None


def test_oracle_touches_only_checkable_propositions() -> None:
    res = run_game(replace(GameConfig(), verifier_arm="A1_announced"), 3)
    ledger = res.game.proposition_ledger
    uncheckable = {p.id for p in ledger if p.class_ is PropositionClass.UNCHECKABLE}
    touched = {v.proposition_id for v in res.verifications}
    assert touched
    assert touched.isdisjoint(uncheckable)


def test_oracle_is_invariant_to_uncheckable_truth_flips() -> None:
    res = run_game(replace(GameConfig(), verifier_arm="A1_announced"), 7)
    ledger = res.game.proposition_ledger
    flipped = [
        replace(p, truth_value=not p.truth_value)
        if p.class_ is PropositionClass.UNCHECKABLE
        else p
        for p in ledger
    ]
    assert verify_checkable(res.game.claims, ledger) == verify_checkable(res.game.claims, flipped)


def test_oracle_trace_identical_across_oracle_arms() -> None:
    cfg = GameConfig()
    traces = [
        run_game(replace(cfg, verifier_arm=arm), 9).verifications
        for arm in ("A1_announced", "A1_implicit", "A2_silent")
    ]
    assert traces[0]  # nonempty
    assert traces[0] == traces[1] == traces[2]


def test_non_oracle_arms_produce_no_verifications() -> None:
    for arm in ("A0_off", "A3_placebo"):
        assert run_game(replace(GameConfig(), verifier_arm=arm), 1).verifications == ()
