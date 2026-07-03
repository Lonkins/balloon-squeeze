"""Run records: the complete, versioned account of one game (contract v1).

Every run assembles a record sufficient to reconstruct the game without re-execution:
setup, the statement board with engine-held truth and audit tags, each participant's
instructions, every utterance in order, every claim joined to its ground-truth verdict,
oracle verdicts, votes/eliminations, and the final per-class scores.

The envelope is ``{"record_version": 1, "game": …, "meta": …}``. The ``game`` payload is
the subject of the byte-identity contract — canonical serialization (sorted keys,
two-space indent, no wall-clock values) makes identical (config, seed, mode) runs
serialize identically on the offline path. ``meta`` carries run context that may
legitimately vary (provider, a *generic* model label, truncation counts) and is exempt.

Undefined rates serialize as ``null`` (never ``NaN``) so records stay strict JSON.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bsq import __version__
from bsq.models import (
    Agent,
    Claim,
    GameConfig,
    Proposition,
    PropositionClass,
    RoundVotes,
    Utterance,
    VerifierArm,
)
from bsq.scoring import ClassCount, SeatScore
from bsq.verifier import Verification, announcement_for
from bsq.views import AUDITED, NOT_AUDITED

GAME_RECORD_VERSION = 1

#: Utterance failure markers (never silently absent).
EXTRACTION_FAILED = "extraction_failed"


def build_game_payload(
    *,
    cfg: GameConfig,
    seed: int,
    arm: VerifierArm,
    ledger: Sequence[Proposition],
    participants: Sequence[Agent],
    instructions: Mapping[str, str],
    utterances: Sequence[Utterance],
    claims_per_utterance: Mapping[int, int],
    scored_claims: Sequence[Claim],
    verifications: Sequence[Verification],
    rounds_votes: Sequence[RoundVotes],
    ended_early: bool,
    impostor_seat: SeatScore,
) -> dict[str, Any]:
    """Assemble the deterministic ``game`` payload from engine-collected state.

    ``claims_per_utterance`` maps an utterance's index in ``utterances`` to the number
    of claims extracted from it — a spoken utterance that yielded zero claims is marked
    ``extraction_failed`` rather than silently absent.
    """
    by_id = {p.id: p for p in ledger}
    show_tags = arm.announces_scope

    board = [
        {
            "id": p.id,
            "surface_form": p.surface_form,
            "class": p.class_.value,
            "truth_value": p.truth_value,
            "audit_tag": (
                (AUDITED if p.class_ is PropositionClass.CHECKABLE else NOT_AUDITED)
                if show_tags
                else None
            ),
            "topic_id": p.topic_id,
            "is_placebo_irrelevant": p.is_placebo_irrelevant,
        }
        for p in ledger
    ]

    participant_entries = [
        {
            "id": a.id,
            "name": a.persona.name if a.persona else a.id,
            "role": a.role.value,
            "instruction": instructions.get(a.id, ""),
        }
        for a in participants
    ]

    n_rounds_played = max((u.round_idx for u in utterances), default=-1) + 1
    votes_by_round = {rv.round_idx: rv for rv in rounds_votes}
    rounds: list[dict[str, Any]] = []
    for round_idx in range(n_rounds_played):
        round_utterances = [
            {
                "speaker_id": u.speaker_id,
                "text": u.text,
                "n_claims": claims_per_utterance.get(i, 0),
                "failure": (
                    EXTRACTION_FAILED
                    if (u.text and claims_per_utterance.get(i, 0) == 0)
                    else None
                ),
            }
            for i, u in enumerate(utterances)
            if u.round_idx == round_idx
        ]
        round_claims = [
            _claim_entry(c, by_id[c.proposition_id])
            for c in scored_claims
            if c.round_idx == round_idx
        ]
        round_verifications = [
            {
                "proposition_id": v.proposition_id,
                "asserted_value": v.asserted_value,
                "truth_value": v.truth_value,
                "correct": v.correct,
            }
            for v in verifications
            if v.round_idx == round_idx
        ]
        vote_block = None
        if round_idx in votes_by_round:
            rv = votes_by_round[round_idx]
            vote_block = {
                "votes": [{"voter_id": v.voter_id, "target_id": v.target_id} for v in rv.votes],
                "eliminated": rv.eliminated,
            }
        rounds.append(
            {
                "round_idx": round_idx,
                "utterances": round_utterances,
                "claims": round_claims,
                "verifications": round_verifications,
                "vote": vote_block,
            }
        )

    return {
        "setup": {
            "seed": seed,
            "arm": arm.name,
            "interactive": cfg.interactive,
            "n_agents": cfg.n_agents,
            "rounds": cfg.rounds,
            "n_topics": cfg.n_topics,
            "placebo_fraction": cfg.placebo_fraction,
            "checkability_fraction": cfg.checkability_fraction,
            "announcement": announcement_for(arm),
        },
        "board": board,
        "participants": participant_entries,
        "rounds": rounds,
        "ended_early": ended_early,
        "scores": _scores(impostor_seat),
    }


def _claim_entry(claim: Claim, prop: Proposition) -> dict[str, Any]:
    return {
        "speaker_id": claim.speaker_id,
        "proposition_id": claim.proposition_id,
        "asserted_value": claim.asserted_value,
        "truth_value": prop.truth_value,
        "is_false": claim.asserted_value != prop.truth_value,
        "class": prop.class_.value,
        "audited": prop.class_ is PropositionClass.CHECKABLE,
        "is_placebo": prop.is_placebo_irrelevant,
    }


def _count(cell: ClassCount) -> dict[str, Any]:
    rate = None if cell.n_asserted == 0 else cell.n_false / cell.n_asserted
    return {"n_false": cell.n_false, "n_asserted": cell.n_asserted, "rate": rate}


def _combined(a: ClassCount, b: ClassCount) -> ClassCount:
    return ClassCount(a.n_false + b.n_false, a.n_asserted + b.n_asserted)


def _scores(seat: SeatScore) -> dict[str, Any]:
    return {
        "checkable": _count(_combined(seat.checkable, seat.placebo_checkable)),
        "uncheckable": _count(_combined(seat.uncheckable, seat.placebo_uncheckable)),
        "main_channel": {
            "checkable": _count(seat.checkable),
            "uncheckable": _count(seat.uncheckable),
        },
    }


def finalize(
    game_payload: Mapping[str, Any],
    *,
    provider: str = "mock",
    model_label: str = "offline-mock",
    truncations: int = 0,
) -> dict[str, Any]:
    """Wrap a ``game`` payload in the versioned envelope with a ``meta`` block.

    ``model_label`` defaults to a generic label; committed records must never carry
    model tier names — real-run drivers pass a generic tier label instead.
    """
    return {
        "record_version": GAME_RECORD_VERSION,
        "game": dict(game_payload),
        "meta": {
            "provider": provider,
            "model_label": model_label,
            "truncations": truncations,
            "record_tool_version": __version__,
        },
    }


def serialize(record: Mapping[str, Any]) -> str:
    """Canonical serialization: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def write_record(record: Mapping[str, Any], path: Path) -> Path:
    """Serialize a record to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(record), encoding="utf-8")
    return path


def load_record(source: Path | str) -> dict[str, Any]:
    """Load and version-check a record; unknown versions are refused, never guessed at."""
    text = Path(source).read_text(encoding="utf-8") if isinstance(source, Path) else source
    parsed: Any = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("run record must be a JSON object")
    version = parsed.get("record_version")
    if version != GAME_RECORD_VERSION:
        raise ValueError(
            f"unsupported record_version {version!r}; this tool reads v{GAME_RECORD_VERSION}"
        )
    return parsed


def default_record_path(cfg: GameConfig, seed: int, *, base: Path) -> Path:
    """``<base>/<arm>-seed<seed>[-interactive].json`` — the default destination."""
    suffix = "-interactive" if cfg.interactive else ""
    return base / f"{cfg.verifier_arm}-seed{seed}{suffix}.json"
