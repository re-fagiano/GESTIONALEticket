"""Gestione del flusso OAuth2 per Google Calendar."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Optional, Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


LOGGER = logging.getLogger(__name__)


class GoogleCalendarOAuth:
    """Wrapper per gestire autenticazione, salvataggio e refresh dei token OAuth2."""

    def __init__(
        self,
        client_secrets_file: Path | str,
        token_file: Path | str,
        scopes: Optional[Sequence[str]] = None,
        *,
        run_console: bool = True,
        local_server_port: int = 0,
    ) -> None:
        self.client_secrets_file = Path(client_secrets_file)
        self.token_file = Path(token_file)
        self.scopes = list(scopes or ['https://www.googleapis.com/auth/calendar.readonly'])
        self.run_console = run_console
        self.local_server_port = local_server_port

    def _load_credentials_from_disk(self) -> Optional[Credentials]:
        if not self.token_file.exists():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), scopes=self.scopes)
            return creds
        except Exception as exc:  # pragma: no cover - error path
            LOGGER.warning('Impossibile caricare le credenziali OAuth salvate: %s', exc)
            return None

    def _persist_credentials(self, credentials: Credentials) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        data = credentials.to_json()
        self.token_file.write_text(data, encoding='utf-8')
        LOGGER.debug('Token OAuth salvato in %s', self.token_file)

    def authorize(self, *, force_refresh: bool = False) -> Credentials:
        """Restituisce credenziali valide, avviando il flusso OAuth se necessario."""

        credentials = None if force_refresh else self._load_credentials_from_disk()

        if credentials and credentials.valid and not force_refresh:
            return credentials

        if credentials and credentials.expired and credentials.refresh_token and not force_refresh:
            LOGGER.info('Refresh del token OAuth2 in corso...')
            credentials.refresh(Request())
            self._persist_credentials(credentials)
            return credentials

        LOGGER.info('Avvio del flusso OAuth2 per Google Calendar...')
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secrets_file), scopes=self.scopes
        )
        if self.run_console:
            credentials = flow.run_console()
        else:
            credentials = flow.run_local_server(port=self.local_server_port or 0)
        self._persist_credentials(credentials)
        return credentials

    def revoke(self) -> None:
        """Rimuove il file del token salvato."""

        try:
            self.token_file.unlink()
        except FileNotFoundError:  # pragma: no cover - percorso già pulito
            pass

    @staticmethod
    def dump_scopes(scopes: Iterable[str]) -> str:
        return json.dumps(sorted(set(scopes)))


__all__ = ['GoogleCalendarOAuth']
