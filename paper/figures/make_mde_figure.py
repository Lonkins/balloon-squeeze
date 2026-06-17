"""Generate ``mde-vs-games.svg`` from the committed power model — pure stdlib, no plotting deps.

The curve is *required games per arm* versus the *minimum detectable effect* (MDE) on the
within-``A1`` tag gap, computed by :func:`bsq.power.required_games_for_class` on the gradient
stronger-tier operating point (paper §5), for two between-world ICC assumptions. It marks the
achieved 14-world budget and the +0.07 directional hint, making legible why that hint is
unresolvable at this budget and exactly how many *worlds* (not deeper coverage) would resolve
it. Run ``python paper/figures/make_mde_figure.py`` to (re)write the SVG beside this file. The
numbers are locked by ``tests/test_mde_figure.py`` so the figure and the paper cannot drift.
"""

from __future__ import annotations

import pathlib

from bsq.power import ArmClassStats, required_games_for_class

# Gradient stronger-tier operating point (paper §5): audited (checkable) vs unaudited
# (uncheckable) false rates and claims/game; the two channels are the arms of the tag-gap.
_C_RATE, _C_CPG = 0.440, 7.14
_U_RATE, _U_CPG = 0.508, 4.36
_ICCS = (0.0, 0.15)
_HINT_MDE = 0.07
_BUDGET_GAMES = 14
_MDES = [round(0.07 + 0.01 * i, 2) for i in range(24)]  # 0.07 .. 0.30

# SVG geometry.
_W, _H = 660, 420
_L, _R, _T, _B = 78, 28, 30, 56
_PX0, _PX1 = _L, _W - _R
_PY0, _PY1 = _T, _H - _B
_X_MIN, _X_MAX = 0.07, 0.30
_Y_MIN, _Y_MAX = 0.0, 320.0
_COLORS = {0.0: "#1f6feb", 0.15: "#cf222e"}


def required_games(mde: float, icc: float) -> int:
    chk = ArmClassStats(observed_false_rate=_C_RATE, claims_per_game=_C_CPG, icc=icc)
    unc = ArmClassStats(observed_false_rate=_U_RATE, claims_per_game=_U_CPG, icc=icc)
    return int(required_games_for_class(unc, chk, mde=mde))


def _px(mde: float) -> float:
    return _PX0 + (mde - _X_MIN) / (_X_MAX - _X_MIN) * (_PX1 - _PX0)


def _py(games: float) -> float:
    return _PY1 - (games - _Y_MIN) / (_Y_MAX - _Y_MIN) * (_PY1 - _PY0)


def _curve(icc: float) -> str:
    pts = " ".join(f"{_px(m):.1f},{_py(min(required_games(m, icc), _Y_MAX)):.1f}" for m in _MDES)
    return f'<polyline points="{pts}" fill="none" stroke="{_COLORS[icc]}" stroke-width="2.5"/>'


def render_svg() -> str:
    parts: list[str] = [
        f'<svg viewBox="0 0 {_W} {_H}" xmlns="http://www.w3.org/2000/svg" '
        'font-family="system-ui, sans-serif" font-size="13">',
        f'<rect x="0" y="0" width="{_W}" height="{_H}" fill="white"/>',
        # axes
        f'<line x1="{_L}" y1="{_PY1}" x2="{_PX1}" y2="{_PY1}" stroke="#444"/>',
        f'<line x1="{_L}" y1="{_PY0}" x2="{_L}" y2="{_PY1}" stroke="#444"/>',
    ]
    # y ticks
    for g in (0, 50, 100, 150, 200, 250, 300):
        y = _py(g)
        parts.append(f'<line x1="{_L - 5}" y1="{y:.1f}" x2="{_L}" y2="{y:.1f}" stroke="#444"/>')
        parts.append(
            f'<text x="{_L - 9}" y="{y + 4:.1f}" text-anchor="end" fill="#444">{g}</text>'
        )
        parts.append(
            f'<line x1="{_L}" y1="{y:.1f}" x2="{_PX1}" y2="{y:.1f}" stroke="#eee"/>'
        )
    # x ticks
    for m in (0.07, 0.10, 0.15, 0.20, 0.25, 0.30):
        x = _px(m)
        parts.append(f'<line x1="{x:.1f}" y1="{_PY1}" x2="{x:.1f}" y2="{_PY1 + 5}" stroke="#444"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{_PY1 + 20}" text-anchor="middle" fill="#444">{m:.2f}</text>'
        )
    # achieved-budget line
    yb = _py(_BUDGET_GAMES)
    parts.append(
        f'<line x1="{_L}" y1="{yb:.1f}" x2="{_PX1}" y2="{yb:.1f}" '
        'stroke="#57606a" stroke-width="1.5" stroke-dasharray="5 4"/>'
    )
    parts.append(
        f'<text x="{_PX1 - 4}" y="{yb - 6:.1f}" text-anchor="end" fill="#57606a">'
        "achieved budget: 14 worlds/arm</text>"
    )
    # curves
    for icc in _ICCS:
        parts.append(_curve(icc))
    # hint marker
    xh = _px(_HINT_MDE)
    nh = required_games(_HINT_MDE, 0.15)
    parts.append(f'<circle cx="{xh:.1f}" cy="{_py(nh):.1f}" r="4" fill="#cf222e"/>')
    parts.append(
        f'<text x="{xh + 8:.1f}" y="{_py(nh) + 4:.1f}" fill="#cf222e">'
        f"+0.07 hint ≈ {nh} worlds/arm</text>"
    )
    # legend + titles
    parts.append(f'<rect x="{_PX1 - 150}" y="{_PY0 + 6}" width="14" height="3" fill="#1f6feb"/>')
    parts.append(f'<text x="{_PX1 - 132}" y="{_PY0 + 13}" fill="#444">ICC = 0</text>')
    parts.append(f'<rect x="{_PX1 - 150}" y="{_PY0 + 24}" width="14" height="3" fill="#cf222e"/>')
    parts.append(f'<text x="{_PX1 - 132}" y="{_PY0 + 31}" fill="#444">ICC = 0.15</text>')
    parts.append(
        f'<text x="{(_PX0 + _PX1) / 2:.0f}" y="{_H - 14}" text-anchor="middle" fill="#222">'
        "minimum detectable tag gap (MDE)</text>"
    )
    parts.append(
        f'<text x="18" y="{(_PY0 + _PY1) / 2:.0f}" text-anchor="middle" fill="#222" '
        f'transform="rotate(-90 18 {(_PY0 + _PY1) / 2:.0f})">required worlds per arm</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    out = pathlib.Path(__file__).with_name("mde-vs-games.svg")
    out.write_text(render_svg() + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for icc in _ICCS:
        print(f"  ICC={icc}: MDE 0.07 -> {required_games(0.07, icc)} worlds/arm; "
              f"0.20 -> {required_games(0.20, icc)}")


if __name__ == "__main__":
    main()
