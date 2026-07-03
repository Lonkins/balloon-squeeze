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
from bsq.models import STANDARD_ARMS, Agent, GameConfig, Persona, Role, Utterance


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


def test_verifier_awareness_is_surfaced_per_arm() -> None:
    policy = LLMPolicy(FakeLLM("x"))
    impostor = _agent(Role.IMPOSTOR)
    announced = policy._system(impostor, _ctx("A1_announced"))
    implicit = policy._system(impostor, _ctx("A1_implicit"))
    off = policy._system(impostor, _ctx("A0_off"))
    silent = policy._system(impostor, _ctx("A2_silent"))
    # A1_announced names the audit tag; A1_implicit announces a verifier but no scope/tag.
    assert "verifier" in announced.lower() and "[audited]" in announced.lower()
    assert "verifier" in implicit.lower() and "[audited]" not in implicit.lower()
    # A0_off and A2_silent surface no verifier to the agent.
    assert "verifier" not in off.lower()
    assert "verifier" not in silent.lower()


class _RecordingLLM:
    """Captures the last (system, user) prompt so the rendered menu can be inspected."""

    def __init__(self) -> None:
        self.last_user = ""

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
        self.last_user = messages[-1].content
        return "ok"


def test_audit_tag_reaches_the_impostor_menu_but_not_the_panelist() -> None:
    client = _RecordingLLM()
    policy = LLMPolicy(client)
    ledger = author_ledger(GameConfig(), 2)
    ctx = _ctx("A1_announced")
    rng = random.Random(0)
    policy.act(agent=_agent(Role.IMPOSTOR), ledger=ledger, round_idx=0, rng=rng, ctx=ctx)
    impostor_menu = client.last_user
    policy.act(agent=_agent(Role.PANELIST), ledger=ledger, round_idx=0, rng=rng, ctx=ctx)
    panelist_menu = client.last_user
    assert "[AUDITED]" in impostor_menu and "[NOT AUDITED]" in impostor_menu
    assert "[AUDITED]" not in panelist_menu  # tag is impostor-only


def test_no_audit_tag_under_implicit_scope() -> None:
    client = _RecordingLLM()
    policy = LLMPolicy(client)
    ledger = author_ledger(GameConfig(), 2)
    policy.act(
        agent=_agent(Role.IMPOSTOR),
        ledger=ledger,
        round_idx=0,
        rng=random.Random(0),
        ctx=_ctx("A1_implicit"),
    )
    assert "[AUDITED]" not in client.last_user  # implicit arm shows no scope tag


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


def _interactive_ctx(history: tuple[Utterance, ...]) -> RoundContext:
    return RoundContext(
        arm=STANDARD_ARMS["A0_off"],
        announcement=None,
        history=history,
        speaker_names=(("p0", "Ash"), ("p1", "Nat"), ("p2", "Cyrus")),
    )


def test_discussion_so_far_renders_prior_utterances_verbatim() -> None:
    client = _RecordingLLM()
    policy = LLMPolicy(client)
    ledger = author_ledger(GameConfig(), 2)
    history = (
        Utterance(speaker_id="p0", round_idx=0, text="The manifest looked odd to me."),
        Utterance(speaker_id="p2", round_idx=0, text="I trust the audit numbers."),
    )
    policy.act(
        agent=_agent(Role.PANELIST),
        ledger=ledger,
        round_idx=1,
        rng=random.Random(0),
        ctx=_interactive_ctx(history),
    )
    assert "Discussion so far:" in client.last_user
    assert "Ash: The manifest looked odd to me." in client.last_user
    assert "Cyrus: I trust the audit numbers." in client.last_user


def test_monologue_prompt_has_no_discussion_block() -> None:
    client = _RecordingLLM()
    policy = LLMPolicy(client)
    ledger = author_ledger(GameConfig(), 2)
    policy.act(
        agent=_agent(Role.PANELIST), ledger=ledger, round_idx=1, rng=random.Random(0), ctx=_ctx()
    )
    assert "Discussion so far:" not in client.last_user


def _make_panelist(i: int, name: str) -> Agent:
    persona = Persona(id=f"x{i}", name=name, blurb="b", voice="dry")
    return Agent(id=f"p{i}", persona=persona, role=Role.PANELIST)


def _living() -> list[Agent]:
    return [_make_panelist(0, "Ash"), _make_panelist(1, "Nat"), _make_panelist(2, "Cyrus")]


def test_llm_vote_parses_exact_name_to_agent_id() -> None:
    policy = LLMPolicy(FakeLLM("Cyrus"))
    living = _living()
    target = policy.vote(
        agent=living[1],  # Nat votes
        living=living,
        round_idx=0,
        rng=random.Random(0),
        ctx=_interactive_ctx(()),
    )
    assert target == "p2"


def test_llm_vote_prompt_names_only_living_others() -> None:
    client = _RecordingLLM()
    policy = LLMPolicy(client)
    living = _living()
    policy.vote(
        agent=living[1],
        living=living,
        round_idx=0,
        rng=random.Random(0),
        ctx=_interactive_ctx(()),
    )
    assert "Ash" in client.last_user and "Cyrus" in client.last_user
    assert "Nat" not in client.last_user.split("Participants still in the discussion:")[1]


def test_llm_vote_garbage_records_abstain() -> None:
    for garbage in ("no idea, honestly!", "", "Everyone", "Nat"):  # incl. self-vote
        policy = LLMPolicy(FakeLLM(garbage))
        living = _living()
        target = policy.vote(
            agent=living[1],
            living=living,
            round_idx=0,
            rng=random.Random(0),
            ctx=_interactive_ctx(()),
        )
        assert target == "abstain", f"expected abstain for {garbage!r}"
