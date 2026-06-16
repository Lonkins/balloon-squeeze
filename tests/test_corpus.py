"""The proposition corpus: distinct, class-neutral, deterministic, replay-stable."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from bsq.corpus import CORPUS_CHECKABLE, CORPUS_UNCHECKABLE
from bsq.ledger import author_ledger
from bsq.models import STANDARD_ARMS, GameConfig


def test_pools_are_nonempty_and_disjoint() -> None:
    assert len(CORPUS_CHECKABLE) >= 8
    assert len(CORPUS_UNCHECKABLE) >= 8
    assert not (set(CORPUS_CHECKABLE) & set(CORPUS_UNCHECKABLE))  # no shared form across pools


def test_no_duplicate_surface_forms_in_a_world() -> None:
    # the regression test for the pilot's "parking listed four times" artifact
    for seed in range(50):
        forms = [p.surface_form for p in author_ledger(GameConfig(), seed)]
        assert len(set(forms)) == len(forms)


def test_ledger_forms_are_replay_identical_across_arms() -> None:
    # author_ledger depends only on (n_topics/placebo, world_seed) — never the arm — so every
    # arm of one world draws the identical id->form map (a precondition for byte-identical replay).
    base = [p.surface_form for p in author_ledger(GameConfig(), 11)]
    for arm in STANDARD_ARMS:
        forms = [p.surface_form for p in author_ledger(replace(GameConfig(), verifier_arm=arm), 11)]
        assert forms == base


def test_corpus_too_small_raises() -> None:
    with pytest.raises(ValueError, match="corpus too small"):
        author_ledger(GameConfig(n_topics=len(CORPUS_CHECKABLE) + 1), 0)


_FACTIVE = re.compile(
    r"\b(checkable|uncheckable|verified|confirmed that|approved that)\b", re.IGNORECASE
)


def test_no_factive_or_class_lexicon() -> None:
    # both-polarity-naturalness proxy: forbid presupposing/factive leads and class words, so
    # every entry reads naturally asserted OR denied and never names its own class.
    for text in (*CORPUS_CHECKABLE, *CORPUS_UNCHECKABLE):
        assert not _FACTIVE.search(text)


def test_entries_are_single_flat_declaratives() -> None:
    # structural-neutrality proxy (a stand-in until a blind class-guess-rate check is wired):
    # one bounded clause, no hedging opener, shared shape across both classes.
    for text in (*CORPUS_CHECKABLE, *CORPUS_UNCHECKABLE):
        assert text.endswith(".")
        assert text.count(".") == 1
        assert not re.match(r"^(maybe|perhaps|i think|it seems|possibly)\b", text, re.IGNORECASE)
