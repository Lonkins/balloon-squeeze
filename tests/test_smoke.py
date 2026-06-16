"""Phase 0 smoke tests: trustworthy plumbing before any game logic."""

from __future__ import annotations

import pytest

from bsq.config import (
    game_config_from_env,
    provider_config_from_env,
    resolve_arm,
)
from bsq.events import EventBus
from bsq.llm import ChatTurn, make_client
from bsq.llm.base import ProviderConfig
from bsq.models import STANDARD_ARMS, Agent, Game, Persona, Role

# --- LLM abstraction -------------------------------------------------------

def test_mock_client_is_deterministic_under_a_seed() -> None:
    client = make_client(ProviderConfig(provider="mock"))
    messages = [ChatTurn(role="user", content="hello")]
    first = client.complete(system="sys", messages=messages, seed=7)
    second = client.complete(system="sys", messages=messages, seed=7)
    assert first == second
    assert isinstance(first, str) and first


def test_mock_seed_changes_output_deterministically() -> None:
    client = make_client(ProviderConfig(provider="mock"))
    messages = [ChatTurn(role="user", content="hello")]
    a = client.complete(system="sys", messages=messages, seed=1)
    b = client.complete(system="sys", messages=messages, seed=2)
    # Re-running each seed reproduces it exactly.
    assert a == client.complete(system="sys", messages=messages, seed=1)
    assert b == client.complete(system="sys", messages=messages, seed=2)


def test_make_client_rejects_unimplemented_and_unknown_providers() -> None:
    with pytest.raises(NotImplementedError):
        make_client(ProviderConfig(provider="ollama"))
    with pytest.raises(ValueError):
        make_client(ProviderConfig(provider="does-not-exist"))


# --- Config from env -------------------------------------------------------

def test_provider_config_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BSQ_PROVIDER", raising=False)
    cfg = provider_config_from_env()
    assert cfg.provider == "mock"
    assert make_client(cfg).complete(system="s", messages=[ChatTurn("user", "x")], seed=0)


def test_invalid_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSQ_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        provider_config_from_env()


def test_checkability_fraction_must_be_in_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSQ_CHECKABILITY_FRACTION", "1.5")
    with pytest.raises(ValueError):
        game_config_from_env()


def test_unknown_arm_raises() -> None:
    with pytest.raises(ValueError):
        resolve_arm("A9_nope")


def test_all_standard_arms_resolve() -> None:
    for name, arm in STANDARD_ARMS.items():
        assert resolve_arm(name) is arm


# --- Event bus -------------------------------------------------------------

def test_event_bus_is_append_only() -> None:
    bus = EventBus()
    bus.emit("game_start", cast=["a", "b"])
    bus.emit("message", speaker="a", text="hi")
    snapshot = bus.events
    assert len(snapshot) == 2
    assert snapshot[0].kind == "game_start"
    # The snapshot is a tuple; emitting more does not mutate it in place.
    bus.emit("message", speaker="b", text="yo")
    assert len(snapshot) == 2
    assert len(bus.events) == 3


def test_emitted_event_payload_is_read_only() -> None:
    bus = EventBus()
    event = bus.emit("vote", target="a")
    with pytest.raises(TypeError):
        event.payload["target"] = "b"  # type: ignore[index]


# --- Domain model ----------------------------------------------------------

def test_game_constructs_with_ground_truth_held() -> None:
    persona = Persona(id="noir", name="Noir", blurb="a gumshoe", voice="clipped")
    impostor = Agent(id="p1", persona=persona, role=Role.IMPOSTOR)
    panelist = Agent(id="p2", persona=persona, role=Role.PANELIST)
    game = Game(
        id="g1",
        seed=42,
        arm=STANDARD_ARMS["A0_off"],
        participants=[impostor, panelist],
        impostor_id="p1",
    )
    assert game.impostor_id == "p1"
    assert game.proposition_ledger == []
    assert {a.role for a in game.participants} == {Role.IMPOSTOR, Role.PANELIST}
