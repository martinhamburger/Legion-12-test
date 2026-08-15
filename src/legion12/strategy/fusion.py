"""Robust fusion of official, expert and empirical strategy priors."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from math import exp, log1p
from pathlib import Path

from .models import FusedStrategy, StrategySource

_EVIDENCE_MULTIPLIER = {
    "tournament_result": 1.50,
    "expert_replay": 1.25,
    "repeated_match_log": 1.20,
    "community_deck": 1.00,
    "official_mechanic": 0.90,
    "designer_commentary": 0.85,
    "hypothesis": 0.55,
}


def load_strategy_sources(path: str | Path) -> list[StrategySource]:
    """Load a JSON list of provenance-aware strategy sources."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("strategy source file must contain a JSON list")
    return [StrategySource.from_dict(item) for item in payload]


def _source_weight(source: StrategySource, matchup: str | None) -> float:
    evidence = _EVIDENCE_MULTIPLIER.get(source.evidence_type, 0.70)
    sample_factor = 1.0 + min(log1p(source.sample_size), log1p(1000)) / log1p(1000)
    matchup_factor = 1.0
    if matchup and source.matchup == matchup:
        matchup_factor = 1.30
    elif source.matchup is not None and source.matchup != matchup:
        matchup_factor = 0.65
    return max(source.reliability * evidence * sample_factor * matchup_factor, 1e-9)


def _weighted_median(values: list[tuple[float, float]]) -> float:
    ordered = sorted(values, key=lambda pair: pair[0])
    total = sum(weight for _, weight in ordered)
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= total / 2:
            return value
    return ordered[-1][0]


def _select_sources(
    sources: Iterable[StrategySource],
    *,
    faction: str,
    archetype: str,
) -> list[StrategySource]:
    selected: list[StrategySource] = []
    for source in sources:
        faction_matches = source.faction in {"*", faction}
        archetype_matches = source.archetype in {"general", archetype}
        if faction_matches and archetype_matches:
            selected.append(source)
    return selected


def fuse_strategy(
    sources: Iterable[StrategySource],
    *,
    faction: str,
    archetype: str,
    matchup: str | None = None,
) -> FusedStrategy:
    """Fuse strategy sources using a robust median/mean blend with shrinkage.

    This intentionally avoids a naive arithmetic average. A weighted median
    limits damage from one extreme guide, while a weighted mean preserves useful
    directional information. Weak evidence is shrunk toward a neutral prior.
    """

    selected = _select_sources(sources, faction=faction, archetype=archetype)
    if not selected:
        raise ValueError(f"no sources found for faction={faction!r}, archetype={archetype!r}")

    per_feature: dict[str, list[tuple[float, float]]] = defaultdict(list)
    rule_support: dict[str, float] = defaultdict(float)
    total_weight = 0.0

    for source in selected:
        weight = _source_weight(source, matchup)
        total_weight += weight
        for feature, value in source.feature_weights.items():
            per_feature[feature].append((max(-10.0, min(10.0, value)), weight))
        for rule in source.rules:
            rule_support[rule] += weight

    fused_weights: dict[str, float] = {}
    feature_confidence: dict[str, float] = {}
    for feature, observations in per_feature.items():
        observation_weight = sum(weight for _, weight in observations)
        weighted_mean = sum(value * weight for value, weight in observations) / observation_weight
        robust_centre = 0.65 * _weighted_median(observations) + 0.35 * weighted_mean
        confidence = 1.0 - exp(-observation_weight / 1.75)
        fused_weights[feature] = round(robust_centre * confidence, 4)
        feature_confidence[feature] = round(confidence, 4)

    rule_threshold = 0.40 * total_weight
    fused_rules = tuple(
        sorted(rule for rule, support in rule_support.items() if support >= rule_threshold)
    )

    return FusedStrategy(
        faction=faction,
        archetype=archetype,
        matchup=matchup,
        feature_weights=dict(sorted(fused_weights.items())),
        feature_confidence=dict(sorted(feature_confidence.items())),
        rules=fused_rules,
        source_ids=tuple(source.source_id for source in selected),
        metadata={
            "source_count": len(selected),
            "total_effective_weight": round(total_weight, 4),
            "fusion": "0.65 weighted median + 0.35 weighted mean, confidence shrinkage",
        },
    )
