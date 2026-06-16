"""LLM agent policy + the real-text extraction pipe, exercised with fake clients."""

from __future__ import annotations

import random
from dataclasses import dataclass

from bsq.agents.llm_policy import LLMPolicy
from bsq.agents.policy import RoundContext
from bsq.engine import run_game
from bsq.extract import make_llm_extractor
from bsq.ledger import author_ledger
from bsq.llm.base import ChatTurn
from bsq.models import STANDARD_ARMS, Agent, GameConfig, Persona, Role


@dataclass(frozen=True)
class FakeLLM:
    """Returns a fixed string regardless of the prompt."""

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


def _agent(role: Role) -> Agent:
    return Agent(id="p1", persona=Persona(id="x", name="Nat", blurb="b", voice="dry"), role=role)


def _ctx(arm: str = "A0_off") -> RoundContext:
    return RoundContext(arm=STANDARD_ARMS[arm], announcement=None)


def test_llm_policy_emits_a_text_utterance() -> None:
    policy = LLMPolicy(FakeLLM("the shipment is fine"))
    ledger = author_ledger(GameConfig(), 0)
    utterance = policy.act(
        agent=_agent(Role.IMPOSTOR), ledger=ledger, round_idx=0, rng=random.Random(0), ctx=_ctx()
    )
    assert utterance.text == "the shipment is fine"
    assert utterance.structured == ()


def test_impostor_prompt_has_deception_incentive_panelist_does_not() -> None:
    policy = LLMPolicy(FakeLLM("x"))
    impostor_system = policy._system(_agent(Role.IMPOSTOR), _ctx())
    panelist_system = policy._system(_agent(Role.PANELIST), _ctx())
    assert "impostor" in impostor_system.lower()
    assert "deceive" in impostor_system.lower()
    assert "impostor" not in panelist_system.lower()


def test_announced_verifier_is_surfaced_only_when_scope_named() -> None:
    policy = LLMPolicy(FakeLLM("x"))
    announced = policy._system(_agent(Role.IMPOSTOR), _ctx("A1_announced"))
    silent = policy._system(_agent(Role.IMPOSTOR), _ctx("A0_off"))
    assert "verifier" in announced.lower()
    assert "verifier" not in silent.lower()


def test_real_text_pipe_produces_scored_claims() -> None:
    policy = LLMPolicy(FakeLLM("I'm certain about the budget and the shipment."))
    extractor_json = (
        '[{"proposition_id":"p000","asserted_value":true},'
        '{"proposition_id":"p001","asserted_value":false},'
        '{"proposition_id":"p002","asserted_value":true}]'
    )
    result = run_game(
        GameConfig(),
        0,
        impostor_policy=policy,
        panelist_policy=policy,
        extractor=make_llm_extractor(FakeLLM(extractor_json)),
    )
    assert len(result.game.claims) > 0
    seat = result.report.by_seat[result.game.impostor_id]
    total = (
        seat.checkable.n_asserted
        + seat.uncheckable.n_asserted
        + seat.placebo_checkable.n_asserted
        + seat.placebo_uncheckable.n_asserted
    )
    assert total > 0


def test_default_extractor_does_not_extract_free_text() -> None:
    # The seam: without the LLM extractor, free-text utterances yield no claims.
    policy = LLMPolicy(FakeLLM("just talking, no structure"))
    result = run_game(GameConfig(), 0, impostor_policy=policy, panelist_policy=policy)
    assert result.game.claims == []
