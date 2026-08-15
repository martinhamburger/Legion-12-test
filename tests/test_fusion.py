from legion12.strategy.fusion import fuse_strategy
from legion12.strategy.models import StrategySource
from legion12.strategy.scoring import rank_actions


def _source(source_id: str, value: float, reliability: float = 1.0) -> StrategySource:
    return StrategySource(
        source_id=source_id,
        name=source_id,
        faction="tianting",
        archetype="ramp_control",
        evidence_type="expert_replay",
        reliability=reliability,
        feature_weights={"tempo": value, "immediate_win": 10.0},
        rules=("take_immediate_win",),
    )


def test_fusion_is_robust_to_one_extreme_source() -> None:
    strategy = fuse_strategy(
        [_source("a", 1.0), _source("b", 1.2), _source("outlier", 10.0, 0.2)],
        faction="tianting",
        archetype="ramp_control",
    )
    assert 0.5 < strategy.feature_weights["tempo"] < 3.0
    assert "take_immediate_win" in strategy.rules


def test_action_ranking_uses_fused_weights() -> None:
    strategy = fuse_strategy(
        [_source("a", 2.0)],
        faction="tianting",
        archetype="ramp_control",
    )
    ranked = rank_actions(
        [
            ("slow", {"tempo": 0.1}),
            ("fast", {"tempo": 0.9}),
        ],
        strategy,
    )
    assert ranked[0][0] == "fast"
