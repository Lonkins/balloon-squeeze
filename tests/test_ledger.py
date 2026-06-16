"""Ledger authoring: topic-matched, truth-balanced, placebo orthogonal to class."""

from __future__ import annotations

from bsq.ledger import author_ledger
from bsq.models import GameConfig, PropositionClass


def test_ledger_is_deterministic() -> None:
    cfg = GameConfig()
    assert author_ledger(cfg, 1) == author_ledger(cfg, 1)


def test_ledger_is_topic_matched() -> None:
    led = author_ledger(GameConfig(n_topics=8), 3)
    assert len(led) == 16
    by_topic: dict[str, set[PropositionClass]] = {}
    for p in led:
        by_topic.setdefault(p.topic_id, set()).add(p.class_)
    assert len(by_topic) == 8
    for classes in by_topic.values():
        assert classes == {PropositionClass.CHECKABLE, PropositionClass.UNCHECKABLE}


def test_truth_is_balanced_within_each_class() -> None:
    led = author_ledger(GameConfig(n_topics=8), 5)
    for cls in (PropositionClass.CHECKABLE, PropositionClass.UNCHECKABLE):
        props = [p for p in led if p.class_ is cls]
        assert sum(p.truth_value for p in props) == len(props) // 2


def test_placebo_is_orthogonal_to_class() -> None:
    led = author_ledger(GameConfig(n_topics=8, placebo_fraction=0.25), 7)
    placebo = [p for p in led if p.is_placebo_irrelevant]
    assert len(placebo) == 4  # round(8 * 0.25) topics x 2 classes
    n_checkable = sum(p.class_ is PropositionClass.CHECKABLE for p in placebo)
    assert n_checkable == 2  # split evenly across classes


def test_agent_verifiable_tracks_class() -> None:
    for p in author_ledger(GameConfig(), 9):
        assert p.agent_verifiable == (p.class_ is PropositionClass.CHECKABLE)


def test_different_seeds_generally_differ() -> None:
    assert author_ledger(GameConfig(), 1) != author_ledger(GameConfig(), 2)
