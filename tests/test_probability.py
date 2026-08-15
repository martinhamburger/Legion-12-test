from math import isclose

import pytest

from legion12.deck.probability import expected_copies, probability_at_least_k


def test_probability_at_least_one_matches_complement() -> None:
    probability = probability_at_least_k(deck_size=40, copies=3, draws=6, at_least=1)
    assert isclose(probability, 0.3943319838, rel_tol=1e-9)


def test_impossible_threshold_is_zero() -> None:
    assert probability_at_least_k(40, 2, 6, 3) == 0.0


def test_expected_copies() -> None:
    assert expected_copies(40, 3, 8) == 0.6


def test_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        probability_at_least_k(40, 41, 6, 1)
