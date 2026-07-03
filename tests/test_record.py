"""Run records: completeness (FR-001), byte-identity (FR-002), default-on capture (FR-003).

A record must let a reader reconstruct the game without re-execution; the offline path
must serialize byte-identically for the same (config, seed); and every entry point —
CLI, probe, pilot — must persist records with no extra flags.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bsq.agents.llm_policy import LLMPolicy
from bsq.engine import run_game
from bsq.extract import make_llm_extractor
from bsq.llm.base import ChatTurn
from bsq.models import GameConfig, PropositionClass
from bsq.pilot import run_pilot
from bsq.probe import collect_arm
from bsq.record import (
    GAME_RECORD_VERSION,
    default_record_path,
    finalize,
    load_record,
    serialize,
)
from bsq.verifier import announcement_for
from bsq.views import AUDITED, NOT_AUDITED


def _interactive_result_and_record(seed: int = 42) -> tuple[object, dict[str, Any]]:
    cfg = GameConfig(n_topics=6, rounds=3, interactive=True, eliminate_between_rounds=False)
    result = run_game(cfg, seed)
    return result, finalize(result.record_game)


def test_record_is_complete_and_self_sufficient() -> None:
    cfg = GameConfig(n_topics=6, rounds=3, interactive=True, eliminate_between_rounds=False)
    result = run_game(cfg, 42)
    record = finalize(result.record_game)

    assert record["record_version"] == GAME_RECORD_VERSION
    game = record["game"]

    setup = game["setup"]
    assert setup["seed"] == 42 and setup["interactive"] is True
    assert setup["arm"] == "A0_off"
    assert setup["announcement"] == announcement_for(result.game.arm)

    board = game["board"]
    assert len(board) == 2 * cfg.n_topics
    per_topic: dict[str, set[str]] = {}
    forms = [b["surface_form"] for b in board]
    assert len(set(forms)) == len(forms)
    for b in board:
        assert b["class"] in ("checkable", "uncheckable")
        assert isinstance(b["truth_value"], bool)
        assert b["audit_tag"] is None  # A0_off announces no scope
        per_topic.setdefault(b["topic_id"], set()).add(b["class"])
    assert all(classes == {"checkable", "uncheckable"} for classes in per_topic.values())

    participants = game["participants"]
    assert sum(1 for p in participants if p["role"] == "impostor") == 1
    assert all(p["instruction"] for p in participants)

    rounds = game["rounds"]
    assert [r["round_idx"] for r in rounds] == list(range(len(rounds)))
    assert all("utterances" in r and "claims" in r and "verifications" in r for r in rounds)
    assert all(r["vote"] is not None for r in rounds)  # interactive: a vote block per round

    assert isinstance(game["ended_early"], bool)
    # scores match a hand-fold over the impostor's claims
    impostor = next(p["id"] for p in participants if p["role"] == "impostor")
    n_false = n_asserted = 0
    for r in rounds:
        for c in r["claims"]:
            if c["speaker_id"] == impostor and not c["is_placebo"] and c["audited"]:
                n_asserted += 1
                n_false += int(c["is_false"])
    assert game["scores"]["main_channel"]["checkable"]["n_false"] == n_false
    assert game["scores"]["main_channel"]["checkable"]["n_asserted"] == n_asserted


def test_audit_tags_present_iff_scope_announced() -> None:
    cfg = GameConfig(n_topics=4, verifier_arm="A1_announced")
    record = finalize(run_game(cfg, 7).record_game)
    tags = {b["audit_tag"] for b in record["game"]["board"]}
    assert tags == {AUDITED, NOT_AUDITED}


def test_game_payload_is_byte_identical_across_runs() -> None:
    _, first = _interactive_result_and_record()
    _, second = _interactive_result_and_record()
    assert serialize(first) == serialize(second)
    assert json.dumps(first["game"], sort_keys=True) == json.dumps(second["game"], sort_keys=True)


def test_claims_validate_against_the_board() -> None:
    _, record = _interactive_result_and_record()
    game = record["game"]
    board = {b["id"]: b for b in game["board"]}
    for r in game["rounds"]:
        for c in r["claims"]:
            prop = board[c["proposition_id"]]
            assert c["truth_value"] == prop["truth_value"]
            assert c["is_false"] == (c["asserted_value"] != prop["truth_value"])
            assert c["audited"] == (prop["class"] == "checkable")
            assert c["class"] == prop["class"]


def test_verifications_are_checkable_only() -> None:
    cfg = GameConfig(n_topics=6, verifier_arm="A2_silent")
    record = finalize(run_game(cfg, 3).record_game)
    game = record["game"]
    board = {b["id"]: b for b in game["board"]}
    votes_seen = 0
    for r in game["rounds"]:
        for v in r["verifications"]:
            assert board[v["proposition_id"]]["class"] == "checkable"
            votes_seen += 1
    assert votes_seen > 0  # A2 runs the oracle


class _FailingExtractorLLM:
    """A policy client that speaks, paired with an extractor client that returns junk."""

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
        return "I have opinions about several of these statements."


def test_extraction_failure_is_marked_on_the_exact_utterance() -> None:
    policy = LLMPolicy(_FailingExtractorLLM())
    junk_extractor = make_llm_extractor(_FailingExtractorLLM())  # non-JSON -> no claims
    cfg = GameConfig(n_topics=4, rounds=1, n_agents=3)
    result = run_game(
        cfg, 5, impostor_policy=policy, panelist_policy=policy, extractor=junk_extractor
    )
    record = finalize(result.record_game)
    utterances = record["game"]["rounds"][0]["utterances"]
    assert utterances and all(u["failure"] == "extraction_failed" for u in utterances)


def test_load_refuses_unknown_record_version(tmp_path: Path) -> None:
    _, record = _interactive_result_and_record()
    bogus = dict(record)
    bogus["record_version"] = 999
    path = tmp_path / "bogus.json"
    path.write_text(json.dumps(bogus), encoding="utf-8")
    with pytest.raises(ValueError, match="record_version"):
        load_record(path)
    good = tmp_path / "good.json"
    good.write_text(serialize(record), encoding="utf-8")
    assert load_record(good)["record_version"] == GAME_RECORD_VERSION


def test_default_record_path_encodes_arm_seed_and_mode(tmp_path: Path) -> None:
    cfg = GameConfig(verifier_arm="A1_announced", interactive=True)
    path = default_record_path(cfg, 7, base=tmp_path)
    assert path == tmp_path / "A1_announced-seed7-interactive.json"
    mono = default_record_path(GameConfig(verifier_arm="A0_off"), 3, base=tmp_path)
    assert mono == tmp_path / "A0_off-seed3.json"


def test_cli_run_writes_a_record_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bsq.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["run", "--seed", "7", "--arm", "A1_announced", "--interactive"]) == 0
    expected = tmp_path / "runs" / "A1_announced-seed7-interactive.json"
    assert expected.exists()
    assert "runs/A1_announced-seed7-interactive.json" in capsys.readouterr().out
    loaded = load_record(expected)
    assert loaded["game"]["setup"]["seed"] == 7


def test_cli_run_out_overrides_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bsq.cli import main

    monkeypatch.chdir(tmp_path)
    target = tmp_path / "custom" / "record.json"
    assert main(["run", "--seed", "3", "--out", str(target)]) == 0
    assert target.exists()
    assert not (tmp_path / "runs").exists()


def test_probe_persists_records_by_default(tmp_path: Path) -> None:
    cfg = GameConfig(n_topics=4, rounds=2)
    collect_arm(cfg, n_games=2, arm="A1_announced", base_seed=100, record_dir=tmp_path)
    written = sorted(p.name for p in tmp_path.glob("*.json"))
    assert written == ["A1_announced-seed100.json", "A1_announced-seed101.json"]
    assert load_record(tmp_path / written[0])["game"]["setup"]["arm"] == "A1_announced"


def test_pilot_persists_records_by_default(tmp_path: Path) -> None:
    cfg = GameConfig(n_topics=4, rounds=2)
    run_pilot(cfg, n_games=2, base_seed=50, record_dir=tmp_path)
    assert len(list(tmp_path.glob("A0_off-seed5*.json"))) == 2


def test_scores_exclude_placebo_in_main_channel() -> None:
    _, record = _interactive_result_and_record()
    scores = record["game"]["scores"]
    for cls in ("checkable", "uncheckable"):
        assert scores[cls]["n_asserted"] >= scores["main_channel"][cls]["n_asserted"]


def test_rates_are_null_not_nan_when_nothing_asserted() -> None:
    # A record must stay strict JSON: undefined rates serialize as null, never NaN.
    _, record = _interactive_result_and_record()
    text = serialize(record)
    assert "NaN" not in text
    json.loads(text)  # strict parse succeeds


def test_committed_example_gallery_matches_regeneration() -> None:
    # Drift lock: the committed transcripts must equal a fresh deterministic regeneration,
    # so the public examples can never silently diverge from the engine.
    from bsq.gallery import example_records

    gallery_dir = Path(__file__).parent.parent / "examples" / "transcripts"
    regenerated = example_records()
    assert sorted(p.name for p in gallery_dir.glob("*.json")) == sorted(regenerated)
    for filename, payload in regenerated.items():
        committed = (gallery_dir / filename).read_text(encoding="utf-8")
        assert committed == payload, f"{filename} drifted from regeneration"


def test_class_counts_match_engine_seat_score() -> None:
    cfg = GameConfig(n_topics=6, rounds=3)
    result = run_game(cfg, 9)
    record = finalize(result.record_game)
    seat = result.report.by_seat[result.game.impostor_id]
    main = record["game"]["scores"]["main_channel"]
    assert main["checkable"]["n_false"] == seat.checkable.n_false
    assert main["checkable"]["n_asserted"] == seat.checkable.n_asserted
    assert main["uncheckable"]["n_false"] == seat.uncheckable.n_false
    assert main["uncheckable"]["n_asserted"] == seat.uncheckable.n_asserted
    assert PropositionClass.CHECKABLE.value == "checkable"  # record uses the enum values
