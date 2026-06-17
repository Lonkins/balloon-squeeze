"""The MDE/power figure is locked to the committed power model — prose and figure can't drift.

This guards against the retracted hand-wave that the +0.07 directional hint needed "~50"
worlds to confirm; the committed estimator says it needs hundreds.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_FIG = Path(__file__).resolve().parent.parent / "paper" / "figures" / "make_mde_figure.py"
_spec = importlib.util.spec_from_file_location("make_mde_figure", _FIG)
assert _spec is not None and _spec.loader is not None
mde_fig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mde_fig)


def test_hint_needs_hundreds_of_worlds_not_fifty() -> None:
    # The +0.07 hint is unresolvable at the 14-world budget: hundreds of worlds/arm per the
    # committed power model, not the ~50 a hand-wave would suggest.
    for icc in (0.0, 0.15):
        n = mde_fig.required_games(0.07, icc)
        assert 150 <= n <= 340, f"MDE=0.07 icc={icc}: {n} worlds/arm out of expected band"
        assert n > 100  # decisively more than the retracted "~50"


def test_gross_effect_is_what_the_budget_resolves() -> None:
    # The achieved ~14-world budget resolves only a gross effect (MDE ~0.20), as claimed.
    assert 20 <= mde_fig.required_games(0.20, 0.15) <= 45


def test_required_worlds_fall_monotonically_with_mde() -> None:
    seq = [mde_fig.required_games(m, 0.15) for m in (0.07, 0.10, 0.15, 0.20, 0.30)]
    assert seq == sorted(seq, reverse=True)


def test_svg_is_well_formed_and_cites_the_hint_number() -> None:
    svg = mde_fig.render_svg()
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "required worlds per arm" in svg
    assert f"{mde_fig.required_games(0.07, 0.15)} worlds/arm" in svg  # the hint annotation
