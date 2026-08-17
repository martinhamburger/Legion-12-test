"""Explicitly approximate learning environments, isolated from strict game engines."""

from .s1_approx import LabConfig, build_profiles, run_experiment

__all__ = ["LabConfig", "build_profiles", "run_experiment"]
