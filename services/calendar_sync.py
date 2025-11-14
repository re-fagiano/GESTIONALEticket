"""Utility per la sincronizzazione dei clienti tramite Google Calendar."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from flask import Flask

from auth.google_calendar import GoogleCalendarOAuth
from services.customer_sync import CustomerSyncService
from services.google_calendar_client import GoogleCalendarClient

DEFAULT_CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def to_rfc3339(dt: datetime) -> str:
    """Converte un ``datetime`` nel formato RFC3339 richiesto da Google."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace('+00:00', 'Z')


def parse_calendar_scopes(raw: Optional[Sequence[str] | str]) -> List[str]:
    """Normalizza la lista di scope configurati per Google Calendar."""

    if raw is None:
        return list(DEFAULT_CALENDAR_SCOPES)
    if isinstance(raw, (list, tuple, set)):
        scopes = [str(scope).strip() for scope in raw if str(scope).strip()]
    else:
        scopes = [scope.strip() for scope in str(raw).split(',') if scope.strip()]
    return scopes or list(DEFAULT_CALENDAR_SCOPES)


def resolve_calendar_settings(app: Flask) -> dict:
    """Restituisce percorsi e impostazioni per l'integrazione Google Calendar."""

    credentials_path = Path(
        app.config.get('GOOGLE_CALENDAR_CREDENTIALS_FILE')
        or (Path(app.instance_path) / 'google_calendar_credentials.json')
    )
    token_path = Path(
        app.config.get('GOOGLE_CALENDAR_TOKEN_FILE')
        or (Path(app.instance_path) / 'google_calendar_token.json')
    )
    scopes = parse_calendar_scopes(app.config.get('GOOGLE_CALENDAR_SCOPES'))
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID') or 'primary'
    return {
        'credentials_path': credentials_path,
        'token_path': token_path,
        'scopes': scopes,
        'calendar_id': calendar_id,
    }


def run_calendar_sync(
    *,
    db,
    oauth: GoogleCalendarOAuth,
    calendar_id: str,
    past_days: int = 30,
    future_days: int = 7,
    max_results: int = 250,
    logger: Optional[logging.Logger] = None,
) -> Tuple[dict, dict]:
    """Scarica gli eventi dal calendario e sincronizza i clienti."""

    past_days = max(int(past_days), 0)
    future_days = max(int(future_days), 0)
    max_results = max(int(max_results), 1)

    now = datetime.now(timezone.utc)
    time_min = to_rfc3339(now - timedelta(days=past_days))
    time_max = to_rfc3339(now + timedelta(days=future_days))

    client = GoogleCalendarClient(oauth, calendar_id=calendar_id)
    events = client.fetch_events(time_min=time_min, time_max=time_max, max_results=max_results)
    candidates = client.extract_customers(events)

    sync_service = CustomerSyncService(db, logger=logger)
    stats = sync_service.sync_candidates(candidates)
    sync_details = {
        'calendar_id': calendar_id,
        'events_count': len(events),
        'candidates_count': len(candidates),
        'past_days': past_days,
        'future_days': future_days,
        'max_results': max_results,
    }
    return stats, sync_details


__all__ = [
    'DEFAULT_CALENDAR_SCOPES',
    'parse_calendar_scopes',
    'resolve_calendar_settings',
    'run_calendar_sync',
    'to_rfc3339',
]
