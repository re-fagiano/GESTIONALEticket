"""Utility functions and constants for ticket status management.

This module centralizes the allowed ticket statuses, their localized labels,
and helper utilities so that the application logic, templates, and any future
extensions can rely on a single source of truth.  Having the data in one place
reduces the likelihood of merge conflicts and keeps validation logic
consistent across the code base.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final, FrozenSet, Mapping, MutableMapping, Tuple

TicketStatusChoice = Tuple[str, str]

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

TICKET_STATUS_CHOICES: Final[Tuple[TicketStatusChoice, ...]] = (
    ("accettazione", "Accettazione"),
    ("preventivo", "Preventivo"),
    ("riparato", "Riparato"),
    ("chiuso", "Chiuso"),
)

TICKET_STATUS_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {value: label for value, label in TICKET_STATUS_CHOICES}
)

ALLOWED_TICKET_STATUSES: Final[FrozenSet[str]] = frozenset(TICKET_STATUS_LABELS)

DEFAULT_TICKET_STATUS: Final[str] = "accettazione"

LEGACY_TICKET_STATUS_MAP: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Legacy English or previous Italian variants mapped to the new states.
        "open": "accettazione",
        "aperto": "accettazione",
        "in_progress": "preventivo",
        "processing": "preventivo",
        "repaired": "riparato",
        "closed": "chiuso",
    }
)

__all__ = [
    "ALLOWED_TICKET_STATUSES",
    "DEFAULT_TICKET_STATUS",
    "LEGACY_TICKET_STATUS_MAP",
    "TICKET_STATUS_CHOICES",
    "TICKET_STATUS_LABELS",
    "TicketStatusChoice",
    "get_ticket_status_context",
    "get_ticket_status_label",
    "normalize_ticket_record",
    "normalize_ticket_status",
    "is_valid_ticket_status",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_valid_ticket_status(status: str) -> bool:
    """Return ``True`` if *status* is one of the allowed ticket states."""

    return status in ALLOWED_TICKET_STATUSES


def get_ticket_status_label(status: str) -> str:
    """Return the localized label for *status* or *status* if unknown."""

    return TICKET_STATUS_LABELS.get(status, status)


def normalize_ticket_status(status: str) -> str:
    """Map legacy ticket statuses to the new canonical values."""

    if not isinstance(status, str):
        return DEFAULT_TICKET_STATUS

    stripped = status.strip()
    if not stripped:
        return DEFAULT_TICKET_STATUS

    lookup_key = stripped.lower()
    if lookup_key in LEGACY_TICKET_STATUS_MAP:
        return LEGACY_TICKET_STATUS_MAP[lookup_key]

    if lookup_key in ALLOWED_TICKET_STATUSES:
        return lookup_key

    return stripped


def normalize_ticket_record(
    record: MutableMapping[str, Any],
    *,
    status_field: str = "status",
) -> str:
    """Normalize and enrich a ticket-like mapping with status metadata.

    The *record* is mutated in-place so that the normalized status replaces the
    original value and the localized label is stored alongside it using the key
    ``"<status_field>_label"``.  The normalized status is returned for
    convenience so callers can decide whether persistence updates are needed.
    """

    current_status = record.get(status_field, DEFAULT_TICKET_STATUS)
    normalized_status = normalize_ticket_status(current_status)
    record[status_field] = normalized_status
    record[f"{status_field}_label"] = get_ticket_status_label(normalized_status)
    return normalized_status


def get_ticket_status_context() -> Mapping[str, object]:
    """Return the context dictionary shared with Jinja templates.

    The returned mapping is deliberately small and comprised exclusively of
    immutable objects, keeping template rendering deterministic.  Having a
    function here avoids duplicating dictionary construction logic in Flask
    view modules and allows other modules (e.g. CLI scripts) to reuse it.
    """

    return {
        "ticket_status_choices": TICKET_STATUS_CHOICES,
        "ticket_status_labels": TICKET_STATUS_LABELS,
        "ticket_allowed_statuses": ALLOWED_TICKET_STATUSES,
        "ticket_default_status": DEFAULT_TICKET_STATUS,
        "get_ticket_status_label": get_ticket_status_label,
        "normalize_ticket_status": normalize_ticket_status,
    }
