"""deconfound: catches a content-encoded confound, passes a de-confounded design."""

from __future__ import annotations

import math

import pytest

from deconfound import blind_guess_rate, is_confounded, per_form_oracle, separability_report

# A content-encoded corpus: checkable = logged events, uncheckable = private-intention predicates.
_CONFOUNDED = [
    ("The Rotterdam container cleared customs on the third.", "checkable"),
    ("Forty-one candidates applied for the platform opening.", "checkable"),
    ("The generator was serviced on the twenty-second.", "checkable"),
    ("The annual audit covered three fiscal years.", "checkable"),
    ("The conference drew two hundred registrations.", "checkable"),
    ("Park privately judged the account renewal already lost.", "uncheckable"),
    ("Sato meant to drop the vendor once a cheaper bid surfaced.", "uncheckable"),
    ("Reyes had ruled out the finalist before the panel convened.", "uncheckable"),
    ("Voss resolved to defer the worst finding on purpose.", "uncheckable"),
    ("Halloran padded the figure expecting the usual cuts.", "uncheckable"),
]


def _deconfounded() -> list[tuple[str, str]]:
    # One flat-event pool; each string assigned BOTH classes across draws (Architecture A),
    # so the form carries no class signal.
    events = [
        "The dock logged fourteen pallets on Tuesday.",
        "Adeyemi logged thirty-two hours on the account.",
        "The cluster restarted twice in the window.",
        "Okafor approved the expense report on the eighth.",
        "The lab ran three hundred checks before release.",
        "Whitfield renewed the contract for eighteen months.",
    ]
    items: list[tuple[str, str]] = []
    for e in events:
        items.append((e, "checkable"))
        items.append((e, "uncheckable"))
    return items


def test_content_encoded_corpus_is_confounded() -> None:
    rep = separability_report(_CONFOUNDED)
    assert rep.verdict == "confounded"
    assert rep.is_confounded
    assert rep.per_form_oracle == 1.0  # each text has one fixed label -> trivially separable
    assert rep.chance == 0.5  # balanced 5/5
    assert rep.n_items == 10 and rep.n_classes == 2


def test_per_world_metadata_design_is_at_chance() -> None:
    rep = separability_report(_deconfounded())
    assert rep.verdict == "at-chance"
    assert not rep.is_confounded
    assert rep.per_form_oracle == 0.5  # same text both classes -> form carries no signal
    assert math.isclose(rep.chance, 0.5)


def test_blind_guess_rate_catches_a_strong_lexical_signal() -> None:
    # a generalisable lexical cue (class A always says 'alpha', B always 'beta') is exactly
    # what the held-out NB exists to detect; on a clean signal it separates near-perfectly.
    items = [(f"the alpha event number {i}", "A") for i in range(12)]
    items += [(f"the beta event number {i}", "B") for i in range(12)]
    assert blind_guess_rate(items, seed=0) > 0.8


def test_per_form_oracle_on_repeated_texts() -> None:
    items = [("a", "x"), ("a", "x"), ("a", "y"), ("b", "y")]  # 'a': 2x/1y -> 2; 'b': 1
    assert per_form_oracle(items) == 0.75  # (2 + 1) / (3 + 1)


def test_single_class_is_trivially_separable_and_empty_raises() -> None:
    assert blind_guess_rate([("a", "x"), ("b", "x")]) == 1.0
    assert math.isnan(blind_guess_rate([("a", "x")]))  # < 2 items
    with pytest.raises(ValueError, match="no items"):
        separability_report([])


def test_is_confounded_convenience() -> None:
    assert is_confounded(_CONFOUNDED)
    assert not is_confounded(_deconfounded())
