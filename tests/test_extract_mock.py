"""The extraction seam on the mock path: structured claims pass through verbatim."""

from __future__ import annotations

from bsq.extract import extract_claims
from bsq.models import StructuredClaim, Utterance


def test_structured_claims_pass_through() -> None:
    utterance = Utterance(
        speaker_id="p1",
        round_idx=2,
        structured=(StructuredClaim("c1", True), StructuredClaim("u1", False)),
    )
    claims = extract_claims(utterance, [])  # ledger is unused on the mock path
    assert [(c.proposition_id, c.asserted_value) for c in claims] == [("c1", True), ("u1", False)]
    assert all(c.speaker_id == "p1" and c.round_idx == 2 for c in claims)
    assert all(c.extractor_conf == 1.0 for c in claims)


def test_text_only_utterance_yields_no_claims_on_the_mock_path() -> None:
    utterance = Utterance(speaker_id="p1", round_idx=0, text="free text, no structure")
    assert extract_claims(utterance, []) == []
