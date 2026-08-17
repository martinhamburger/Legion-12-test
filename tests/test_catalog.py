import json
from pathlib import Path

import pytest

from legion12.catalog import CatalogValidationError, load_trainable_cards, validate_catalog


def card(card_id: str, status: str = "needs_review", effect: str = "not_started") -> dict:
    return {
        "card_id": card_id,
        "source": {"pdf_path": "规则与卡池/通用.pdf", "pdf_sha256": "a" * 64, "page": 3},
        "review": {"status": status},
        "effect": {"implementation_status": effect},
    }


def test_validation_rejects_duplicate_card_id() -> None:
    with pytest.raises(CatalogValidationError, match="duplicate"):
        validate_catalog({"schema_version": "1.0", "cards": [card("a"), card("a")]})


def test_load_trainable_cards_enforces_review_and_effect_gate(tmp_path: Path) -> None:
    path = tmp_path / "pool.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "cards": [
                    card("candidate", "needs_review", "implemented"),
                    card("partial", "verified", "partial"),
                    card("ready", "verified", "implemented"),
                ],
            }
        ),
        encoding="utf-8",
    )
    assert [item["card_id"] for item in load_trainable_cards(path)] == ["ready"]


def test_validation_accepts_a_supplementary_image_source() -> None:
    image_card = card("image")
    image_card["source"] = {
        "kind": "image",
        "image_path": "规则与卡池/补充卡面/S01-0002-佣兵部队.png",
        "image_sha256": "b" * 64,
    }
    validate_catalog({"schema_version": "1.0", "cards": [image_card]})
