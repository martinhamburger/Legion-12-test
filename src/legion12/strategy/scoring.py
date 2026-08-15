"""Feature-based action scoring for the non-random baseline policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .models import FusedStrategy


def score_action(features: Mapping[str, float], strategy: FusedStrategy) -> float:
    """Score one legal action using the fused strategy prior.

    The game engine is responsible for legal-action generation. Features are
    normalized signals such as immediate win, prevention of immediate loss,
    tempo, card advantage, morale waste and archetype-specific progress.
    """

    return sum(strategy.feature_weights.get(name, 0.0) * value for name, value in features.items())


def rank_actions(
    actions: Sequence[tuple[str, Mapping[str, float]]],
    strategy: FusedStrategy,
) -> list[tuple[str, float]]:
    """Return deterministic best-first action rankings."""

    ranked = ((action_id, score_action(features, strategy)) for action_id, features in actions)
    return sorted(ranked, key=lambda item: (-item[1], item[0]))
