"""Recomputable analysis: run-record files -> the full statistics report.

This module deliberately owns *no statistics*. It adapts each record file into the exact
per-game count structure the in-process path consumes (:class:`bsq.probe.GameRecord`),
groups by ``(arm, interactive)``, accounts for every input file, and delegates every
statistic — pooled rates, the seeded cluster-bootstrap tag gap, floor health, the
pre-committed kill-rule verdict — to the unchanged :mod:`bsq.probe` functions. Relocating
*where* the numbers are computed, never *what* they compute, is what makes record-derived
results exactly equivalent to the in-process ones (and keeps any future methodological
change a ``probe``/pre-registration matter).

Guarantees: deterministic under (inputs, seed, draws); no pooling across arm or
deliberation mode; every file reported as used or excluded-with-reason; each record's
folded counts are cross-checked against its own ``scores.main_channel`` block, so a
corrupted file is excluded rather than silently contaminating the analysis.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bsq.models import PropositionClass
from bsq.probe import (
    FloorStats,
    GameRecord,
    GapCI,
    ProbeReport,
    arm_floor,
    evaluate,
    floor_is_healthy,
    gap_ci,
)
from bsq.record import GAME_RECORD_VERSION, serialize

_C = PropositionClass.CHECKABLE
_U = PropositionClass.UNCHECKABLE

#: File-accounting statuses. Every input file receives exactly one.
USED = "used"
NOT_A_RECORD = "not-a-record"
UNSUPPORTED_VERSION = "unsupported-version"
CORRUPT = "corrupt"
DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class FileAccount:
    path: str
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class GroupStats:
    """One (arm, interactive) group's folded counts and delegated statistics."""

    arm: str
    interactive: bool
    n_games: int
    main: Mapping[str, tuple[int, int]]  # class value -> (n_false, n_asserted)
    placebo: Mapping[str, tuple[int, int]]
    floor: FloorStats
    healthy: bool
    tag_gap: GapCI
    degenerate: bool  # < 2 games: the clustered interval is not meaningfully estimated


@dataclass(frozen=True, slots=True)
class Contrast:
    baseline: str
    treatment: str
    interactive: bool
    delta_c: float


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    analysis_seed: int
    n_draws: int
    files: tuple[FileAccount, ...]
    groups: Mapping[tuple[str, bool], GroupStats]
    contrasts: tuple[Contrast, ...]
    verdicts: tuple[tuple[bool, ProbeReport], ...]  # (interactive, kill-rule report)
    verdict_missing: tuple[str, ...]  # modes with A1 present but the rule's arms missing

    @property
    def verdict(self) -> ProbeReport | None:
        """The kill-rule report when exactly one mode qualifies (the common case)."""
        return self.verdicts[0][1] if len(self.verdicts) == 1 else None

    @property
    def n_used(self) -> int:
        return sum(1 for f in self.files if f.status == USED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_seed": self.analysis_seed,
            "n_draws": self.n_draws,
            "files": [
                {"path": f.path, "status": f.status, "reason": f.reason} for f in self.files
            ],
            "groups": [_group_dict(g) for _, g in sorted(self.groups.items())],
            "contrasts": [
                {
                    "baseline": c.baseline,
                    "treatment": c.treatment,
                    "interactive": c.interactive,
                    "delta_c": _num(c.delta_c),
                }
                for c in self.contrasts
            ],
            "verdicts": [
                {
                    "interactive": interactive,
                    "verdict": str(probe_report.verdict),
                    "gates": {
                        "tag_gap": _gap_dict(probe_report.tag_gap),
                        "placebo_gap": _gap_dict(probe_report.placebo_gap),
                        "silent_gap": _gap_dict(probe_report.silent_gap),
                        "delta_c": _num(probe_report.delta_c),
                        "floor": _floor_dict(probe_report.floor),
                    },
                }
                for interactive, probe_report in self.verdicts
            ],
            "verdict_missing": list(self.verdict_missing),
        }

    def to_json(self) -> str:
        return serialize(self.to_dict())

    def render_text(self) -> str:
        lines = [
            f"analysis seed={self.analysis_seed} draws={self.n_draws} "
            f"files used={self.n_used}/{len(self.files)}"
        ]
        for (arm, interactive), group in sorted(self.groups.items()):
            mode = "interactive" if interactive else "monologue"
            gap = group.tag_gap
            degenerate = "  [degenerate: <2 games]" if group.degenerate else ""
            lines.append(f"\n{arm} ({mode}) — {group.n_games} game(s){degenerate}")
            lines.append(
                f"  main      C {group.main['checkable'][0]}/{group.main['checkable'][1]}"
                f"  U {group.main['uncheckable'][0]}/{group.main['uncheckable'][1]}"
            )
            lines.append(
                f"  placebo   C {group.placebo['checkable'][0]}/{group.placebo['checkable'][1]}"
                f"  U {group.placebo['uncheckable'][0]}/{group.placebo['uncheckable'][1]}"
            )
            lines.append(
                f"  floor     C/game={group.floor.c_claims_per_game:.2f} "
                f"U/game={group.floor.u_claims_per_game:.2f} healthy={group.healthy}"
            )
            lines.append(
                f"  tag gap   {_fmt(gap.point)} [{_fmt(gap.lo)}, {_fmt(gap.hi)}]"
                f"  (C={_fmt(gap.c_rate)} n={gap.c_claims}; U={_fmt(gap.u_rate)} n={gap.u_claims})"
            )
        for c in self.contrasts:
            mode = "interactive" if c.interactive else "monologue"
            lines.append(
                f"\ndelta_C ({c.baseline} - {c.treatment}, {mode}) = {_fmt(c.delta_c)}"
            )
        for interactive, probe_report in self.verdicts:
            mode = "interactive" if interactive else "monologue"
            lines.append(f"\nkill-rule verdict ({mode}): {probe_report.verdict}")
        for missing in self.verdict_missing:
            lines.append(f"\nverdict unavailable: missing {missing}")
        lines.append("\nfiles:")
        for f in self.files:
            reason = f" — {f.reason}" if f.reason else ""
            lines.append(f"  [{f.status}] {f.path}{reason}")
        return "\n".join(lines) + "\n"


def analyze_paths(
    paths: Sequence[Path], *, seed: int = 0, n_draws: int = 2000
) -> AnalysisReport:
    """Analyze record files/directories into the full statistics report."""
    accounts: list[FileAccount] = []
    seen: dict[tuple[str, int, bool], str] = {}
    grouped: dict[tuple[str, bool], list[GameRecord]] = {}

    for file in _expand(paths):
        account, identity, game_record = _ingest(file)
        if account.status == USED and identity is not None and game_record is not None:
            if identity in seen:
                account = FileAccount(
                    path=account.path,
                    status=DUPLICATE,
                    reason=f"same (arm, seed, interactive) as {seen[identity]}",
                )
            else:
                seen[identity] = account.path
                grouped.setdefault((identity[0], identity[2]), []).append(game_record)
        accounts.append(account)

    groups = {
        key: _group_stats(key, records, seed=seed, n_draws=n_draws)
        for key, records in grouped.items()
    }
    contrasts = _contrasts(grouped)
    verdicts, missing = _verdicts(grouped, seed=seed, n_draws=n_draws)
    return AnalysisReport(
        analysis_seed=seed,
        n_draws=n_draws,
        files=tuple(accounts),
        groups=groups,
        contrasts=tuple(contrasts),
        verdicts=tuple(verdicts),
        verdict_missing=tuple(missing),
    )


def _expand(paths: Sequence[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.glob("*.json"))
        else:
            yield path


def _ingest(
    file: Path,
) -> tuple[FileAccount, tuple[str, int, bool] | None, GameRecord | None]:
    """Load one file -> (account, identity, adapted counts); never raises on bad input."""
    path = str(file)
    if not file.is_file():
        return FileAccount(path, NOT_A_RECORD, "no such file"), None, None
    try:
        parsed: Any = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return FileAccount(path, NOT_A_RECORD, f"unreadable: {exc}"), None, None
    if not isinstance(parsed, dict) or "record_version" not in parsed:
        return FileAccount(path, NOT_A_RECORD, "no record_version field"), None, None
    if parsed.get("record_version") != GAME_RECORD_VERSION:
        return (
            FileAccount(
                path,
                UNSUPPORTED_VERSION,
                f"record_version {parsed.get('record_version')!r}; supported: "
                f"{GAME_RECORD_VERSION}",
            ),
            None,
            None,
        )
    try:
        game = parsed["game"]
        setup = game["setup"]
        identity = (str(setup["arm"]), int(setup["seed"]), bool(setup["interactive"]))
        game_record = _fold(game)
        mismatch = _integrity_mismatch(game_record, game["scores"]["main_channel"])
    except (KeyError, TypeError, ValueError) as exc:
        return FileAccount(path, NOT_A_RECORD, f"malformed record: {exc}"), None, None
    if mismatch:
        return FileAccount(path, CORRUPT, mismatch), None, None
    return FileAccount(path, USED), identity, game_record


def _fold(game: Mapping[str, Any]) -> GameRecord:
    """Fold the impostor's claims rows into per-class (false, total) counts."""
    impostor = next(p["id"] for p in game["participants"] if p["role"] == "impostor")
    main = {_C: [0, 0], _U: [0, 0]}
    placebo = {_C: [0, 0], _U: [0, 0]}
    for round_ in game["rounds"]:
        for claim in round_["claims"]:
            if claim["speaker_id"] != impostor:
                continue
            cls = PropositionClass(claim["class"])
            cell = (placebo if claim["is_placebo"] else main)[cls]
            cell[1] += 1
            cell[0] += int(claim["is_false"])
    return GameRecord(
        main={cls: (v[0], v[1]) for cls, v in main.items()},
        placebo={cls: (v[0], v[1]) for cls, v in placebo.items()},
    )


def _integrity_mismatch(
    game_record: GameRecord, main_channel: Mapping[str, Any]
) -> str | None:
    """The record self-describes its main-channel totals; a recount must agree."""
    for cls, key in ((_C, "checkable"), (_U, "uncheckable")):
        false, total = game_record.main[cls]
        declared = main_channel[key]
        if declared["n_false"] != false or declared["n_asserted"] != total:
            return (
                f"scores.main_channel.{key} declares "
                f"{declared['n_false']}/{declared['n_asserted']} but claims rows fold to "
                f"{false}/{total}"
            )
    return None


def _group_stats(
    key: tuple[str, bool], records: list[GameRecord], *, seed: int, n_draws: int
) -> GroupStats:
    arm, interactive = key
    floor = arm_floor(records)
    return GroupStats(
        arm=arm,
        interactive=interactive,
        n_games=len(records),
        main=_pool(records, placebo=False),
        placebo=_pool(records, placebo=True),
        floor=floor,
        healthy=floor_is_healthy(floor),
        tag_gap=gap_ci(records, placebo=False, n_draws=n_draws, seed=seed),
        degenerate=len(records) < 2,
    )


def _pool(records: Sequence[GameRecord], *, placebo: bool) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for cls in (_C, _U):
        false = total = 0
        for r in records:
            cell = (r.placebo if placebo else r.main)[cls]
            false += cell[0]
            total += cell[1]
        out[cls.value] = (false, total)
    return out


def _checkable_rate(records: Sequence[GameRecord]) -> float:
    false, total = 0, 0
    for r in records:
        false += r.main[_C][0]
        total += r.main[_C][1]
    return false / total if total else math.nan


def _contrasts(grouped: Mapping[tuple[str, bool], list[GameRecord]]) -> list[Contrast]:
    out: list[Contrast] = []
    for interactive in (False, True):
        a0 = grouped.get(("A0_off", interactive))
        a1 = grouped.get(("A1_announced", interactive))
        if a0 and a1:
            out.append(
                Contrast(
                    baseline="A0_off",
                    treatment="A1_announced",
                    interactive=interactive,
                    delta_c=arm_floor(a0).c_rate - _checkable_rate(a1),
                )
            )
    return out


def _verdicts(
    grouped: Mapping[tuple[str, bool], list[GameRecord]], *, seed: int, n_draws: int
) -> tuple[list[tuple[bool, ProbeReport]], list[str]]:
    verdicts: list[tuple[bool, ProbeReport]] = []
    missing: list[str] = []
    for interactive in (False, True):
        mode = "interactive" if interactive else "monologue"
        present = {
            arm: grouped.get((arm, interactive)) for arm in ("A0_off", "A1_announced", "A2_silent")
        }
        if not any(present.values()):
            continue
        absent = [arm for arm, records in present.items() if not records]
        if absent:
            if present["A1_announced"]:
                missing.append(f"{', '.join(absent)} ({mode})")
            continue
        a0, a1, a2 = present["A0_off"], present["A1_announced"], present["A2_silent"]
        assert a0 and a1 and a2  # narrowed by the absent-check above
        verdicts.append((interactive, evaluate(a0, a1, a2, n_draws=n_draws, seed=seed)))
    return verdicts, missing


def _num(value: float) -> float | None:
    return None if math.isnan(value) else value


def _fmt(value: float) -> str:
    return "—" if math.isnan(value) else f"{value:+.3f}"


def _gap_dict(gap: GapCI) -> dict[str, Any]:
    return {
        "point": _num(gap.point),
        "lo": _num(gap.lo),
        "hi": _num(gap.hi),
        "c_rate": _num(gap.c_rate),
        "u_rate": _num(gap.u_rate),
        "c_claims": gap.c_claims,
        "u_claims": gap.u_claims,
    }


def _floor_dict(floor: FloorStats) -> dict[str, Any]:
    return {
        "c_rate": _num(floor.c_rate),
        "u_rate": _num(floor.u_rate),
        "c_claims_per_game": floor.c_claims_per_game,
        "u_claims_per_game": floor.u_claims_per_game,
        "healthy": floor_is_healthy(floor),
    }


def _group_dict(group: GroupStats) -> dict[str, Any]:
    def cells(pool: Mapping[str, tuple[int, int]]) -> dict[str, Any]:
        return {
            cls: {
                "n_false": false,
                "n_asserted": total,
                "rate": (false / total) if total else None,
            }
            for cls, (false, total) in sorted(pool.items())
        }

    return {
        "arm": group.arm,
        "interactive": group.interactive,
        "n_games": group.n_games,
        "degenerate": group.degenerate,
        "main": cells(group.main),
        "placebo": cells(group.placebo),
        "floor": _floor_dict(group.floor),
        "tag_gap": _gap_dict(group.tag_gap),
    }
