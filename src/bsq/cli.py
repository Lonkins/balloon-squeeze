"""Command-line entry point.

- ``bsq selftest`` — zero-setup determinism check on the mock provider.
- ``bsq run`` — run one mock game and print the impostor's per-class false-mass.

The remaining experiment commands (``replay``, ``score`` over saved logs) arrive in
later phases on top of this plumbing.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from bsq import __version__
from bsq.config import game_config_from_env, provider_config_from_env, resolve_arm
from bsq.engine import run_game
from bsq.llm import ChatTurn, make_client
from bsq.models import STANDARD_ARMS
from bsq.record import default_record_path, finalize, load_record, write_record
from bsq.render import render_html
from bsq.replay import arm_swap_is_identical, is_deterministic


def _selftest() -> int:
    """Exercise the mock provider and confirm it is deterministic under a seed."""
    cfg = provider_config_from_env()
    if cfg.provider != "mock":
        print(f"selftest expects BSQ_PROVIDER=mock (got {cfg.provider!r})", file=sys.stderr)
        return 2
    client = make_client(cfg)
    messages = [ChatTurn(role="user", content="worst advice you ever followed?")]
    first = client.complete(system="You are a participant.", messages=messages, seed=42)
    second = client.complete(system="You are a participant.", messages=messages, seed=42)
    ok = first == second
    print(f"mock seed=42 -> {first!r}")
    print("deterministic: " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def _run(args: argparse.Namespace) -> int:
    """Run a single mock game and report the impostor's per-class false-mass."""
    cfg = game_config_from_env()
    if args.rounds is not None:
        cfg = replace(cfg, rounds=args.rounds)
    if args.arm is not None:
        resolve_arm(args.arm)  # validate
        cfg = replace(cfg, verifier_arm=args.arm)
    if args.interactive:
        cfg = replace(cfg, interactive=True)
    seed = args.seed if args.seed is not None else (provider_config_from_env().seed or 0)

    result = run_game(cfg, seed)
    provider = provider_config_from_env().provider
    record = finalize(
        result.record_game,
        provider=provider,
        model_label="offline-mock" if provider == "mock" else "unlabeled",
    )
    destination = (
        Path(args.out) if args.out else default_record_path(cfg, seed, base=Path("runs"))
    )
    write_record(record, destination)
    seat = result.report.by_seat[result.game.impostor_id]
    c, u = seat.checkable, seat.uncheckable
    print(f"game seed={seed} arm={cfg.verifier_arm} impostor={result.game.impostor_id}")
    print(f"  checkable  : false={c.n_false}/{c.n_asserted}  C={seat.c:.3f}")
    print(f"  uncheckable: false={u.n_false}/{u.n_asserted}  U={seat.u:.3f}")
    print(f"  record     : {destination}")
    return 0


def _replay(args: argparse.Namespace) -> int:
    """Check the within-world replay invariants on the configured provider (mock)."""
    cfg = game_config_from_env()
    seed = args.seed if args.seed is not None else (provider_config_from_env().seed or 0)
    arms = list(STANDARD_ARMS)
    identical = arm_swap_is_identical(cfg, seed, arms)
    deterministic = all(is_deterministic(cfg, seed, arm) for arm in arms)
    print(f"replay seed={seed} arms={arms}")
    print(f"  arm-swap identical (agent claim stream): {'OK' if identical else 'FAILED'}")
    print(f"  deterministic (same seed+arm twice)    : {'OK' if deterministic else 'FAILED'}")
    print("  note: real-provider determinism is not checked here (needs a provider + key)")
    return 0 if identical and deterministic else 1


def _render(args: argparse.Namespace) -> int:
    """Render a run record to a self-contained HTML replay."""
    source = Path(args.record)
    try:
        record = load_record(source)
        html = render_html(record)
    except (ValueError, OSError, KeyError) as exc:
        print(f"cannot render {source}: {exc}", file=sys.stderr)
        return 1
    destination = Path(args.out) if args.out else source.with_suffix(".html")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    print(f"replay: {destination}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bsq", description="Balloon Squeeze")
    parser.add_argument("--version", action="version", version=f"bsq {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("selftest", help="run a zero-setup determinism check on the mock provider")
    run_p = sub.add_parser("run", help="run one mock game and print per-class false-mass")
    run_p.add_argument("--seed", type=int, default=None, help="world seed (default: BSQ_SEED or 0)")
    run_p.add_argument("--rounds", type=int, default=None, help="number of rounds")
    run_p.add_argument("--arm", type=str, default=None, help="verifier arm (e.g. A0_off)")
    run_p.add_argument(
        "--interactive",
        action="store_true",
        help="interactive mode: speakers see the discussion; rounds end in a vote",
    )
    run_p.add_argument(
        "--out",
        type=str,
        default=None,
        help="run-record destination (default: runs/<arm>-seed<seed>[-interactive].json)",
    )
    replay_p = sub.add_parser("replay", help="check arm-swap identity + determinism on mock")
    replay_p.add_argument("--seed", type=int, default=None, help="world seed (default: BSQ_SEED)")
    render_p = sub.add_parser("render", help="render a run record to an HTML replay")
    render_p.add_argument("record", type=str, help="path to a run-record .json")
    render_p.add_argument(
        "-o", "--out", type=str, default=None, help="output path (default: alongside the record)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return _selftest()
    if args.command == "run":
        return _run(args)
    if args.command == "replay":
        return _replay(args)
    if args.command == "render":
        return _render(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
