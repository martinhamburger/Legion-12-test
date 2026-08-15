"""Evaluation metrics and statistically disciplined stopping rules."""

from .statistics import MatchSummary, wilson_interval

__all__ = ["MatchSummary", "wilson_interval"]
