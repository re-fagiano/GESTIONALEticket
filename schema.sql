-- Schema per il gestionale a ticket.

-- Tabella clienti.  Ogni cliente ha un identificativo univoco e dati anagrafici.
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT
);

-- Tabella ticket.  Un ticket è associato a un cliente e contiene
-- informazioni sul problema, lo stato e le date di creazione/aggiornamento.
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'accettazione'
        CHECK (status IN ('accettazione', 'preventivo', 'riparato', 'chiuso')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- Tabella riparazioni.  Una riparazione fa riferimento a un ticket e
-- memorizza informazioni dettagliate sull'intervento e il suo stato.
CREATE TABLE IF NOT EXISTS repairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    product TEXT,
    issue_description TEXT,
    repair_status TEXT NOT NULL DEFAULT 'pending',
    date_received DATE,
    date_repaired DATE,
    date_returned DATE,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);