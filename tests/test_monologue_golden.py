"""The monologue-mode golden regression: the measured configuration must never move.

The fixture was generated from the engine as it stood when the recorded real-model
results were produced (pre-interactive-mode). Every seed x arm world below must keep
reproducing the identical claim stream, event sequence, impostor seat counts, and
oracle verdicts. If this test fails, a change has altered the behaviour of the
configuration the published numbers are attached to — that is never acceptable;
fix the change, not this fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bsq.engine import run_game
from bsq.models import GameConfig

_FIXTURE = Path(__file__).parent / "fixtures" / "monologue_golden.json"


def _stable_surface(seed: int, arm: str) -> dict[str, Any]:
    cfg = GameConfig(verifier_arm=arm)
    result = run_game(cfg, seed)
    seat = result.report.by_seat[result.game.impostor_id]
    return {
        "seed": seed,
        "arm": arm,
        "impostor": result.game.impostor_id,
        "events": [e.kind for e in result.events],
        "claims": [
            [c.round_idx, c.speaker_id, c.proposition_id, c.asserted_value, c.is_false]
            for c in result.report.scored_claims
        ],
        "impostor_seat": {
            "checkable": [seat.checkable.n_false, seat.checkable.n_asserted],
            "uncheckable": [seat.uncheckable.n_false, seat.uncheckable.n_asserted],
            "placebo_checkable": [
                seat.placebo_checkable.n_false,
                seat.placebo_checkable.n_asserted,
            ],
            "placebo_uncheckable": [
                seat.placebo_uncheckable.n_false,
                seat.placebo_uncheckable.n_asserted,
            ],
        },
        "verifications": [
            [v.round_idx, v.proposition_id, v.asserted_value, v.truth_value, v.correct]
            for v in result.verifications
        ],
    }


def test_monologue_mode_matches_pre_change_golden() -> None:
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert len(golden) == 9  # 3 seeds x 3 arms
    for world in golden:
        regenerated = _stable_surface(world["seed"], world["arm"])
        assert regenerated == world, (
            f"monologue behaviour drifted for seed={world['seed']} arm={world['arm']} — "
            "the measured configuration must stay byte-identical"
        )
