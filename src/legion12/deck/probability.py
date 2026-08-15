"""Exact hypergeometric helpers for deck-building decisions."""

from __future__ import annotations

from math import comb


def _validate(deck_size: int, copies: int, draws: int, at_least: int = 0) -> None:
    if deck_size <= 0:
        raise ValueError("deck_size must be positive")
    if not 0 <= copies <= deck_size:
        raise ValueError("copies must be between 0 and deck_size")
    if not 0 <= draws <= deck_size:
        raise ValueError("draws must be between 0 and deck_size")
    if at_least < 0:
        raise ValueError("at_least must be non-negative")


def probability_at_least_k(deck_size: int, copies: int, draws: int, at_least: int) -> float:
    """Return P(X >= at_least) for draws without replacement.

    X follows a hypergeometric distribution with ``copies`` successes in a
    ``deck_size`` population and ``draws`` sampled cards.
    """

    _validate(deck_size, copies, draws, at_least)
    if at_least == 0:
        return 1.0
    if at_least > min(copies, draws):
        return 0.0

    denominator = comb(deck_size, draws)
    maximum = min(copies, draws)
    minimum = max(at_least, draws - (deck_size - copies))
    numerator = sum(
        comb(copies, successes) * comb(deck_size - copies, draws - successes)
        for successes in range(minimum, maximum + 1)
    )
    return numerator / denominator


def probability_at_least_one(deck_size: int, copies: int, draws: int) -> float:
    """Return the probability of seeing one or more copies."""

    return probability_at_least_k(deck_size, copies, draws, at_least=1)


def expected_copies(deck_size: int, copies: int, draws: int) -> float:
    """Return the expected number of copies seen in ``draws`` cards."""

    _validate(deck_size, copies, draws)
    return draws * copies / deck_size
