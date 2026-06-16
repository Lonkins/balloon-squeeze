"""Surface forms and views: class-blind, truth-independent, and structurally safe."""

from __future__ import annotations

import dataclasses
import re

from bsq.corpus import CORPUS_CHECKABLE, CORPUS_UNCHECKABLE
from bsq.ledger import author_ledger
from bsq.models import GameConfig
from bsq.views import VIEW_FIELDS, PropositionView, proposition_views

_CORPUS = set(CORPUS_CHECKABLE) | set(CORPUS_UNCHECKABLE)


def test_surface_forms_are_deterministic_and_distinct_within_a_world() -> None:
    a = {p.id: p.surface_form for p in author_ledger(GameConfig(), 7)}
    b = {p.id: p.surface_form for p in author_ledger(GameConfig(), 7)}
    assert a == b  # same world seed -> identical id->form map (replay-safe)
    assert len(set(a.values())) == len(a)  # and no two forms in a world look alike


def test_surface_forms_carry_no_class_or_truth_cue() -> None:
    for text in _CORPUS:
        low = text.lower()
        for leak in ("checkable", "uncheckable", "true", "false"):
            assert leak not in low


def test_ledger_ids_are_opaque_and_forms_come_from_the_corpus() -> None:
    for p in author_ledger(GameConfig(), 4):
        assert re.fullmatch(r"p\d{3}", p.id)  # opaque: no class/truth in the id
        assert p.surface_form in _CORPUS


def test_ids_are_shuffled_not_positional() -> None:
    ids_in_build_order = [p.id for p in author_ledger(GameConfig(n_topics=8), 5)]
    assert ids_in_build_order != sorted(ids_in_build_order)  # decoupled from topic/class order


def test_view_exposes_only_the_safe_fields() -> None:
    names = {f.name for f in dataclasses.fields(PropositionView)}
    assert names == set(VIEW_FIELDS)
    assert "truth_value" not in names
    assert "class_" not in names
    assert "is_placebo_irrelevant" not in names


def test_proposition_views_strip_hidden_fields() -> None:
    ledger = author_ledger(GameConfig(), 3)
    views = proposition_views(ledger)
    assert len(views) == len(ledger)
    for view, prop in zip(views, ledger, strict=True):
        assert view.id == prop.id
        assert view.surface_form == prop.surface_form
        assert view.topic_id == prop.topic_id
        assert not hasattr(view, "truth_value")
        assert not hasattr(view, "class_")
