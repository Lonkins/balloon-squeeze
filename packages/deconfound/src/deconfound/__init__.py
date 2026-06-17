"""deconfound — does your condition label leak into item *content*? (pure stdlib)

Before trusting any A/B contrast whose two conditions use *different items* — "easy vs
hard to monitor", "checkable vs uncheckable", "harmful vs benign" — check that a blind
classifier cannot recover the condition label from the item text alone. If it can (above
the majority-class baseline), your conditions differ in **content**, not only in your
manipulation: a construct confound that no downstream correction repairs, because the
conditions are collinear by design.

The recipe (from *Balloon Squeeze*, where it caught an 82.8-95.3% confound and drove it to
chance):

  1. ``separability_report`` — run two blind, string-only classifiers over your labelled
     items and compare against the majority-class baseline:
     - a word-level multinomial Naive Bayes on a held-out split (generalisation), and
     - a per-form majority oracle (the ceiling of any classifier that sees only the text;
       meaningful when the *same* item appears under different labels across draws, the
       de-confounded design where class is per-draw metadata).
  2. If either beats chance by more than ``tolerance``, the verdict is ``confounded``.

Pure standard library, no dependencies. The classifiers are deliberately weak: if even a
weak blind classifier separates your conditions, a referee's stronger one certainly will.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from collections.abc import Hashable, Iterable
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z0-9']+")

#: One labelled item: its text and the condition label it was assigned.
LabeledItem = tuple[str, Hashable]


@dataclass(frozen=True, slots=True)
class SeparabilityReport:
    """How separable the condition labels are from item content alone."""

    nb_holdout: float  # word-level Naive Bayes accuracy on a held-out split
    per_form_oracle: float  # ceiling of any form-only classifier (per-text majority label)
    chance: float  # majority-class baseline (a classifier that always guesses the top class)
    n_items: int
    n_classes: int
    tolerance: float

    @property
    def is_confounded(self) -> bool:
        """True if either blind classifier beats the majority baseline by > ``tolerance``."""
        margin = self.chance + self.tolerance
        return self.nb_holdout > margin or self.per_form_oracle > margin

    @property
    def verdict(self) -> str:
        return "confounded" if self.is_confounded else "at-chance"


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def blind_guess_rate(items: Iterable[LabeledItem], *, seed: int = 0) -> float:
    """Word-level multinomial Naive Bayes accuracy on a deterministic 50/50 holdout split.

    Returns ``nan`` for fewer than two items; 1.0 for a single class (trivially separable).
    """
    data = list(items)
    if len(data) < 2:
        return math.nan
    if len({label for _, label in data}) < 2:
        return 1.0
    order = list(range(len(data)))
    random.Random(seed).shuffle(order)
    mid = len(data) // 2
    train = [data[i] for i in order[:mid]]
    test = [data[i] for i in order[mid:]]
    if not train or not test:
        return math.nan

    word_counts: dict[Hashable, Counter[str]] = {}
    n_doc: Counter[Hashable] = Counter()
    n_tok: Counter[Hashable] = Counter()
    vocab: set[str] = set()
    for text, label in train:
        toks = _tokens(text)
        word_counts.setdefault(label, Counter()).update(toks)
        n_doc[label] += 1
        n_tok[label] += len(toks)
        vocab.update(toks)
    v = len(vocab)

    correct = 0
    for text, label in test:
        best: Hashable = None
        best_lp = -math.inf
        for c, wc in word_counts.items():
            lp = math.log(n_doc[c] / len(train))
            for w in _tokens(text):
                lp += math.log((wc[w] + 1) / (n_tok[c] + v))
            if lp > best_lp:
                best_lp, best = lp, c
        correct += int(best == label)
    return correct / len(test)


def per_form_oracle(items: Iterable[LabeledItem]) -> float:
    """Accuracy of always predicting each text's majority label — the form-only ceiling.

    For a corpus where every text has one fixed label this is trivially 1.0; it is the
    informative metric when the *same* text appears under different labels across draws.
    """
    data = list(items)
    if not data:
        return math.nan
    by_text: dict[str, Counter[Hashable]] = {}
    for text, label in data:
        by_text.setdefault(text, Counter())[label] += 1
    correct = total = 0
    for c in by_text.values():
        total += sum(c.values())
        correct += max(c.values())
    return correct / total


def separability_report(
    items: Iterable[LabeledItem], *, seed: int = 0, tolerance: float = 0.05
) -> SeparabilityReport:
    """Run both blind classifiers and the baseline; bundle into a verdict."""
    data = list(items)
    if not data:
        raise ValueError("no items to assess")
    counts = Counter(label for _, label in data)
    return SeparabilityReport(
        nb_holdout=blind_guess_rate(data, seed=seed),
        per_form_oracle=per_form_oracle(data),
        chance=max(counts.values()) / len(data),
        n_items=len(data),
        n_classes=len(counts),
        tolerance=tolerance,
    )


def is_confounded(
    items: Iterable[LabeledItem], *, seed: int = 0, tolerance: float = 0.05
) -> bool:
    """Convenience: True if the condition labels are recoverable from content above chance."""
    return separability_report(items, seed=seed, tolerance=tolerance).is_confounded


__all__ = [
    "LabeledItem",
    "SeparabilityReport",
    "blind_guess_rate",
    "is_confounded",
    "per_form_oracle",
    "separability_report",
]
__version__ = "0.1.0"
