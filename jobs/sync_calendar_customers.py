"""Job CLI per sincronizzare i clienti dal calendario Google."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from auth.google_calendar import GoogleCalendarOAuth
from services.calendar_sync import parse_calendar_scopes, run_calendar_sync

from app import create_app
from database import get_db

LOGGER = logging.getLogger(__name__)


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
        scopes = parse_calendar_scopes(
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

        db = get_db()
        stats, details = run_calendar_sync(
            db=db,
            oauth=oauth,
            calendar_id=calendar_id,
            past_days=args.past_days,
            future_days=args.future_days,
            max_results=args.max_results,
            logger=LOGGER,
        )
        LOGGER.info(
            'Sincronizzazione completata: %s creati, %s aggiornati, %s invariati (totale %s).',
            stats['created'],
            stats['updated'],
            stats['skipped'],
            stats['total'],
        )
        LOGGER.info(
            'Calendario %s: %s eventi elaborati, %s candidati estratti.',
            details['calendar_id'],
            details['events_count'],
            details['candidates_count'],
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
