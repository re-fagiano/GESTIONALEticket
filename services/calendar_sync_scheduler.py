"""Scheduler semplice per avviare la sincronizzazione da Google Calendar."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from flask import Flask

from auth.google_calendar import GoogleCalendarOAuth
from database import get_db
from services.calendar_sync import resolve_calendar_settings, run_calendar_sync


class CalendarSyncScheduler:
    """Esegue periodicamente la sincronizzazione clienti in un thread dedicato."""

    def __init__(
        self,
        app: Flask,
        *,
        interval_seconds: int = 3600,
        past_days: int = 30,
        future_days: int = 7,
        max_results: int = 250,
        calendar_id: Optional[str] = None,
    ) -> None:
        self.app = app
        self.interval_seconds = max(int(interval_seconds), 60)
        self.past_days = past_days
        self.future_days = future_days
        self.max_results = max_results
        self.calendar_id = calendar_id
        self.logger = app.logger.getChild('calendar_auto_sync')
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, name='CalendarSyncScheduler', daemon=True)
        self._thread.start()
        self.logger.info(
            'Scheduler sincronizzazione Google Calendar avviato (intervallo %s secondi).',
            self.interval_seconds,
        )

    def stop(self) -> None:
        if not self._thread:
            return
        self._stop_event.set()
        self._thread.join(timeout=1)
        self._thread = None

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            self._execute_sync()
            self._stop_event.wait(self.interval_seconds)

    def _execute_sync(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.logger.debug('Esecuzione di sincronizzazione già in corso, salto.')
            return
        try:
            with self.app.app_context():
                settings = resolve_calendar_settings(self.app)
                credentials_path = settings['credentials_path']
                if not credentials_path.exists():
                    self.logger.warning(
                        'Sincronizzazione Google Calendar saltata: credenziali mancanti (%s).',
                        credentials_path,
                    )
                    return

                oauth = GoogleCalendarOAuth(
                    credentials_path,
                    settings['token_path'],
                    settings['scopes'],
                    run_console=False,
                    allow_interactive=False,
                )
                calendar_id = (self.calendar_id or settings['calendar_id']).strip() or settings['calendar_id']
                db = get_db()
                stats, _ = run_calendar_sync(
                    db=db,
                    oauth=oauth,
                    calendar_id=calendar_id,
                    past_days=self.past_days,
                    future_days=self.future_days,
                    max_results=self.max_results,
                    logger=self.logger,
                )
                self.logger.info(
                    'Sincronizzazione Google Calendar completata automaticamente: %s creati, %s aggiornati, %s invariati.',
                    stats['created'],
                    stats['updated'],
                    stats['skipped'],
                )
        except RuntimeError as exc:
            self.logger.warning('Impossibile eseguire la sincronizzazione automatica: %s', exc)
        except Exception:
            self.logger.exception('Errore imprevisto durante la sincronizzazione automatica.')
        finally:
            self._lock.release()


__all__ = ['CalendarSyncScheduler']
