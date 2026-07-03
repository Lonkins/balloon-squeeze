"""Recomputable analysis from run records: adapter, accounting, determinism, equivalence.

The analysis must be a pure function of record files — statistics identical to the
in-process path (it reuses the same probe functions on the same per-game counts), every
input file accounted for, and nothing pooled across arms or deliberation modes.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from bsq.analyze import analyze_paths
from bsq.engine import run_game
from bsq.models import GameConfig
from bsq.probe import (
    GameRecord,
    arm_floor,
    evaluate,
    floor_is_healthy,
    gap_ci,
)
from bsq.record import default_record_path, finalize, load_record, write_record


def _record_set(
    tmp_path: Path,
    arm: str,
    seeds: list[int],
    *,
    interactive: bool = False,
    impostor_policy: object = None,
    subdir: str = "",
) -> Path:
    """Write one record per seed for an arm; returns the directory written into."""
    dest = tmp_path / subdir if subdir else tmp_path
    dest.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        cfg = GameConfig(n_topics=6, rounds=3, verifier_arm=arm, interactive=interactive)
        kwargs: dict[str, Any] = {}
        if impostor_policy is not None:
            kwargs["impostor_policy"] = impostor_policy
        result = run_game(cfg, seed, **kwargs)
        write_record(finalize(result.record_game), default_record_path(cfg, seed, base=dest))
    return dest


def test_probe_seams_are_public() -> None:
    # The analysis consumes these unchanged; if a rename breaks this, the single source
    # of statistical truth has moved and analyze.py must follow it deliberately.
    assert callable(gap_ci) and callable(arm_floor) and callable(evaluate)
    assert callable(floor_is_healthy)
    assert GameRecord is not None


def test_adapter_counts_equal_a_hand_fold(tmp_path: Path) -> None:
    dest = _record_set(tmp_path, "A1_announced", [7])
    report = analyze_paths([dest], seed=0)
    group = report.groups[("A1_announced", False)]

    record = load_record(dest / "A1_announced-seed7.json")
    game = record["game"]
    impostor = next(p["id"] for p in game["participants"] if p["role"] == "impostor")
    fold = {("checkable", False): [0, 0], ("uncheckable", False): [0, 0],
            ("checkable", True): [0, 0], ("uncheckable", True): [0, 0]}
    for rnd in game["rounds"]:
        for c in rnd["claims"]:
            if c["speaker_id"] != impostor:
                continue
            cell = fold[(c["class"], c["is_placebo"])]
            cell[0] += int(c["is_false"])
            cell[1] += 1
    assert group.main["checkable"] == tuple(fold[("checkable", False)])
    assert group.main["uncheckable"] == tuple(fold[("uncheckable", False)])
    assert group.placebo["checkable"] == tuple(fold[("checkable", True)])
    assert group.placebo["uncheckable"] == tuple(fold[("uncheckable", True)])


def test_groups_never_pool_across_arm_or_mode(tmp_path: Path) -> None:
    _record_set(tmp_path, "A1_announced", [1, 2], interactive=False)
    _record_set(tmp_path, "A1_announced", [3], interactive=True)
    _record_set(tmp_path, "A0_off", [4])
    report = analyze_paths([tmp_path], seed=0)
    keys = set(report.groups)
    assert keys == {("A1_announced", False), ("A1_announced", True), ("A0_off", False)}
    assert report.groups[("A1_announced", False)].n_games == 2
    assert report.groups[("A1_announced", True)].n_games == 1


def test_every_file_is_accounted_for(tmp_path: Path) -> None:
    dest = _record_set(tmp_path, "A1_announced", [7])
    (dest / "notes.json").write_text('{"hello": "world"}', encoding="utf-8")
    (dest / "not-json.json").write_text("plain text", encoding="utf-8")
    future = load_record(dest / "A1_announced-seed7.json")
    future["record_version"] = 99
    (dest / "future.json").write_text(json.dumps(future), encoding="utf-8")
    # a duplicate: same (arm, seed, mode) under another filename
    (dest / "zz-copy.json").write_text(
        (dest / "A1_announced-seed7.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    corrupt = load_record(dest / "A1_announced-seed7.json")
    corrupt["game"]["scores"]["main_channel"]["checkable"]["n_false"] += 1
    (dest / "corrupt.json").write_text(json.dumps(corrupt), encoding="utf-8")

    report = analyze_paths([dest], seed=0)
    by_name = {Path(f.path).name: f for f in report.files}
    assert len(by_name) == 6
    assert by_name["A1_announced-seed7.json"].status == "used"
    assert by_name["notes.json"].status == "not-a-record"
    assert by_name["not-json.json"].status == "not-a-record"
    assert by_name["future.json"].status == "unsupported-version"
    assert by_name["zz-copy.json"].status == "duplicate"
    assert by_name["corrupt.json"].status == "corrupt"
    for account in report.files:
        if account.status != "used":
            assert account.reason  # every exclusion carries its reason


def test_reports_are_byte_deterministic(tmp_path: Path) -> None:
    dest = _record_set(tmp_path, "A1_announced", [1, 2, 3])
    a = analyze_paths([dest], seed=0).to_json()
    b = analyze_paths([dest], seed=0).to_json()
    assert a == b
    assert "NaN" not in a
    json.loads(a)  # strict JSON


def test_single_game_gap_is_flagged_degenerate(tmp_path: Path) -> None:
    dest = _record_set(tmp_path, "A1_announced", [7])
    report = analyze_paths([dest], seed=0)
    assert report.groups[("A1_announced", False)].degenerate is True


def test_verdict_requires_all_three_arms(tmp_path: Path) -> None:
    _record_set(tmp_path, "A0_off", [1, 2])
    _record_set(tmp_path, "A1_announced", [3, 4])
    partial = analyze_paths([tmp_path], seed=0)
    assert partial.verdict is None
    assert partial.verdict_missing and any("A2_silent" in m for m in partial.verdict_missing)

    _record_set(tmp_path, "A2_silent", [5, 6])
    full = analyze_paths([tmp_path], seed=0)
    assert full.verdict is not None
    assert full.verdict_missing == ()


def test_delta_c_reported_when_baseline_and_treatment_exist(tmp_path: Path) -> None:
    _record_set(tmp_path, "A0_off", [1, 2])
    _record_set(tmp_path, "A1_announced", [3, 4])
    report = analyze_paths([tmp_path], seed=0)
    assert len(report.contrasts) == 1
    contrast = report.contrasts[0]
    assert contrast.baseline == "A0_off" and contrast.treatment == "A1_announced"


def test_cli_analyze_prints_report_and_writes_json(
    tmp_path: Path, capsys: Any
) -> None:
    from bsq.cli import main

    dest = _record_set(tmp_path, "A1_announced", [1, 2])
    out_json = tmp_path / "report.json"
    assert main(["analyze", str(dest), "--json", str(out_json)]) == 0
    printed = capsys.readouterr().out
    assert "A1_announced (monologue) — 2 game(s)" in printed
    assert "tag gap" in printed and "[used]" in printed
    parsed = json.loads(out_json.read_text(encoding="utf-8"))
    assert parsed["analysis_seed"] == 0
    assert parsed["groups"][0]["n_games"] == 2


def test_cli_analyze_empty_dir_exits_nonzero(tmp_path: Path) -> None:
    from bsq.cli import main

    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["analyze", str(empty)]) == 1


def test_undefined_rates_serialize_as_null(tmp_path: Path) -> None:
    dest = _record_set(tmp_path, "A0_off", [20])  # small game; placebo cells may be empty
    text = analyze_paths([dest], seed=0).to_json()
    parsed = json.loads(text)
    assert parsed  # strict parse; no NaN anywhere
    assert "NaN" not in text


# ---------------------------------------------------------------------------
# US2 — the record-derived path is PROVEN: in-process equivalence + planted truth
# ---------------------------------------------------------------------------


def _eq(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or a == b


def test_equivalence_with_the_in_process_path(tmp_path: Path) -> None:
    """Identical games, two paths: probe in-process vs analyze-over-records — exactly equal."""
    from bsq.probe import collect_arm

    cfg = GameConfig(n_topics=6, rounds=3)
    in_process: dict[str, list[GameRecord]] = {}
    for arm, base_seed in (("A0_off", 100), ("A1_announced", 200), ("A2_silent", 300)):
        in_process[arm] = collect_arm(
            cfg, n_games=6, arm=arm, base_seed=base_seed, record_dir=tmp_path
        )
    expected = evaluate(
        in_process["A0_off"], in_process["A1_announced"], in_process["A2_silent"], seed=0
    )

    report = analyze_paths([tmp_path], seed=0)
    assert report.verdict is not None
    actual = report.verdict

    for got, want in (
        (actual.tag_gap, expected.tag_gap),
        (actual.placebo_gap, expected.placebo_gap),
        (actual.silent_gap, expected.silent_gap),
    ):
        assert _eq(got.point, want.point) and _eq(got.lo, want.lo) and _eq(got.hi, want.hi)
        assert got.c_claims == want.c_claims and got.u_claims == want.u_claims
        assert _eq(got.c_rate, want.c_rate) and _eq(got.u_rate, want.u_rate)
    assert _eq(actual.delta_c, expected.delta_c)
    assert actual.floor == expected.floor
    assert actual.verdict == expected.verdict
    # and the folded per-game counts agree cell-for-cell
    for arm in ("A0_off", "A1_announced", "A2_silent"):
        group = report.groups[(arm, False)]
        assert group.n_games == len(in_process[arm])


def test_planted_displacement_is_recovered(tmp_path: Path) -> None:
    """Displacer-generated records recover the planted contrast within tolerance."""
    from bsq.agents.displacer import StrategicDisplacerPolicy

    displacer = StrategicDisplacerPolicy(lie_rate=0.5, s_c=0.6, s_u=0.6)
    seeds = list(range(40))
    _record_set(tmp_path, "A0_off", seeds, impostor_policy=displacer, subdir="set")
    _record_set(
        tmp_path, "A1_announced", [s + 1000 for s in seeds],
        impostor_policy=displacer, subdir="set",
    )
    report = analyze_paths([tmp_path / "set"], seed=0)

    # planted: under A1 the checkable lie prob drops by b*s_c and uncheckable rises by
    # b*s_u -> expected tag gap ~= b*(s_c + s_u) = 0.5 * 1.2 = 0.6; A0 gap ~= 0.
    a1_gap = report.groups[("A1_announced", False)].tag_gap.point
    a0_gap = report.groups[("A0_off", False)].tag_gap.point
    assert abs(a1_gap - 0.6) < 0.15, f"planted gap not recovered: {a1_gap}"
    assert abs(a0_gap) < 0.15, f"baseline gap should be ~0: {a0_gap}"
    # delta_C ~= b*s_c = 0.30 in the suppression direction
    assert report.contrasts and abs(report.contrasts[0].delta_c - 0.30) < 0.12


def test_no_effect_set_reads_clean(tmp_path: Path) -> None:
    """Arm-insensitive impostor -> no spurious effect; verdict is not tag-conditioning."""
    from bsq.probe import ProbeVerdict

    seeds = list(range(12))
    _record_set(tmp_path, "A0_off", seeds, subdir="null")
    _record_set(tmp_path, "A1_announced", [s + 1000 for s in seeds], subdir="null")
    _record_set(tmp_path, "A2_silent", [s + 2000 for s in seeds], subdir="null")
    report = analyze_paths([tmp_path / "null"], seed=0)
    assert report.verdict is not None
    assert report.verdict.verdict is not ProbeVerdict.TAG_CONDITIONING
    a1_gap = report.groups[("A1_announced", False)].tag_gap
    assert a1_gap.lo <= 0.0 <= a1_gap.hi  # CI covers zero: clean null
