"""Validation and safe loading for imported card-pool data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CatalogValidationError(ValueError):
    """Raised when a card pool cannot safely be consumed."""


REVIEW_STATUSES = {"needs_review", "verified", "rejected"}
EFFECT_STATUSES = {"not_started", "partial", "implemented", "not_applicable"}
ENGINE_CARD_TYPES = {
    "ruler",
    "unit",
    "artifact",
    "tactic_active",
    "tactic_counter",
    "city",
    "faction_morale",
    "disaster",
    "token",
    "unmodeled",
}


def load_catalog(path: Path) -> dict[str, Any]:
    """Load and validate a card-pool JSON document."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_catalog(payload)
    return payload


def validate_catalog(payload: dict[str, Any]) -> None:
    """Validate stable identifiers and the provenance/review safety boundary."""

    if payload.get("schema_version") != "1.0":
        raise CatalogValidationError("unsupported or missing schema_version")
    if not isinstance(payload.get("cards"), list):
        raise CatalogValidationError("cards must be a list")

    seen: set[str] = set()
    for card in payload["cards"]:
        card_id = card.get("card_id")
        if not isinstance(card_id, str) or not card_id:
            raise CatalogValidationError("every card needs a non-empty card_id")
        if card_id in seen:
            raise CatalogValidationError(f"duplicate card_id: {card_id}")
        seen.add(card_id)

        source = card.get("source", {})
        if source.get("kind") == "image":
            if not isinstance(source.get("image_path"), str) or not source["image_path"]:
                raise CatalogValidationError(f"{card_id} is missing source.image_path")
            if not isinstance(source.get("image_sha256"), str) or len(source["image_sha256"]) != 64:
                raise CatalogValidationError(f"{card_id} is missing source.image_sha256")
        else:
            if not isinstance(source.get("pdf_path"), str) or not source["pdf_path"]:
                raise CatalogValidationError(f"{card_id} is missing source.pdf_path")
            if not isinstance(source.get("pdf_sha256"), str) or len(source["pdf_sha256"]) != 64:
                raise CatalogValidationError(f"{card_id} is missing source.pdf_sha256")
            if not isinstance(source.get("page"), int) or source["page"] < 1:
                raise CatalogValidationError(f"{card_id} has an invalid source.page")

        engine_card_type = card.get("engine_card_type")
        if engine_card_type is not None and engine_card_type not in ENGINE_CARD_TYPES:
            raise CatalogValidationError(f"{card_id} has an invalid engine_card_type")

        review = card.get("review", {})
        if review.get("status") not in REVIEW_STATUSES:
            raise CatalogValidationError(f"{card_id} has an invalid review.status")
        effect = card.get("effect", {})
        if effect.get("implementation_status") not in EFFECT_STATUSES:
            raise CatalogValidationError(f"{card_id} has an invalid effect implementation_status")


def load_trainable_cards(path: Path) -> list[dict[str, Any]]:
    """Return only cards that are reviewed and have executable effects.

    This intentionally excludes OCR candidates and partly implemented cards.  It is
    the mandatory boundary between a human-review catalog and a rules engine.
    """

    payload = load_catalog(path)
    return [
        card
        for card in payload["cards"]
        if card["review"]["status"] == "verified"
        and card["effect"]["implementation_status"] in {"implemented", "not_applicable"}
    ]
