"""Client per interrogare Google Calendar e derivare anagrafiche clienti."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from googleapiclient.discovery import build

from auth.google_calendar import GoogleCalendarOAuth

LOGGER = logging.getLogger(__name__)

_FIELD_PATTERNS = {
    'email': re.compile(r'email\s*[:=-]\s*(?P<value>[^\n]+)', re.IGNORECASE),
    'phone': re.compile(r'(?:telefono|tel|phone)\s*[:=-]\s*(?P<value>[^\n]+)', re.IGNORECASE),
    'address': re.compile(r'(?:indirizzo|address)\s*[:=-]\s*(?P<value>[^\n]+)', re.IGNORECASE),
}


@dataclass
class CalendarCustomerCandidate:
    """Dati anagrafici estratti da un evento di calendario."""

    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    event_id: Optional[str]
    raw_event: dict


class GoogleCalendarClient:
    """Wrapper di alto livello per interrogare il Calendar API."""

    def __init__(
        self,
        oauth: GoogleCalendarOAuth,
        *,
        calendar_id: str = 'primary',
        application_name: str = 'GestionaleTicket/GoogleCalendarSync',
    ) -> None:
        self.oauth = oauth
        self.calendar_id = calendar_id
        self.application_name = application_name

    def fetch_events(
        self,
        *,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
        single_events: bool = True,
        order_by: str = 'startTime',
        query: Optional[str] = None,
    ) -> List[dict]:
        credentials = self.oauth.authorize()
        service = build('calendar', 'v3', credentials=credentials, cache_discovery=False)
        kwargs = {
            'calendarId': self.calendar_id,
            'maxResults': max_results,
            'singleEvents': single_events,
            'orderBy': order_by,
        }
        if time_min:
            kwargs['timeMin'] = time_min
        if time_max:
            kwargs['timeMax'] = time_max
        if query:
            kwargs['q'] = query

        LOGGER.debug('Richiesta eventi calendario %s con parametri %s', self.calendar_id, kwargs)
        events_result = service.events().list(**kwargs).execute()
        items = events_result.get('items', [])
        LOGGER.info('Recuperati %s eventi dal calendario %s', len(items), self.calendar_id)
        return items

    def extract_customers(self, events: Iterable[dict]) -> List[CalendarCustomerCandidate]:
        candidates: List[CalendarCustomerCandidate] = []
        for event in events:
            candidate = self._event_to_candidate(event)
            if candidate:
                candidates.append(candidate)
        LOGGER.info('Estratti %s potenziali clienti dagli eventi.', len(candidates))
        return candidates

    def _event_to_candidate(self, event: dict) -> Optional[CalendarCustomerCandidate]:
        summary = (event.get('summary') or '').strip()
        attendees = event.get('attendees') or []
        description = (event.get('description') or '').strip()
        location = (event.get('location') or '').strip()

        email = None
        name = summary
        if attendees:
            for attendee in attendees:
                if attendee.get('resource'):
                    continue
                email = email or attendee.get('email')
                display_name = (attendee.get('displayName') or '').strip()
                if not name and display_name:
                    name = display_name
                if email and name:
                    break

        if not name:
            LOGGER.debug('Evento %s ignorato: nome assente.', event.get('id'))
            return None

        parsed_fields = self._parse_description(description)
        email = email or parsed_fields.get('email')
        phone = parsed_fields.get('phone')
        address = parsed_fields.get('address') or location

        notes = description or None

        return CalendarCustomerCandidate(
            name=name.strip(),
            email=(email or '').strip() or None,
            phone=(phone or '').strip() or None,
            address=(address or '').strip() or None,
            notes=notes,
            event_id=event.get('id'),
            raw_event=event,
        )

    @staticmethod
    def _parse_description(description: str) -> dict:
        parsed: dict = {}
        if not description:
            return parsed
        for field, pattern in _FIELD_PATTERNS.items():
            match = pattern.search(description)
            if match:
                value = (match.group('value') or '').strip()
                if value:
                    parsed[field] = value
        return parsed


__all__ = ['GoogleCalendarClient', 'CalendarCustomerCandidate']
