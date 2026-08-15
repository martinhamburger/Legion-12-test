"""Small, dependency-free statistical helpers for match evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


def wilson_interval(successes: float, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial-like score.

    Draws may be represented as half a success. This is an approximation, but
    is more stable than a plain normal interval for small samples.
    """

    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must be between 0 and trials")
    if z <= 0:
        raise ValueError("z must be positive")

    proportion = successes / trials
    denominator = 1 + z**2 / trials
    centre = proportion + z**2 / (2 * trials)
    margin = z * sqrt((proportion * (1 - proportion) + z**2 / (4 * trials)) / trials)
    return (centre - margin) / denominator, (centre + margin) / denominator


@dataclass(frozen=True, slots=True)
class MatchSummary:
    """Win/draw/loss summary for one candidate against one baseline."""

    wins: int
    draws: int
    losses: int

    def __post_init__(self) -> None:
        if min(self.wins, self.draws, self.losses) < 0:
            raise ValueError("match counts must be non-negative")
        if self.games == 0:
            raise ValueError("at least one game is required")

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def score(self) -> float:
        return (self.wins + 0.5 * self.draws) / self.games

    def confidence_interval(self, z: float = 1.96) -> tuple[float, float]:
        return wilson_interval(self.wins + 0.5 * self.draws, self.games, z=z)

    def decision(
        self,
        *,
        target: float = 0.5,
        required_margin: float = 0.0,
        minimum_games: int = 200,
    ) -> str:
        """Return ``accept``, ``reject`` or ``continue`` for sequential screening."""

        if self.games < minimum_games:
            return "continue"
        lower, upper = self.confidence_interval()
        if lower > target + required_margin:
            return "accept"
        if upper < target + required_margin:
            return "reject"
        return "continue"
