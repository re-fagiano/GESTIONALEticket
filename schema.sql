
-- Tabella utenti per la gestione dell'autenticazione e dei ruoli.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella clienti.  Ogni cliente ha un identificativo univoco e dati anagrafici.
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
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
    status TEXT NOT NULL DEFAULT 'open',
    product TEXT,
    issue_description TEXT,
    payment_info TEXT,
    repair_status TEXT NOT NULL DEFAULT 'accettazione',
    date_received DATE,
    date_repaired DATE,
    date_returned DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    last_modified_by INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (last_modified_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Storico delle modifiche ai ticket per garantire la tracciabilità completa.
CREATE TABLE IF NOT EXISTS ticket_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by INTEGER,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Allegati associati ai ticket. Conserva i metadati dei file caricati
-- (nome originale, nome su disco, tipo MIME, dimensione e autore).
CREATE TABLE IF NOT EXISTS ticket_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    content_type TEXT,
    file_size INTEGER,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by INTEGER,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ticket_attachments_ticket_id
    ON ticket_attachments(ticket_id);

-- Gestione del magazzino. Ogni articolo ha un codice univoco, un nome,
-- una descrizione facoltativa e informazioni di inventario.
CREATE TABLE IF NOT EXISTS inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    minimum_quantity INTEGER NOT NULL DEFAULT 0,
    location TEXT,
    category TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inventory_items_name
    ON inventory_items(name);

-- Dati iniziali di magazzino.
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('215443', 'maurizia', 'cane di legno', 2, 0, 'P1', 'nope', 'Prezzo unitario: 896.00 €. Valore totale: 1792.00 €');
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215284', 'pompa siltal', 'pompa scarico SL', 1, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215223', 'pompa siltal', 'pompa siltal', 1, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215134', 'pompa siltal', 'pompa siltal', 1, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215242', 'pompa siltal', 'pompa siltal', 1, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215285', 'pompa siltal', 'pompa siltal', 5, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('PMP006AC', 'pompa ASC BK', 'pompa ASC BK', 2, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('PMP010AC', 'pompa ASC BK', 'pompa ASC BK', 4, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215475', 'POMPA 30 W WH', 'POMPA SCARICO HANYU', 1, 0, 'P01', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215299', 'POMPA AEG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215342', 'POMPA SCARICO AEG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215287', 'POMPA SCARICO AEG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215213', 'POMPA SCARICO SG', 'POMPA SCARICO', 2, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('D422133', 'POMPA SCARICO AEG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215133', 'POMPA SCARICO CY', '49001618', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215629', 'POMPA SCARICO SM SG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215373', 'POMPA SCARICO SG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215266', 'POMPA SCARICO SG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215244', 'POMPA SCARICO SM', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215112', 'POMPA SCARICO SM', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215368', 'POMPA SCARICO SM', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215422', 'POMPA SCARICO LG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215423', 'POMPA SCARICO SAMSUNG', 'POMPA SCARICO', 1, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215446', 'POMPA SCARICO SM', 'POMPA SCARICO', 2, 0, 'P02', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215214', 'POMPA SCARICO ARDO', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00214114', 'POMPA SCARICO ARDO', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215460', 'POMPA SCARICO ARDO', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215459', 'POMPA SCARICO ARDO', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215395', 'POMPA SCARICO ARDO', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('00215479', 'POMPA SCARICO VESTEL', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('PMP006MI', 'POMPA SCARICO MIELE', 'POMPA SCARICO', 1, 0, 'P03', NULL, NULL);
INSERT OR IGNORE INTO inventory_items (code, name, description, quantity, minimum_quantity, location, category, notes)
VALUES ('0024000406A', 'POMPA SCARICO HAIER', 'POMPA SCARICO', 2, 0, 'P03', NULL, NULL);
