#!/usr/bin/env python3
"""Run reproducible multi-seed S1 approximate-lab stability experiments."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", required=True, help="comma-separated integer seeds")
    parser.add_argument("--episodes", type=int, default=500_000)
    parser.add_argument("--games", type=int, default=20_000)
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from legion12.lab import LabConfig, run_experiment

    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    if not seeds:
        raise SystemExit("at least one seed is required")
    rows = []
    for index, seed in enumerate(seeds, start=1):
        result = run_experiment(
            ROOT,
            LabConfig(
                seed=seed,
                training_episodes=args.episodes,
                evaluation_games=args.games,
                max_turns=args.max_turns,
            ),
        )
        evaluation = result["evaluation"]
        rows.append(
            {
                "seed": seed,
                "score": evaluation["learned_score"],
                "wins": evaluation["learned_wins"],
                "games": evaluation["games"],
                "confidence_95": evaluation["confidence_95"],
                "by_faction": evaluation["by_faction"],
            }
        )
        print(f"{index}/{len(seeds)} seed={seed} score={evaluation['learned_score']}")
    scores = [row["score"] for row in rows]
    total_wins = sum(row["wins"] for row in rows)
    total_games = sum(row["games"] for row in rows)
    payload = {
        "schema_version": "1.0",
        "lab_id": "s1-approx-v0",
        "disclaimer": "近似规则实验：多 seed 稳定性测试，不代表正式规则胜率。",
        "config": {
            "seeds": seeds,
            "training_episodes": args.episodes,
            "evaluation_games_per_seed": args.games,
            "max_turns": args.max_turns,
        },
        "runs": rows,
        "aggregate": {
            "mean_score": round(statistics.mean(scores), 4),
            "score_standard_deviation": round(statistics.pstdev(scores), 4),
            "minimum_score": min(scores),
            "maximum_score": max(scores),
            "pooled_wins": total_wins,
            "pooled_games": total_games,
            "pooled_score": round(total_wins / total_games, 4),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["aggregate"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
