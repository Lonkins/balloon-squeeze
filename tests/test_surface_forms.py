"""Surface forms and views: class-blind, truth-independent, and structurally safe."""

from __future__ import annotations

import dataclasses
import re

from bsq.ledger import author_ledger, surface_form_for
from bsq.models import GameConfig
from bsq.views import VIEW_FIELDS, PropositionView, proposition_views


def test_surface_form_is_a_pure_function_of_the_id() -> None:
    assert surface_form_for("p007") == surface_form_for("p007")
    assert surface_form_for("p007") != surface_form_for("p008")


def test_surface_form_carries_no_class_or_truth_cue() -> None:
    for token in ("p000", "p123"):
        text = surface_form_for(token).lower()
        for leak in ("checkable", "uncheckable", "true", "false"):
            assert leak not in text


def test_ledger_ids_are_opaque() -> None:
    for p in author_ledger(GameConfig(), 4):
        assert re.fullmatch(r"p\d{3}", p.id)  # opaque: no class/truth in the id
        assert p.surface_form == surface_form_for(p.id)


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
