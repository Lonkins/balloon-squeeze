"""LLM extractor: prompt-build + defensive parsing, exercised with a fake client."""

from __future__ import annotations

from dataclasses import dataclass

from bsq.extract import llm_extract_claims
from bsq.llm.base import ChatTurn
from bsq.models import Utterance
from bsq.views import PropositionView


@dataclass(frozen=True)
class FakeLLM:
    """An ``LLMClient`` that returns a fixed string, for testing extraction parsing."""

    canned: str

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatTurn],
        max_tokens: int = 256,
        temperature: float = 0.0,
        stop: list[str] | None = None,
        seed: int | None = None,
    ) -> str:
        return self.canned


VIEWS = [
    PropositionView("p000", "statement zero", "t000"),
    PropositionView("p001", "statement one", "t000"),
]


def _utterance(text: str | None) -> Utterance:
    return Utterance(speaker_id="imp", round_idx=1, text=text)


def test_valid_json_extracts_claims() -> None:
    raw = (
        '[{"proposition_id":"p000","asserted_value":true},'
        '{"proposition_id":"p001","asserted_value":false}]'
    )
    claims = llm_extract_claims(_utterance("blah"), VIEWS, FakeLLM(raw))
    got = [(c.proposition_id, c.asserted_value) for c in claims]
    assert got == [("p000", True), ("p001", False)]
    assert all(c.speaker_id == "imp" and c.round_idx == 1 for c in claims)


def test_malformed_json_yields_no_claims() -> None:
    assert llm_extract_claims(_utterance("x"), VIEWS, FakeLLM("not json at all")) == []


def test_non_list_payload_yields_no_claims() -> None:
    raw = '{"proposition_id":"p000","asserted_value":true}'
    assert llm_extract_claims(_utterance("x"), VIEWS, FakeLLM(raw)) == []


def test_off_menu_and_non_bool_items_are_dropped() -> None:
    raw = (
        '[{"proposition_id":"ghost","asserted_value":true},'
        '{"proposition_id":"p000","asserted_value":"yes"},'
        '{"proposition_id":"p001","asserted_value":true}]'
    )
    claims = llm_extract_claims(_utterance("x"), VIEWS, FakeLLM(raw))
    assert [(c.proposition_id, c.asserted_value) for c in claims] == [("p001", True)]


def test_empty_text_skips_extraction() -> None:
    assert llm_extract_claims(_utterance(None), VIEWS, FakeLLM("[]")) == []


# --- real-model output formats (the 0-claims-pilot bug) --------------------

_REAL_VIEWS = [
    PropositionView(pid, f"statement {pid}", "t000")
    for pid in ("p009", "p011", "p014", "p015")
]


def test_parses_real_fenced_extractor_output() -> None:
    # the verbatim string a real model returned in the pilot: markdown-fenced JSON,
    # which bare json.loads rejects -> 0 claims for every utterance.
    raw = (
        '```json\n[\n  {"proposition_id": "p009", "asserted_value": true},\n'
        '  {"proposition_id": "p015", "asserted_value": true},\n'
        '  {"proposition_id": "p011", "asserted_value": false},\n'
        '  {"proposition_id": "p014", "asserted_value": false}\n]\n```'
    )
    claims = llm_extract_claims(_utterance("..."), _REAL_VIEWS, FakeLLM(raw))
    got = [(c.proposition_id, c.asserted_value) for c in claims]
    assert got == [("p009", True), ("p015", True), ("p011", False), ("p014", False)]


def test_plain_fence_extracts_claims() -> None:
    raw = '```\n[{"proposition_id":"p000","asserted_value":true}]\n```'
    claims = llm_extract_claims(_utterance("x"), VIEWS, FakeLLM(raw))
    assert [(c.proposition_id, c.asserted_value) for c in claims] == [("p000", True)]


def test_prose_then_array_extracts_claims() -> None:
    raw = 'Here are the claims:\n[{"proposition_id":"p001","asserted_value":false}]'
    claims = llm_extract_claims(_utterance("x"), VIEWS, FakeLLM(raw))
    assert [(c.proposition_id, c.asserted_value) for c in claims] == [("p001", False)]
