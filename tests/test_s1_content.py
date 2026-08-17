from pathlib import Path

import pytest

from legion12.catalog import (
    S1ContentValidationError,
    load_s1_bundle,
    load_simulatable_reference_decks,
)

ROOT = Path(__file__).resolve().parents[1]


def test_s1_bundle_validates_the_fixed_first_match_scope() -> None:
    bundle = load_s1_bundle(ROOT)
    assert len(bundle["disasters"]["cards"]) == 10
    assert [deck["deck_id"] for deck in bundle["reference_decks"]["decks"]] == [
        "s01-tianting-yang-jian-reference",
        "s01-takamagahara-susanoo-reference",
    ]


def test_s1_reference_decks_remain_blocked_until_rules_and_effects_are_ready() -> None:
    with pytest.raises(S1ContentValidationError, match="ruleset is not verified"):
        load_simulatable_reference_decks(ROOT)
