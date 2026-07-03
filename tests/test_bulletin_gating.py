"""Per-arm bulletin gating: broadcasting is an explicit arm property.

The consequence-coupling change emitted verifier bulletins for ANY oracle arm in
interactive mode, which made A2_silent — the kill rule's content-artifact control,
publicly defined as "the verifier runs but is never announced" — broadcast its verdicts
to the group. These pins make broadcasting an opt-in per-arm property
(``VerifierArm.broadcasts_verdicts``) and keep every covert/announced semantic exactly
as documented:

- A2_silent is genuinely covert in BOTH modes (the oracle still runs, silently);
- announced arms broadcast exactly as before;
- A4_feedback_revealed announces nothing up front but broadcasts in-game, so the
  boundary is learnable only from observed feedback (calibration arm, never pooled,
  never feeding the kill rule).
"""

from __future__ import annotations

import random

from bsq.agents.llm_policy import LLMPolicy
from bsq.agents.policy import RoundContext
from bsq.engine import run_game
from bsq.ledger import author_ledger
from bsq.llm.base import ChatTurn
from bsq.models import (
    CONTROL_ARMS,
    STANDARD_ARMS,
    Agent,
    GameConfig,
    Persona,
    Role,
)
from bsq.record import finalize
from bsq.views import agent_menu_views


def _interactive_cfg(arm: str) -> GameConfig:
    return GameConfig(
        n_topics=6, rounds=2, n_agents=3, verifier_arm=arm,
        interactive=True, eliminate_between_rounds=False,
    )


def test_a2_silent_interactive_is_genuinely_covert() -> None:
    result = run_game(_interactive_cfg("A2_silent"), 3)
    assert result.verifications  # the oracle still runs — covertly
    assert all(e.kind != "verifier_bulletin" for e in result.events)
    record = finalize(result.record_game)
    for round_entry in record["game"]["rounds"]:
        assert "bulletin" not in round_entry
        assert all(u["speaker_id"] != "verifier" for u in round_entry["utterances"])


def test_announced_arms_still_broadcast() -> None:
    for arm in ("A1_announced", "A1_implicit"):
        result = run_game(_interactive_cfg(arm), 3)
        assert any(e.kind == "verifier_bulletin" for e in result.events), arm
        record = finalize(result.record_game)
        entries = record["game"]["rounds"][0]["bulletin"]["entries"]
        assert entries, arm
        assert {"speaker_id", "proposition_id", "surface_form", "verdict"} <= set(entries[0])


def test_broadcast_registry_invariants() -> None:
    all_arms = {**STANDARD_ARMS, **CONTROL_ARMS}
    for name, arm in all_arms.items():
        if arm.broadcasts_verdicts:
            assert arm.runs_oracle, f"{name} broadcasts but has no oracle to broadcast"
    assert not (STANDARD_ARMS.keys() & CONTROL_ARMS.keys())
    assert STANDARD_ARMS["A2_silent"].broadcasts_verdicts is False
    assert STANDARD_ARMS["A1_announced"].broadcasts_verdicts is True
    assert STANDARD_ARMS["A1_implicit"].broadcasts_verdicts is True
    assert CONTROL_ARMS["A1_positive_control"].broadcasts_verdicts is True
    assert CONTROL_ARMS["A1_shuffled_tags"].broadcasts_verdicts is True
    assert "A4_feedback_revealed" not in STANDARD_ARMS
    a4 = CONTROL_ARMS["A4_feedback_revealed"]
    assert (a4.announces_verifier, a4.announces_scope, a4.runs_oracle) == (False, False, True)
    assert a4.broadcasts_verdicts is True


class _RecordingLLM:
    """Captures every (system, user) prompt pair; answers a fixed line."""

    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

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
        self.prompts.append((system, messages[-1].content))
        return "I have nothing further to add."


def test_a4_reveals_nothing_up_front() -> None:
    """A4 menus carry no tags; A4 prompts contain no verifier announcement."""
    arm = CONTROL_ARMS["A4_feedback_revealed"]
    cfg = GameConfig(n_topics=8)
    ledger = author_ledger(cfg, 5)
    views = agent_menu_views(ledger, arm, world_seed=5)
    assert all(v.audit_tag is None for v in views)

    client = _RecordingLLM()
    policy = LLMPolicy(client)
    ctx = RoundContext(arm=arm, announcement=None, world_seed=5)
    impostor = Agent(
        id="p1", persona=Persona(id="x", name="Ash", blurb="b", voice="dry"),
        role=Role.IMPOSTOR,
    )
    policy.act(agent=impostor, ledger=ledger, round_idx=0, rng=random.Random(0), ctx=ctx)
    system, user = client.prompts[-1]
    for phrase in (
        "A verifier will fact-check",
        "A verifier is fact-checking",
        "announced to the group",
        "[AUDITED]",
        "[NOT AUDITED]",
    ):
        assert phrase not in system and phrase not in user, phrase


def test_a4_replay_identity_with_a0() -> None:
    """The world is byte-identical across the arm swap (A4 vs A0, same seed)."""
    boards = {
        arm: finalize(run_game(_interactive_cfg(arm), 7).record_game)["game"]["board"]
        for arm in ("A4_feedback_revealed", "A0_off")
    }
    assert boards["A4_feedback_revealed"] == boards["A0_off"]


def test_a4_bulletins_flow_and_analyze_groups_separately(tmp_path: object) -> None:
    """A4 broadcasts in-game, and analyze keys its records to their own group."""
    from pathlib import Path

    from bsq.analyze import analyze_paths
    from bsq.record import default_record_path, write_record

    out = Path(str(tmp_path))
    for seed in (1, 2):
        cfg = _interactive_cfg("A4_feedback_revealed")
        result = run_game(cfg, seed)
        assert any(e.kind == "verifier_bulletin" for e in result.events)
        write_record(finalize(result.record_game), default_record_path(cfg, seed, base=out))
    report = analyze_paths([out], seed=0)
    assert set(report.groups) == {("A4_feedback_revealed", True)}
