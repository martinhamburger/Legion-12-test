#!/usr/bin/env python3
"""Run the isolated S1 approximate learning lab and persist Pages artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from legion12.lab import LabConfig, build_profiles, run_experiment

    parser = argparse.ArgumentParser(
        description="Run the reproducible S1 approximate learning lab."
    )
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument("--episodes", type=int, default=20_000)
    parser.add_argument("--games", type=int, default=1_000)
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/labs/s1-approx-v0")
    args = parser.parse_args()
    config = LabConfig(args.seed, args.episodes, args.games, args.max_turns)
    result = run_experiment(ROOT, config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "profiles.json").write_text(
        json.dumps(build_profiles(ROOT), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "latest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"lab={result['lab_id']} episodes={args.episodes} games={args.games} score={result['evaluation']['learned_score']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
