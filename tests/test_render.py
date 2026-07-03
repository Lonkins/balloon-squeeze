"""The replay renderer: complete, escaped, deterministic, offline (FR-009/010).

The rendered HTML must present everything a record contains (board, discussion, claim
verdicts, verifier checks, votes, eliminations, scoreboard), neutralise hostile model
text, refuse unknown record versions, and reference no external resources.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from bsq.engine import run_game
from bsq.models import GameConfig
from bsq.record import finalize
from bsq.render import render_html

_GALLERY = Path(__file__).parent.parent / "examples" / "transcripts"


def _example_record() -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(
        (_GALLERY / "A1_announced.json").read_text(encoding="utf-8")
    )
    return parsed


def test_replay_contains_every_board_statement_vote_and_claim() -> None:
    record = _example_record()
    html = render_html(record)
    game = record["game"]
    for entry in game["board"]:
        assert entry["surface_form"] in html
    for participant in game["participants"]:
        assert participant["name"] in html
    n_claim_chips = sum(len(r["claims"]) for r in game["rounds"])
    assert html.count("claim-chip") >= n_claim_chips
    for r in game["rounds"]:
        if r["vote"] and r["vote"]["eliminated"]:
            assert "eliminated" in html.lower()
    assert "scoreboard" in html.lower()


def test_replay_reveals_the_audit_boundary_and_verdicts() -> None:
    html = render_html(_example_record())
    assert "[AUDITED]" in html and "[NOT AUDITED]" in html
    assert "lie" in html.lower()  # per-claim verdict chips


def test_hostile_utterance_text_renders_inert() -> None:
    record = _example_record()
    hostile = copy.deepcopy(record)
    hostile["game"]["rounds"][0]["utterances"][0]["text"] = (
        '<script>alert("xss")</script><img src=x onerror=alert(1)>'
    )
    html = render_html(hostile)
    assert '<script>alert("xss")</script>' not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html


def test_render_is_deterministic() -> None:
    record = _example_record()
    assert render_html(record) == render_html(record)


def test_unknown_record_version_is_refused() -> None:
    record = _example_record()
    record["record_version"] = 999
    with pytest.raises(ValueError, match="record_version"):
        render_html(record)


def test_replay_references_no_external_resources() -> None:
    html = render_html(_example_record())
    assert "http://" not in html
    assert "https://" not in html


def test_monologue_record_renders_without_vote_blocks() -> None:
    cfg = GameConfig(n_topics=4, rounds=2)
    record = finalize(run_game(cfg, 3).record_game)
    html = render_html(record)
    assert "scoreboard" in html.lower()
    assert '<div class="vote-block' not in html  # no vote panels in a monologue replay


def test_web_standards_reduced_motion_and_a11y() -> None:
    html = render_html(_example_record())
    assert "prefers-reduced-motion" in html  # transitions disabled for motion-sensitive users
    assert 'aria-live="polite"' in html  # the scoreboard announces updates
    assert 'aria-pressed' in html  # stateful controls expose their state
    assert 'aria-label="Replay controls"' in html
    # the mobile layout keeps the scoreboard in flow so it cannot obscure the timeline
    assert "max-width: 700px" in html and "position: static" in html


def test_early_end_is_shown() -> None:
    # The gallery example (seed 8) catches the impostor in the final round.
    record = _example_record()
    if record["game"]["ended_early"]:
        html = render_html(record)
        assert "impostor" in html.lower()
