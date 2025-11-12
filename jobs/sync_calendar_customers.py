"""Job CLI per sincronizzare i clienti dal calendario Google."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from auth.google_calendar import GoogleCalendarOAuth
from services.customer_sync import CustomerSyncService
from services.google_calendar_client import GoogleCalendarClient

from app import create_app
from database import get_db

LOGGER = logging.getLogger(__name__)


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace('+00:00', 'Z')


def _parse_scopes(raw: str | Sequence[str] | None) -> Sequence[str]:
    if raw is None:
        return ['https://www.googleapis.com/auth/calendar.readonly']
    if isinstance(raw, (list, tuple)):
        scopes = list(raw)
    else:
        scopes = [scope.strip() for scope in str(raw).split(',') if scope.strip()]
    return scopes or ['https://www.googleapis.com/auth/calendar.readonly']


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calendar-id', help='ID del calendario Google da sincronizzare.')
    parser.add_argument(
        '--past-days', type=int, default=30, help='Intervallo retroattivo (in giorni) da includere.'
    )
    parser.add_argument(
        '--future-days', type=int, default=7, help='Intervallo futuro (in giorni) da includere.'
    )
    parser.add_argument('--max-results', type=int, default=250, help='Numero massimo di eventi da analizzare.')
    parser.add_argument(
        '--local-server', action='store_true', help='Utilizza il browser locale per completare l\'OAuth.'
    )
    parser.add_argument(
        '--verbose', action='store_true', help='Abilita log dettagliati.'
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    app = create_app()
    with app.app_context():
        credentials_file = Path(
            os.environ.get('GOOGLE_CALENDAR_CREDENTIALS_FILE')
            or app.config.get('GOOGLE_CALENDAR_CREDENTIALS_FILE')
            or (Path(app.instance_path) / 'google_calendar_credentials.json')
        )
        token_file = Path(
            os.environ.get('GOOGLE_CALENDAR_TOKEN_FILE')
            or app.config.get('GOOGLE_CALENDAR_TOKEN_FILE')
            or (Path(app.instance_path) / 'google_calendar_token.json')
        )
        scopes = _parse_scopes(
            os.environ.get('GOOGLE_CALENDAR_SCOPES')
            or app.config.get('GOOGLE_CALENDAR_SCOPES')
        )

        if not credentials_file.exists():
            LOGGER.error('File di credenziali Google Calendar non trovato: %s', credentials_file)
            return 1

        oauth = GoogleCalendarOAuth(
            credentials_file,
            token_file,
            scopes,
            run_console=not args.local_server,
        )

        calendar_id = (
            args.calendar_id
            or os.environ.get('GOOGLE_CALENDAR_ID')
            or app.config.get('GOOGLE_CALENDAR_ID')
            or 'primary'
        )

        now = datetime.now(timezone.utc)
        time_min = _to_rfc3339(now - timedelta(days=max(args.past_days, 0)))
        time_max = _to_rfc3339(now + timedelta(days=max(args.future_days, 0)))

        client = GoogleCalendarClient(oauth, calendar_id=calendar_id)
        events = client.fetch_events(time_min=time_min, time_max=time_max, max_results=args.max_results)
        candidates = client.extract_customers(events)

        db = get_db()
        sync_service = CustomerSyncService(db)
        stats = sync_service.sync_candidates(candidates)

        LOGGER.info(
            'Sincronizzazione completata: %s creati, %s aggiornati, %s invariati (totale %s).',
            stats['created'],
            stats['updated'],
            stats['skipped'],
            stats['total'],
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
