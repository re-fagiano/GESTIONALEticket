-- Migrazione per aggiornare gli stati dei ticket ai nuovi valori introdotti
-- nel 2024-02-17.  Eseguire questo script dopo aver aggiornato l'applicazione
-- per convertire i valori legacy ed evitare dati inconsistenti.

BEGIN TRANSACTION;

UPDATE tickets SET status = 'accettazione'
WHERE status IN ('open', 'aperto');

UPDATE tickets SET status = 'preventivo'
WHERE status IN ('in_progress', 'processing', 'preventivo');

UPDATE tickets SET status = 'riparato'
WHERE status IN ('repaired', 'riparato');

UPDATE tickets SET status = 'chiuso'
WHERE status IN ('closed', 'chiuso');

COMMIT;
