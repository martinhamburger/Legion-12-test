from pathlib import Path

from legion12.lab import LabConfig, build_profiles, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_s1_lab_profiles_cover_the_two_reference_decks_without_claiming_strict_rules() -> None:
    document = build_profiles(ROOT)
    assert document["coverage"]["main_cards"] == 29
    assert document["coverage"]["leaders"] == 2
    assert document["coverage"]["resources"] == 2
    assert "不代表正式规则胜率" in document["disclaimer"]
    mercenary = next(
        profile for profile in document["profiles"] if profile["profile_id"] == "S01-0002"
    )
    assert mercenary["review_status"] == "needs_review"


def test_s1_lab_is_deterministic_for_a_fixed_seed() -> None:
    config = LabConfig(seed=7, training_episodes=40, evaluation_games=20, max_turns=6)
    first = run_experiment(ROOT, config)
    second = run_experiment(ROOT, config)
    assert first["evaluation"] == second["evaluation"]
    assert first["representative_replays"] == second["representative_replays"]
    assert first["evaluation"]["games"] == 20
    assert len(first["training_curve"]) == 20
    assert {"mean_reward", "win_rate", "epsilon", "mean_turns"} <= set(first["training_curve"][0])
    assert first["deck_insights"]["morale_waste_per_turn"] >= 0
    for replay in first["representative_replays"]:
        for step in replay["steps"]:
            assert step["chosen_action"] in step["legal_actions"]
            assert step["active_morale"] >= 0
            assert step["rested_morale"] >= 0
            assert len(step["board"]) <= 3
