"""Command-line entry point for early Legion 12 research utilities."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from .deck.probability import expected_copies, probability_at_least_k
from .strategy.fusion import fuse_strategy, load_strategy_sources


def _odds_command(args: argparse.Namespace) -> int:
    probability = probability_at_least_k(
        args.deck_size,
        args.copies,
        args.draws,
        args.at_least,
    )
    result = {
        "deck_size": args.deck_size,
        "copies": args.copies,
        "draws": args.draws,
        "at_least": args.at_least,
        "probability": probability,
        "percentage": round(probability * 100, 4),
        "expected_copies": expected_copies(args.deck_size, args.copies, args.draws),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _fuse_command(args: argparse.Namespace) -> int:
    sources = load_strategy_sources(args.source)
    strategy = fuse_strategy(
        sources,
        faction=args.faction,
        archetype=args.archetype,
        matchup=args.matchup,
    )
    print(json.dumps(asdict(strategy), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legion12",
        description="Expert-seeded Legion 12 deck and policy research tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    odds = subparsers.add_parser("odds", help="calculate exact draw probabilities")
    odds.add_argument("--deck-size", type=int, required=True)
    odds.add_argument("--copies", type=int, required=True)
    odds.add_argument("--draws", type=int, required=True)
    odds.add_argument("--at-least", type=int, default=1)
    odds.set_defaults(handler=_odds_command)

    fuse = subparsers.add_parser("fuse", help="fuse provenance-aware strategy sources")
    fuse.add_argument("--source", type=Path, required=True)
    fuse.add_argument("--faction", required=True)
    fuse.add_argument("--archetype", required=True)
    fuse.add_argument("--matchup")
    fuse.set_defaults(handler=_fuse_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
