"""Surface forms and views: class-blind, truth-independent, and structurally safe."""

from __future__ import annotations

import dataclasses
import re

from bsq.corpus import CORPUS_EVENTS
from bsq.ledger import author_ledger
from bsq.models import STANDARD_ARMS, GameConfig, PropositionClass
from bsq.views import (
    AUDITED,
    NOT_AUDITED,
    VIEW_FIELDS,
    AgentMenuView,
    PropositionView,
    agent_menu_views,
    proposition_views,
)

_CORPUS = set(CORPUS_EVENTS)


def test_surface_forms_are_deterministic_and_distinct_within_a_world() -> None:
    a = {p.id: p.surface_form for p in author_ledger(GameConfig(), 7)}
    b = {p.id: p.surface_form for p in author_ledger(GameConfig(), 7)}
    assert a == b  # same world seed -> identical id->form map (replay-safe)
    assert len(set(a.values())) == len(a)  # and no two forms in a world look alike


def test_surface_forms_carry_no_class_or_truth_cue() -> None:
    for text in _CORPUS:
        low = text.lower()
        for leak in ("checkable", "uncheckable", "true", "false", "audited"):
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
    assert "audit_tag" not in names  # the extractor view never carries the audit tag


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


def test_agent_menu_tags_checkability_only_under_announced_scope() -> None:
    ledger = author_ledger(GameConfig(), 3)
    announced = agent_menu_views(ledger, STANDARD_ARMS["A1_announced"])
    for view, prop in zip(announced, ledger, strict=True):
        expected = AUDITED if prop.class_ is PropositionClass.CHECKABLE else NOT_AUDITED
        assert view.audit_tag == expected
    for arm in ("A0_off", "A1_implicit", "A2_silent", "A3_placebo"):
        for view in agent_menu_views(ledger, STANDARD_ARMS[arm]):
            assert view.audit_tag is None  # no tag unless the arm announces scope


def test_extractor_path_can_never_carry_the_audit_tag() -> None:
    # Blindness regression guard: the extractor view is a different type with no tag field,
    # and the menu string it produces never contains the tag tokens.
    ledger = author_ledger(GameConfig(), 5)
    extractor_menu = "\n".join(v.surface_form for v in proposition_views(ledger))
    assert AUDITED not in extractor_menu
    assert NOT_AUDITED not in extractor_menu
    assert "audit_tag" not in {f.name for f in dataclasses.fields(PropositionView)}
    assert "audit_tag" in {f.name for f in dataclasses.fields(AgentMenuView)}
