"""Utility per la generazione dei codici cliente sequenziali."""

from __future__ import annotations

import sqlite3

CUSTOMER_CODE_ALPHABET = 'abcdefghijklmnopqrstuvwxyz'
CUSTOMER_CODE_LENGTH = 4
MAX_CUSTOMER_CODES = len(CUSTOMER_CODE_ALPHABET) ** CUSTOMER_CODE_LENGTH


def customer_code_to_int(code: str) -> int:
    """Converte un codice cliente (es. ``"aaab"``) nel corrispondente valore intero."""
    normalized = (code or '').strip().lower()
    if len(normalized) != CUSTOMER_CODE_LENGTH:
        raise ValueError('Codice cliente non valido.')

    value = 0
    base = len(CUSTOMER_CODE_ALPHABET)
    for char in normalized:
        if char not in CUSTOMER_CODE_ALPHABET:
            raise ValueError('Codice cliente non valido.')
        value = value * base + (ord(char) - ord('a'))
    return value


def int_to_customer_code(value: int) -> str:
    """Converte un valore intero nel corrispondente codice cliente alfabetico."""
    if not 0 <= value < MAX_CUSTOMER_CODES:
        raise ValueError('Valore codice cliente fuori intervallo.')

    base = len(CUSTOMER_CODE_ALPHABET)
    chars = ['a'] * CUSTOMER_CODE_LENGTH
    for index in range(CUSTOMER_CODE_LENGTH - 1, -1, -1):
        chars[index] = chr(ord('a') + (value % base))
        value //= base
    return ''.join(chars)


def generate_next_customer_code(db: sqlite3.Connection) -> str:
    """Calcola il prossimo codice cliente disponibile usando l'ordinamento alfabetico."""
    row = db.execute(
        'SELECT code FROM customers '
        "WHERE code IS NOT NULL AND code != '' ORDER BY code DESC LIMIT 1"
    ).fetchone()
    if row is None or not row['code']:
        return int_to_customer_code(0)

    current_value = customer_code_to_int(row['code'])
    next_value = current_value + 1
    if next_value >= MAX_CUSTOMER_CODES:
        raise ValueError('Limite massimo per i codici cliente raggiunto.')
    return int_to_customer_code(next_value)


__all__ = [
    'CUSTOMER_CODE_ALPHABET',
    'CUSTOMER_CODE_LENGTH',
    'MAX_CUSTOMER_CODES',
    'customer_code_to_int',
    'int_to_customer_code',
    'generate_next_customer_code',
]
