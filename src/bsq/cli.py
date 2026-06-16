"""Command-line entry point.

Phase 0 ships ``version`` and ``selftest`` (a zero-setup determinism check on the
mock provider). The experiment commands (``run``, ``replay``, ``score``) arrive in
later phases on top of this plumbing.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from bsq import __version__
from bsq.config import provider_config_from_env
from bsq.llm import ChatTurn, make_client


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bsq", description="Balloon Squeeze")
    parser.add_argument("--version", action="version", version=f"bsq {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("selftest", help="run a zero-setup determinism check on the mock provider")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return _selftest()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
