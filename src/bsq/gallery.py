"""The committed example-transcript gallery.

One deterministic, offline-generated run record per core experimental arm, committed
under ``examples/transcripts/`` so a visitor can read (and replay) a full game without
running anything. A drift-lock test regenerates the gallery and asserts the committed
files match, so the examples can never silently diverge from the engine.

The seed is chosen for a demonstrative game: all rounds are played, panelists are
eliminated along the way, the impostor lies in both channels, and (in interactive
arms) is caught by the final vote.
"""

from __future__ import annotations

from pathlib import Path

from bsq.engine import run_game
from bsq.models import STANDARD_ARMS, GameConfig
from bsq.record import default_record_path, finalize, serialize

EXAMPLE_SEED = 8
EXAMPLE_CONFIG = GameConfig(n_topics=12, rounds=3, interactive=True)


def example_records() -> dict[str, str]:
    """Serialized example record per core arm, keyed by destination filename."""
    gallery: dict[str, str] = {}
    for arm in STANDARD_ARMS:
        cfg = GameConfig(
            n_topics=EXAMPLE_CONFIG.n_topics,
            rounds=EXAMPLE_CONFIG.rounds,
            interactive=EXAMPLE_CONFIG.interactive,
            verifier_arm=arm,
        )
        result = run_game(cfg, EXAMPLE_SEED)
        record = finalize(result.record_game)
        name = default_record_path(cfg, EXAMPLE_SEED, base=Path(".")).name
        gallery[f"{arm}.json"] = serialize(record)
        del name  # filenames in the gallery are per-arm, not per-seed
    return gallery


def write_example_gallery(dest: Path) -> list[Path]:
    """(Re)generate the committed gallery; returns the written paths."""
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, payload in example_records().items():
        path = dest / filename
        path.write_text(payload, encoding="utf-8")
        written.append(path)
    return written
