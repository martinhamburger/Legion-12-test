"""Validation and strict loading for the S1 first-match structured data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .catalog import load_catalog


class S1ContentValidationError(ValueError):
    """Raised when S1 structured content is incomplete or unsafe to simulate."""


S01_DISASTERS = {f"S01-DS{number:02d}" for number in range(1, 11)}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_is_valid(source: dict[str, Any]) -> bool:
    if source.get("kind") == "image":
        return (
            isinstance(source.get("image_path"), str) and len(source.get("image_sha256", "")) == 64
        )
    return (
        isinstance(source.get("pdf_path"), str)
        and len(source.get("pdf_sha256", "")) == 64
        and (source.get("page") is None or isinstance(source.get("page"), int))
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_source_files(root: Path, sources: list[dict[str, Any]]) -> None:
    """Verify that all source records point to present, hash-matching evidence."""

    checked: set[tuple[str, str]] = set()
    for source in sources:
        if not _source_is_valid(source):
            raise S1ContentValidationError("an S1 source is incomplete")
        path = source.get("asset_path") or source.get("pdf_path") or source.get("image_path")
        expected = (
            source.get("asset_sha256") or source.get("pdf_sha256") or source.get("image_sha256")
        )
        if not isinstance(path, str) or not isinstance(expected, str):
            raise S1ContentValidationError("an S1 source has no file hash")
        key = (path, expected)
        if key in checked:
            continue
        checked.add(key)
        evidence = root / path
        if not evidence.is_file():
            raise S1ContentValidationError(f"source evidence is missing: {path}")
        if _sha256(evidence) != expected:
            raise S1ContentValidationError(f"source hash mismatch: {path}")


def load_s1_bundle(root: Path) -> dict[str, Any]:
    """Load and validate all structured S1 files without authorizing simulation."""

    catalog = load_catalog(root / "data/card_pools/s01/card_pool.json")
    s1 = root / "data/s1"
    rulesets = root / "data/rulesets"
    bundle = {
        "catalog": catalog,
        "disasters": _read(s1 / "disasters.json"),
        "factions": _read(s1 / "faction_resources.json"),
        "reference_decks": _read(s1 / "reference_decks.json"),
        "standard_ruleset": _read(rulesets / "standard-2.0-s01.json"),
        "historical_rulebook": _read(rulesets / "handbook-v1-2025-04-26.json"),
        "version_differences": _read(rulesets / "version_differences.json"),
        "source_registry": _read(root / "data/strategy_sources/source_registry.json"),
    }
    validate_s1_bundle(bundle)
    sources = [card["source"] for card in bundle["catalog"]["cards"]]
    sources += [card["source"] for card in bundle["disasters"]["cards"]]
    sources += [item["source"] for item in bundle["factions"]["factions"]]
    sources += bundle["standard_ruleset"]["sources"]
    sources.append(bundle["historical_rulebook"]["source"])
    sources += [rule["source"] for rule in bundle["historical_rulebook"]["rules"]]
    _validate_source_files(root, sources)
    return bundle


def validate_s1_bundle(bundle: dict[str, Any]) -> None:
    """Validate identifiers, S1 boundaries, and reference-deck legality."""

    catalog_cards = bundle["catalog"]["cards"]
    by_official_id = {
        card.get("official_card_id"): card for card in catalog_cards if card.get("official_card_id")
    }
    if "S01-0002" not in by_official_id:
        raise S1ContentValidationError("S01-0002 佣兵部队 is missing")

    disasters = bundle["disasters"].get("cards")
    if not isinstance(disasters, list):
        raise S1ContentValidationError("disasters.cards must be a list")
    disaster_ids = {card.get("official_card_id") for card in disasters}
    if disaster_ids != S01_DISASTERS:
        raise S1ContentValidationError(
            "S1 disaster catalogue must contain exactly S01-DS01 through S01-DS10"
        )
    final = [card for card in disasters if card.get("is_final")]
    if len(final) != 1 or final[0].get("official_card_id") != "S01-DS10":
        raise S1ContentValidationError("S01-DS10 must be the only final disaster")
    if any(not _source_is_valid(card.get("source", {})) for card in disasters):
        raise S1ContentValidationError("every disaster needs a complete source")

    factions = bundle["factions"].get("factions")
    if not isinstance(factions, list) or {item.get("faction_id") for item in factions} != {
        "tianting",
        "takamagahara",
    }:
        raise S1ContentValidationError(
            "S1 first match requires tianting and takamagahara morale definitions"
        )
    if any(
        item.get("morale_deck_size") != 8 or not _source_is_valid(item.get("source", {}))
        for item in factions
    ):
        raise S1ContentValidationError(
            "each first-match faction needs an 8-card sourced morale deck"
        )

    standard = bundle["standard_ruleset"]
    if standard.get("ruleset_id") != "standard-2.0-s01":
        raise S1ContentValidationError("unexpected standard ruleset")
    draft = standard.get("disaster_draft", {})
    if (
        draft.get("final_disaster_id") != "S01-DS10"
        or draft.get("set_id") != "s01-disaster-catalogue"
    ):
        raise S1ContentValidationError("standard ruleset does not lock the S1 disaster pool")
    if draft.get("bans") != ["first_player", "second_player", "first_player"]:
        raise S1ContentValidationError("standard ruleset must define the three S1 disaster bans")
    if (
        draft.get("public_random_draw") != 1
        or draft.get("first_player_draws") != 3
        or draft.get("first_player_selects") != 1
        or draft.get("second_player_draws") != 2
        or draft.get("second_player_selects") != 1
        or draft.get("deck_order") != "shuffle_selected_then_place_above_final"
    ):
        raise S1ContentValidationError("standard ruleset has an incomplete S1 disaster draft")
    if not all(_source_is_valid(source) for source in standard.get("sources", [])):
        raise S1ContentValidationError("standard ruleset needs complete sources")

    historical = bundle["historical_rulebook"]
    forbidden = set(historical.get("must_not_drive", []))
    if not {"standard-2.0-s01", "training", "strict_simulation"}.issubset(forbidden):
        raise S1ContentValidationError("historical handbook must be isolated from strict execution")
    historical_rules = historical.get("rules", [])
    if len(historical_rules) != 22 or any(
        not isinstance(rule.get("text"), str)
        or not rule["text"].strip()
        or not _source_is_valid(rule.get("source", {}))
        for rule in historical_rules
    ):
        raise S1ContentValidationError(
            "historical handbook must contain 22 sourced transcribed pages"
        )

    comparisons = bundle["version_differences"].get("comparisons", [])
    if not any(
        item.get("higher_priority_ruleset_id") == "standard-2.0-s01"
        and item.get("lower_priority_ruleset_id") == "handbook-v1-2025-04-26"
        for item in comparisons
    ):
        raise S1ContentValidationError("historical rulebook needs an explicit precedence record")

    registry = bundle.get("source_registry", [])
    registry_ids = {entry.get("source_id") for entry in registry if isinstance(entry, dict)}
    registry_ids.update(source.get("source_id") for source in standard.get("sources", []))

    seen_decks: set[str] = set()
    for deck in bundle["reference_decks"].get("decks", []):
        deck_id = deck.get("deck_id")
        if not isinstance(deck_id, str) or deck_id in seen_decks:
            raise S1ContentValidationError("reference deck ids must be unique")
        seen_decks.add(deck_id)
        if deck.get("ruleset_id") != "standard-2.0-s01":
            raise S1ContentValidationError(f"{deck_id} references the wrong ruleset")
        if not set(deck.get("source_ids", [])).issubset(registry_ids):
            raise S1ContentValidationError(f"{deck_id} references an unknown strategy source")
        cards = deck.get("cards", {})
        if sum(cards.values()) != 40:
            raise S1ContentValidationError(f"{deck_id} must contain 40 cards")
        faction = deck.get("faction_id")
        ruler = by_official_id.get(deck.get("ruler_official_card_id"))
        if (
            ruler is None
            or ruler.get("engine_card_type") != "ruler"
            or ruler["faction"]["id"] != faction
        ):
            raise S1ContentValidationError(f"{deck_id} has an invalid ruler")
        for official_id, copies in cards.items():
            card = by_official_id.get(official_id)
            if card is None:
                raise S1ContentValidationError(f"{deck_id} references unknown card {official_id}")
            if not isinstance(copies, int) or copies < 1 or copies > 3:
                raise S1ContentValidationError(f"{deck_id} has invalid copies for {official_id}")
            if card["faction"]["id"] not in {faction, "common"}:
                raise S1ContentValidationError(f"{deck_id} includes off-faction card {official_id}")


def load_simulatable_reference_decks(root: Path) -> list[dict[str, Any]]:
    """Return reference decks only after every dependency is verified and implemented."""

    bundle = load_s1_bundle(root)
    standard = bundle["standard_ruleset"]
    if standard.get("status") != "verified":
        raise S1ContentValidationError("standard ruleset is not verified")
    dependencies: list[dict[str, Any]] = []
    dependencies.extend(bundle["catalog"]["cards"])
    dependencies.extend(bundle["disasters"]["cards"])
    dependencies.extend(bundle["factions"]["factions"])
    if any(item.get("review", {}).get("status") != "verified" for item in dependencies):
        raise S1ContentValidationError("S1 content has unreviewed dependencies")
    if any(
        item.get("effect", {}).get("implementation_status") not in {"implemented", "not_applicable"}
        for item in dependencies
        if "effect" in item
    ):
        raise S1ContentValidationError("S1 content has unimplemented effects")
    raise S1ContentValidationError("no S1 game engine is available yet")
