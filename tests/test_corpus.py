"""The proposition corpus: one flat pool, class-neutral by construction, replay-stable.

The headline guard is ``test_blind_class_guess_rate_is_at_chance`` — the empirical
re-measurement of the construct-validity confound that sank the old two-pool corpus
(82.8-95.3% blind separation). Under Architecture A class is per-world metadata over a
single pool, so the same string is checkable in some worlds and uncheckable in others and
a string-only classifier cannot beat chance.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import replace

import pytest

from bsq.corpus import CORPUS_EVENTS
from bsq.ledger import author_ledger
from bsq.models import STANDARD_ARMS, GameConfig, PropositionClass

_CHK = PropositionClass.CHECKABLE


def test_pool_is_nonempty_and_distinct() -> None:
    assert len(CORPUS_EVENTS) >= 16  # >= 2x the default n_topics=8
    assert len(set(CORPUS_EVENTS)) == len(CORPUS_EVENTS)  # no duplicate entries


def test_no_duplicate_surface_forms_in_a_world() -> None:
    # the regression test for the pilot's "parking listed four times" artifact
    for seed in range(50):
        forms = [p.surface_form for p in author_ledger(GameConfig(), seed)]
        assert len(set(forms)) == len(forms)


def test_ledger_is_replay_identical_across_arms() -> None:
    # author_ledger depends only on (n_topics/placebo, world_seed) — never the arm — so every
    # arm of one world draws the identical id->form map AND the identical id->class map (both
    # preconditions for byte-identical replay; class assignment must not depend on the arm).
    base = author_ledger(GameConfig(), 11)
    base_forms = {p.id: p.surface_form for p in base}
    base_class = {p.id: p.class_ for p in base}
    for arm in STANDARD_ARMS:
        led = author_ledger(replace(GameConfig(), verifier_arm=arm), 11)
        assert {p.id: p.surface_form for p in led} == base_forms
        assert {p.id: p.class_ for p in led} == base_class


def test_corpus_too_small_raises() -> None:
    with pytest.raises(ValueError, match="corpus too small"):
        author_ledger(GameConfig(n_topics=len(CORPUS_EVENTS) // 2 + 1), 0)


_FACTIVE = re.compile(
    r"\b(checkable|uncheckable|verified|confirmed that|approved that)\b", re.IGNORECASE
)


def test_no_factive_or_class_lexicon() -> None:
    # both-polarity-naturalness proxy: forbid presupposing/factive leads and class words, so
    # every entry reads naturally asserted OR denied and never names its own class.
    for text in CORPUS_EVENTS:
        assert not _FACTIVE.search(text)


def test_entries_are_single_flat_declaratives() -> None:
    # structural neutrality: one bounded clause, no hedging opener, shared shape for the
    # whole pool (so no subset is intrinsically "an intention" or "a public record").
    for text in CORPUS_EVENTS:
        assert text.endswith(".")
        assert text.count(".") == 1
        assert not re.match(r"^(maybe|perhaps|i think|it seems|possibly)\b", text, re.IGNORECASE)


def _form_class_corpus(n_worlds: int, n_topics: int) -> list[tuple[str, bool]]:
    """Collect (surface_form, is_checkable) instances across many worlds."""
    data: list[tuple[str, bool]] = []
    for seed in range(n_worlds):
        for p in author_ledger(GameConfig(n_topics=n_topics), seed):
            data.append((p.surface_form, p.class_ is _CHK))
    return data


def _nb_holdout_accuracy(data: list[tuple[str, bool]]) -> float:
    """Word-level multinomial NB trained on the first half of worlds, tested on the second."""
    mid = len(data) // 2
    train, test = data[:mid], data[mid:]
    tok = re.compile(r"[a-z']+")
    cc: dict[bool, Counter[str]] = {True: Counter(), False: Counter()}
    ndoc = {True: 0, False: 0}
    ntok = {True: 0, False: 0}
    vocab: set[str] = set()
    for text, is_chk in train:
        words = tok.findall(text.lower())
        cc[is_chk].update(words)
        ndoc[is_chk] += 1
        ntok[is_chk] += len(words)
        vocab |= set(words)
    v = len(vocab)
    correct = 0
    for text, is_chk in test:
        best, best_lp = True, -math.inf
        for label in (True, False):
            lp = math.log(ndoc[label] / len(train))
            for w in tok.findall(text.lower()):
                lp += math.log((cc[label][w] + 1) / (ntok[label] + v))
            if lp > best_lp:
                best_lp, best = lp, label
        correct += best == is_chk
    return correct / len(test)


def _per_form_majority_accuracy(data: list[tuple[str, bool]]) -> float:
    """The strongest string-only classifier: always predict each form's majority class."""
    counts: dict[str, Counter[bool]] = {}
    for form, is_chk in data:
        counts.setdefault(form, Counter())[is_chk] += 1
    total = correct = 0
    for c in counts.values():
        total += c[True] + c[False]
        correct += max(c[True], c[False])
    return correct / total


def test_blind_class_guess_rate_is_at_chance() -> None:
    # The confound gate. Two pre-registered string-only classifiers over 400 worlds:
    # (1) a word-level NB with a world holdout split, (2) a per-form majority-class oracle
    # (the ceiling of any classifier that sees only the form). Both must sit at chance —
    # the old corpus separated at 82.8-95.3%. Deterministic (fixed seeds).
    data = _form_class_corpus(n_worlds=400, n_topics=16)
    nb = _nb_holdout_accuracy(data)
    oracle = _per_form_majority_accuracy(data)
    assert nb <= 0.58, f"word-NB separated class at {nb:.3f} (> 0.58 chance band)"
    assert oracle <= 0.58, f"per-form majority oracle separated class at {oracle:.3f} (> 0.58)"


def test_same_form_appears_under_both_classes_across_worlds() -> None:
    # surface-form -> class is NOT stable: the de-confounding invariant. At least most forms
    # appear as BOTH checkable and uncheckable across seeds.
    seen: dict[str, set[bool]] = {}
    for seed in range(120):
        for p in author_ledger(GameConfig(n_topics=16), seed):
            seen.setdefault(p.surface_form, set()).add(p.class_ is _CHK)
    both = sum(1 for classes in seen.values() if classes == {True, False})
    assert both >= 0.9 * len(seen)  # nearly every drawn form flips class across worlds
