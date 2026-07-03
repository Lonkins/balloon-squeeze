"""The committed example-transcript gallery and the Pages-servable demo site.

One deterministic, offline-generated run record per core experimental arm, committed
under ``examples/transcripts/`` so a visitor can read (and replay) a full game without
running anything — plus rendered replays and an index page under ``docs/demo/`` so the
gallery is one GitHub-Pages toggle away from being a live site. Drift-lock tests
regenerate both and assert the committed files match, so neither can silently diverge
from the engine, the records, or the renderer.

The seed is chosen for a demonstrative game: all rounds are played, panelists are
eliminated along the way, the impostor lies in both channels, and (in interactive
arms) is caught by the final vote.
"""

from __future__ import annotations

import json
from pathlib import Path

from bsq.engine import run_game
from bsq.models import STANDARD_ARMS, GameConfig
from bsq.record import default_record_path, finalize, serialize
from bsq.render import render_html

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


_ARM_BLURBS: dict[str, str] = {
    "A0_off": "baseline — no verifier is announced and none runs",
    "A1_announced": "the treatment — a verifier is announced and the impostor's menu "
    "carries the [AUDITED]/[NOT AUDITED] tags",
    "A1_implicit": "a verifier is announced but its scope is not (no tags)",
    "A2_silent": "a verifier runs but is never announced (content-only control)",
    "A3_placebo": "a moderator with no verification (authority placebo)",
}

_DEMO_CSS = """
:root {
  --bg: oklch(19% 0.02 260); --surface: oklch(24% 0.02 260);
  --text: oklch(92% 0.01 260); --muted: oklch(70% 0.02 260);
  --accent: oklch(78% 0.14 85);
}
* { box-sizing: border-box; }
body {
  margin: 0 auto; max-width: 720px; padding: 3rem 1.5rem;
  background: var(--bg); color: var(--text);
  font: 16px/1.6 ui-sans-serif, system-ui, sans-serif;
}
h1 { font-size: 1.5rem; letter-spacing: 0.01em; }
p { color: var(--muted); }
ul.replays { list-style: none; padding: 0; display: grid; gap: 0.6rem; }
ul.replays a {
  display: block; background: var(--surface); color: var(--text);
  border-radius: 10px; padding: 0.9rem 1.1rem; text-decoration: none;
}
ul.replays a:hover { outline: 1px solid var(--accent); }
ul.replays .arm { font-weight: 650; }
ul.replays .blurb { display: block; color: var(--muted); font-size: 0.85rem; }
footer { margin-top: 2.5rem; font-size: 0.8rem; color: var(--muted); }
"""


def demo_index_html() -> str:
    """The demo gallery's index page (self-contained, offline, no external references)."""
    items = "".join(
        f'<li><a href="{arm}.html"><span class="arm">{arm}</span>'
        f'<span class="blurb">{blurb}</span></a></li>'
        for arm, blurb in _ARM_BLURBS.items()
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Balloon Squeeze — replay gallery</title>"
        f"<style>{_DEMO_CSS}</style></head><body>"
        "<h1>Balloon Squeeze — replay gallery</h1>"
        "<p>One seeded social-deduction game, replayed under each verifier arm. A hidden "
        "impostor is incentivised to lie about a board of statements while the engine holds "
        "ground truth for every claim; watch where the false claims land relative to the "
        "audited/unaudited boundary, and whether the group catches the impostor. Every "
        "replay is generated deterministically from a committed run record — the same "
        "world, seed 8, under five experimental arms.</p>"
        f'<ul class="replays">{items}</ul>'
        "<footer>Generated offline from committed run records; drift-locked to the engine. "
        "Source and method: the repository README and docs/record-format.md.</footer>"
        "</body></html>\n"
    )


def write_demo_site(dest: Path) -> list[Path]:
    """(Re)generate the committed demo site from the example records; returns the paths."""
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, payload in example_records().items():
        record = json.loads(payload)
        page = dest / filename.replace(".json", ".html")
        page.write_text(render_html(record), encoding="utf-8")
        written.append(page)
    index = dest / "index.html"
    index.write_text(demo_index_html(), encoding="utf-8")
    written.append(index)
    return written
