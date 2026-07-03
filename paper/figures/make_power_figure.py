"""Generate the simulation-based operating-characteristics artifacts (committed).

Replaces the earlier analytic MDE figure: that curve repurposed a two-proportion power
formula that did not match the pooled-gap + cluster-bootstrap estimator actually used.
Everything here is measured by Monte-Carlo on the committed decision machinery itself
(see ``bsq.oc``): detection power uses the full kill rule (so its error modes — e.g.
false-ARTIFACT vetoes at small n — are priced in), and the report carries verdict error
rates and CI coverage per scenario and cluster count.

Outputs (drift-locked by ``tests/test_oc.py``):
- ``oc-report.json`` — the full operating-characteristics table
- ``power-simulated.svg`` — detection power vs planted gap, one curve per cluster count

Deterministic under the committed seed; pure stdlib.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from bsq.oc import detection_power, run_oc_study

#: Committed study parameters (also the drift-lock's regeneration parameters).
STUDY = {
    "n_reps": 120,
    "n_draws": 300,
    "n_games_grid": (10, 14, 30),
    "claims_per_game": (5, 4),
    "icc": 0.15,
    "seed": 0,
}
POWER = {
    "gaps": (0.10, 0.15, 0.20, 0.25, 0.30),
    "n_games_grid": (10, 14, 30),
    "base_rate": 0.4,
    "claims_per_game": (5, 4),
    "icc": 0.15,
    "n_reps": 120,
    "n_draws": 300,
    "seed": 0,
}

_W, _H, _PAD = 640, 400, 56
_COLORS = ("#5b8dd9", "#d9a05b", "#7bc47f")


def build_report() -> dict[str, object]:
    scenarios = run_oc_study(**STUDY)  # type: ignore[arg-type]
    power = detection_power(**POWER)  # type: ignore[arg-type]
    return {
        "simulation_model": {
            "kind": "beta-binomial world model, counts-level, full kill rule applied",
            **{k: list(v) if isinstance(v, tuple) else v for k, v in STUDY.items()},
        },
        "scenarios": [
            {
                "name": s.name,
                "n_games": s.n_games,
                "n_reps": s.n_reps,
                "verdict_rates": dict(s.verdict_rates),
                "ci_coverage": s.ci_coverage,
            }
            for s in scenarios
        ],
        "power_curve": power,
    }


def _x(gap: float, gaps: list[float]) -> float:
    lo, hi = min(gaps), max(gaps)
    return _PAD + (gap - lo) / (hi - lo) * (_W - 2 * _PAD)


def _y(rate: float) -> float:
    return _H - _PAD - rate * (_H - 2 * _PAD)


def build_svg(report: dict[str, object]) -> str:
    points = report["power_curve"]
    assert isinstance(points, list)
    gaps = sorted({p["gap"] for p in points})
    ns = sorted({int(p["n_games"]) for p in points})
    parts = [
        f'<svg viewBox="0 0 {_W} {_H}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="sans-serif" font-size="12">',
        f'<rect width="{_W}" height="{_H}" fill="white"/>',
        f'<line x1="{_PAD}" y1="{_H - _PAD}" x2="{_W - _PAD}" y2="{_H - _PAD}" stroke="#333"/>',
        f'<line x1="{_PAD}" y1="{_PAD}" x2="{_PAD}" y2="{_H - _PAD}" stroke="#333"/>',
        f'<text x="{_W / 2}" y="{_H - 14}" text-anchor="middle">planted tag gap</text>',
        f'<text x="16" y="{_H / 2}" text-anchor="middle" '
        f'transform="rotate(-90 16 {_H / 2})">P(detection verdict)</text>',
        f'<text x="{_W / 2}" y="24" text-anchor="middle" font-size="13">'
        "Detection power of the committed kill rule (simulated, "
        f'ICC={report["simulation_model"]["icc"]})</text>',  # type: ignore[index]
    ]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        parts.append(
            f'<text x="{_PAD - 8}" y="{_y(frac) + 4}" text-anchor="end">{frac:.2f}</text>'
        )
        parts.append(
            f'<line x1="{_PAD}" y1="{_y(frac)}" x2="{_W - _PAD}" y2="{_y(frac)}" '
            'stroke="#ddd" stroke-dasharray="3,3"/>'
        )
    for gap in gaps:
        parts.append(
            f'<text x="{_x(gap, gaps)}" y="{_H - _PAD + 18}" text-anchor="middle">'
            f"{gap:.2f}</text>"
        )
    for i, n in enumerate(ns):
        series = [p for p in points if int(p["n_games"]) == n]
        series.sort(key=lambda p: p["gap"])
        path = " ".join(
            f"{'M' if j == 0 else 'L'}{_x(p['gap'], gaps):.1f},{_y(p['detection_rate']):.1f}"
            for j, p in enumerate(series)
        )
        color = _COLORS[i % len(_COLORS)]
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>')
        for p in series:
            parts.append(
                f'<circle cx="{_x(p["gap"], gaps):.1f}" cy="{_y(p["detection_rate"]):.1f}" '
                f'r="3" fill="{color}"/>'
            )
        parts.append(
            f'<text x="{_W - _PAD + 6}" y="{_y(series[-1]["detection_rate"]) + 4}" '
            f'fill="{color}">n={n}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main(out_dir: Path) -> None:
    report = build_report()
    (out_dir / "oc-report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "power-simulated.svg").write_text(build_svg(report), encoding="utf-8")
    print("wrote oc-report.json and power-simulated.svg")


if __name__ == "__main__":
    main(Path(__file__).parent)
