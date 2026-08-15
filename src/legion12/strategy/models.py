"""Data models for provenance-aware strategy seeds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class StrategySource:
    """One human, official or experimental strategy source."""

    source_id: str
    name: str
    faction: str
    archetype: str
    evidence_type: str
    reliability: float
    feature_weights: dict[str, float]
    rules: tuple[str, ...] = ()
    sample_size: int = 0
    matchup: str | None = None
    game_version: str | None = None
    source_url: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")
        if not 0 <= self.reliability <= 1:
            raise ValueError("reliability must be between 0 and 1")
        if self.sample_size < 0:
            raise ValueError("sample_size must be non-negative")
        if any(not -10 <= value <= 10 for value in self.feature_weights.values()):
            raise ValueError("feature weights must be within [-10, 10]")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StrategySource:
        return cls(
            source_id=str(payload["source_id"]),
            name=str(payload["name"]),
            faction=str(payload["faction"]),
            archetype=str(payload["archetype"]),
            evidence_type=str(payload["evidence_type"]),
            reliability=float(payload["reliability"]),
            feature_weights={
                str(key): float(value) for key, value in payload["feature_weights"].items()
            },
            rules=tuple(str(rule) for rule in payload.get("rules", [])),
            sample_size=int(payload.get("sample_size", 0)),
            matchup=payload.get("matchup"),
            game_version=payload.get("game_version"),
            source_url=payload.get("source_url"),
            notes=payload.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class FusedStrategy:
    """A robustly fused strategy prior for one faction and archetype."""

    faction: str
    archetype: str
    feature_weights: dict[str, float]
    feature_confidence: dict[str, float]
    rules: tuple[str, ...]
    source_ids: tuple[str, ...]
    matchup: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
