from legion12.evaluation.statistics import MatchSummary, wilson_interval


def test_wilson_interval_contains_observed_score() -> None:
    lower, upper = wilson_interval(60, 100)
    assert lower < 0.60 < upper


def test_match_summary_draws_count_as_half() -> None:
    summary = MatchSummary(wins=50, draws=20, losses=30)
    assert summary.games == 100
    assert summary.score == 0.60


def test_sequential_decision_accepts_clear_winner() -> None:
    summary = MatchSummary(wins=150, draws=0, losses=50)
    assert summary.decision(minimum_games=200, required_margin=0.02) == "accept"
