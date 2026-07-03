"""Operating characteristics: measured error rates, deterministic, drift-locked."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from bsq.oc import SCENARIOS, detection_power, run_oc_study

_FIGDIR = Path(__file__).parent.parent / "paper" / "figures"


def _load_figure_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "make_power_figure", _FIGDIR / "make_power_figure.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_power_figure"] = module
    spec.loader.exec_module(module)
    return module


def test_oc_study_is_deterministic_and_sane() -> None:
    a = run_oc_study(n_reps=20, n_draws=150, n_games_grid=(14,), seed=0)
    b = run_oc_study(n_reps=20, n_draws=150, n_games_grid=(14,), seed=0)
    assert a == b  # pure function of the seed
    by_name = {r.name: r for r in a}
    # a clean null is mostly inert; a strong planted gap is mostly detected
    assert by_name["null"].verdict_rates["inert"] >= 0.7
    assert by_name["gap-strong"].verdict_rates["tag-conditioning"] >= 0.6
    # the artifact scenario is caught by the silent-arm control at a visible rate
    assert by_name["artifact"].verdict_rates["artifact"] >= 0.2
    # CI coverage is in a plausible band (percentile bootstrap at small n undercovers —
    # that is exactly the kind of measured fact the report exists to state)
    assert 0.75 <= by_name["null"].ci_coverage <= 1.0


def test_power_is_monotone_in_gap_and_n() -> None:
    points = detection_power(
        gaps=(0.10, 0.30), n_games_grid=(10, 30), n_reps=30, n_draws=150, seed=0
    )
    rate = {(p["gap"], int(p["n_games"])): p["detection_rate"] for p in points}
    assert rate[(0.30, 30)] >= rate[(0.10, 30)]  # stronger effects are easier
    assert rate[(0.30, 30)] >= rate[(0.30, 10)]  # more clusters help
    assert rate[(0.30, 30)] > 0.8  # a gross effect at n=30 is reliably detected


def test_committed_oc_artifacts_match_regeneration() -> None:
    """Drift lock: the committed report and figure equal a fresh regeneration."""
    module = _load_figure_module()
    report = module.build_report()  # type: ignore[attr-defined]
    committed = json.loads((_FIGDIR / "oc-report.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(report)), "oc-report.json drifted"
    svg = module.build_svg(report)  # type: ignore[attr-defined]
    assert (_FIGDIR / "power-simulated.svg").read_text(encoding="utf-8") == svg


def test_scenario_set_is_the_committed_one() -> None:
    names = [s.name for s in SCENARIOS]
    assert names == ["null", "gap-at-threshold", "gap-strong", "artifact"]
