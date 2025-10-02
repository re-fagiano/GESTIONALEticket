"""Utility functions and constants for ticket status management.

This module centralizes the allowed ticket statuses, their localized labels,
and helper utilities so that the application logic, templates, and any future
extensions can rely on a single source of truth.  Having the data in one place
reduces the likelihood of merge conflicts and keeps validation logic
consistent across the code base.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, FrozenSet, Mapping, Tuple

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

__all__ = [
    "ALLOWED_TICKET_STATUSES",
    "DEFAULT_TICKET_STATUS",
    "TICKET_STATUS_CHOICES",
    "TICKET_STATUS_LABELS",
    "TicketStatusChoice",
    "get_ticket_status_context",
    "is_valid_ticket_status",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_valid_ticket_status(status: str) -> bool:
    """Return ``True`` if *status* is one of the allowed ticket states."""

    return status in ALLOWED_TICKET_STATUSES


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
    }
