-- Remappa gli stati delle riparazioni esistenti ai nuovi valori.
BEGIN TRANSACTION;

UPDATE tickets
SET repair_status = 'diagnosticato'
WHERE repair_status = 'accettazione';

UPDATE tickets
SET repair_status = 'preventivo_pronto'
WHERE repair_status = 'preventivo';

-- Il valore "preventivo_accettato" è mantenuto ma lo normalizziamo comunque.
UPDATE tickets
SET repair_status = 'preventivo_accettato'
WHERE repair_status = 'preventivo_accettato';

UPDATE tickets
SET repair_status = 'intervento_completato'
WHERE repair_status IN ('pronta', 'riconsegnata');

-- Aggiorna anche lo storico per riflettere le nuove etichette leggibili.
UPDATE ticket_history
SET old_value = 'Diagnosticato'
WHERE field = 'repair_status' AND old_value = 'Accettazione';

UPDATE ticket_history
SET new_value = 'Diagnosticato'
WHERE field = 'repair_status' AND new_value = 'Accettazione';

UPDATE ticket_history
SET old_value = 'Preventivo pronto'
WHERE field = 'repair_status' AND old_value = 'Preventivo';

UPDATE ticket_history
SET new_value = 'Preventivo pronto'
WHERE field = 'repair_status' AND new_value = 'Preventivo';

UPDATE ticket_history
SET old_value = 'Preventivo accettato'
WHERE field = 'repair_status' AND old_value = 'Preventivo accettato';

UPDATE ticket_history
SET new_value = 'Preventivo accettato'
WHERE field = 'repair_status' AND new_value = 'Preventivo accettato';

UPDATE ticket_history
SET old_value = 'Intervento completato'
WHERE field = 'repair_status' AND old_value IN ('Pronta', 'Riconsegnata');

UPDATE ticket_history
SET new_value = 'Intervento completato'
WHERE field = 'repair_status' AND new_value IN ('Pronta', 'Riconsegnata');

COMMIT;
