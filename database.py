"""
Utility per la gestione della connessione al database SQLite.

Queste funzioni permettono di ottenere una connessione condivisa all'interno
della richiesta Flask (usando `g`), di inizializzare lo schema e di chiudere
automaticamente la connessione al termine della richiesta.
"""

import sqlite3
from flask import current_app, g
from pathlib import Path


def get_db():
    """Restituisce una connessione al database, creandola se necessario.

    La connessione è memorizzata nell'oggetto `g` (contesto di Flask) per
    evitare di aprire più connessioni nella stessa richiesta. Le righe
    risultanti verranno restituite come oggetti tipo dizionario per un
    accesso più comodo ai campi.
    """
    if 'db' not in g:
        # Ottiene il percorso del database dal contesto dell'app o usa il default
        db_path = current_app.config.get('DATABASE', 'database.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(e=None):
    """Chiude la connessione al database se presente nel contesto g."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Inizializza il database eseguendo lo script SQL contenuto in `schema.sql`.

    Se il database non esiste, viene creato automaticamente.  Questa funzione
    può essere richiamata all'avvio dell'applicazione per assicurarsi che
    esistano le tabelle necessarie.
    """
    db = get_db()
    schema_path = Path(current_app.root_path) / 'schema.sql'
    # Usa open_resource per aprire file relativi al package Flask, ma in questo
    # caso usiamo schema_path per maggiore chiarezza.
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    db.executescript(sql_script)

    # Migrazioni leggere per colonne aggiunte dopo il rilascio iniziale.
    def _column_exists(table: str, column: str) -> bool:
        rows = db.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row[1] == column for row in rows)

    if not _column_exists('tickets', 'created_by'):
        db.execute('ALTER TABLE tickets ADD COLUMN created_by INTEGER')
    if not _column_exists('tickets', 'last_modified_by'):
        db.execute('ALTER TABLE tickets ADD COLUMN last_modified_by INTEGER')
    if not _column_exists('tickets', 'payment_info'):
        db.execute('ALTER TABLE tickets ADD COLUMN payment_info TEXT')

    # Garantisce la presenza della tabella di storico modifiche.
    db.execute(
        'CREATE TABLE IF NOT EXISTS ticket_history ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'ticket_id INTEGER NOT NULL, '
        'field TEXT NOT NULL, '
        'old_value TEXT, '
        'new_value TEXT, '
        'changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
        'changed_by INTEGER, '
        'FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE, '
        'FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL'
        ')'
    )

    db.commit()
