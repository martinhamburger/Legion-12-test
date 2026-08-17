"""Versioned card-pool loading and training-safety gates."""

from .catalog import CatalogValidationError, load_catalog, load_trainable_cards, validate_catalog
from .s1 import (
    S1ContentValidationError,
    load_s1_bundle,
    load_simulatable_reference_decks,
    validate_s1_bundle,
)

__all__ = [
    "CatalogValidationError",
    "S1ContentValidationError",
    "load_catalog",
    "load_s1_bundle",
    "load_simulatable_reference_decks",
    "load_trainable_cards",
    "validate_catalog",
    "validate_s1_bundle",
]
