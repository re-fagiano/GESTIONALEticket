"""Servizio per importare clienti a partire dagli eventi di Google Calendar."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from services.customer_codes import generate_next_customer_code
from services.google_calendar_client import CalendarCustomerCandidate

LOGGER = logging.getLogger(__name__)


@dataclass
class Customer:
    """Rappresenta un record cliente normalizzato."""

    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    source_event_id: Optional[str] = None

    @classmethod
    def from_candidate(cls, candidate: CalendarCustomerCandidate) -> 'Customer':
        return cls(
            name=candidate.name.strip(),
            email=(candidate.email or '').strip() or None,
            phone=(candidate.phone or '').strip() or None,
            address=(candidate.address or '').strip() or None,
            source_event_id=candidate.event_id,
        )


class CustomerSyncService:
    """Sincronizza i clienti estratti dal calendario con il database locale."""

    def __init__(self, connection: sqlite3.Connection, *, logger: Optional[logging.Logger] = None) -> None:
        self.connection = connection
        self.logger = logger or LOGGER

    def sync_candidates(self, candidates: Iterable[CalendarCustomerCandidate]) -> Dict[str, int]:
        customers = [Customer.from_candidate(candidate) for candidate in candidates if candidate.name]
        return self.sync_customers(customers)

    def sync_customers(self, customers: Iterable[Customer]) -> Dict[str, int]:
        stats = {'total': 0, 'created': 0, 'updated': 0, 'skipped': 0}
        cursor = self.connection.cursor()

        for customer in customers:
            stats['total'] += 1
            existing = self._find_existing(cursor, customer)
            if existing is None:
                try:
                    code = generate_next_customer_code(self.connection)
                except ValueError as exc:
                    self.logger.error('Impossibile generare il codice cliente: %s', exc)
                    stats['skipped'] += 1
                    continue
                cursor.execute(
                    'INSERT INTO customers (code, name, email, phone, address) VALUES (?, ?, ?, ?, ?)',
                    (code, customer.name, customer.email, customer.phone, customer.address),
                )
                stats['created'] += 1
                self.logger.info('Creato nuovo cliente "%s" (codice %s).', customer.name, code)
            else:
                updates = {}
                for field in ('name', 'email', 'phone', 'address'):
                    new_value = getattr(customer, field)
                    old_value = existing[field]
                    normalized_old = (old_value or '').strip()
                    normalized_new = (new_value or '').strip()
                    if normalized_old != normalized_new:
                        updates[field] = new_value
                if updates:
                    assignments = ', '.join(f"{field} = ?" for field in updates)
                    values = list(updates.values())
                    values.append(existing['id'])
                    cursor.execute(
                        f'UPDATE customers SET {assignments} WHERE id = ?',
                        values,
                    )
                    stats['updated'] += 1
                    self.logger.info('Aggiornato cliente "%s".', customer.name)
                else:
                    stats['skipped'] += 1

        self.connection.commit()
        return stats

    def _find_existing(self, cursor: sqlite3.Cursor, customer: Customer) -> Optional[sqlite3.Row]:
        if customer.email:
            row = cursor.execute(
                'SELECT * FROM customers WHERE LOWER(email) = LOWER(?)',
                (customer.email,),
            ).fetchone()
            if row:
                return row
        if customer.phone:
            row = cursor.execute(
                'SELECT * FROM customers WHERE phone = ?',
                (customer.phone,),
            ).fetchone()
            if row:
                return row
        row = cursor.execute(
            'SELECT * FROM customers WHERE LOWER(name) = LOWER(?)',
            (customer.name,),
        ).fetchone()
        return row


__all__ = ['Customer', 'CustomerSyncService']
