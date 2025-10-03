# Gestionale a Ticket per Interventi Tecnici

Questo progetto è un semplice gestionale a ticket pensato per officine o centri di assistenza che devono tracciare interventi tecnici, anagrafiche dei clienti e lo stato delle riparazioni.  L'applicazione è stata pensata per essere facile da installare e utilizzare: si basa su **Python** con il micro‑framework **Flask** e utilizza **SQLite** come database locale.

## Funzionalità principali

- **Anagrafica clienti:** memorizza i dati anagrafici di ciascun cliente (nome, email, telefono, indirizzo) in modo da poterli richiamare rapidamente quando si crea un ticket【212499813267287†L162-L169】.
- **Gestione dei ticket:** permette di aprire nuovi ticket, associare un cliente al ticket, inserire l’oggetto e la descrizione del problema, e aggiornarne lo stato (es. aperto, in lavorazione, risolto)【212499813267287†L150-L159】. Ogni ticket è identificato da un numero univoco e registra automaticamente la data di apertura【395316353871554†L139-L147】.
- **Tracciamento delle riparazioni:** per interventi su hardware o dispositivi, è possibile registrare i dettagli della riparazione (prodotto, problema riscontrato, date di consegna/ritiro, ecc.) e aggiornare lo stato della riparazione (diagnosticato, preventivo pronto, preventivo accettato, intervento completato).
- **Interfaccia web semplice:** l’applicazione fornisce pagine HTML con moduli per inserire e modificare dati e tabelle per visualizzare l’elenco di clienti, ticket e riparazioni.  In futuro è possibile espanderla con funzionalità di ricerca, assegnazione a tecnici specifici o invio di email ai clienti.

## Requisiti

- Python 3.8 o superiore
- [Flask](https://flask.palletsprojects.com/) – la libreria è elencata nel file `requirements.txt` e può essere installata con `pip`.

## Installazione

1. Clonare o copiare questo repository in una cartella sul proprio computer.
2. Creare ed attivare un ambiente virtuale (opzionale ma consigliato):

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # su Windows usare `venv\Scripts\activate`
   ```

3. Installare le dipendenze:

   ```bash
   pip install -r requirements.txt
   ```

4. Inizializzare il database.  La prima volta che si avvia l’applicazione verrà creato automaticamente il file `database.db` con le tabelle necessarie, ma è anche possibile eseguire manualmente lo script SQL:

   ```bash
   sqlite3 database.db < schema.sql
   ```

5. Avviare l’applicazione Flask:

   ```bash
   flask --app app.py run --reload
   ```

   Per impostazione predefinita l’applicazione è disponibile all’indirizzo `http://127.0.0.1:5000/`.

### Aggiornamento degli stati di riparazione esistenti

Se stai aggiornando un database già in uso, esegui lo script nella cartella `migrations/` per rimappare i vecchi stati (`accettazione`, `preventivo`, `pronta`, `riconsegnata`, ecc.) sui nuovi valori.  Questo evita discrepanze tra i dati salvati e le nuove opzioni disponibili nell’interfaccia.

```bash
sqlite3 database.db < migrations/202405_update_repair_statuses.sql
```

## Struttura del progetto

- `app.py` – contiene il codice dell’applicazione Flask, le rotte e la logica di business.
- `database.py` – funzioni di utilità per ottenere la connessione al database e inizializzare lo schema.
- `schema.sql` – definizione delle tabelle SQLite per clienti, ticket e riparazioni.
- `templates/` – directory con i template HTML Jinja2.
- `static/style.css` – foglio di stile di base per la grafica dell’interfaccia.
- `requirements.txt` – elenco dei pacchetti Python necessari.

## Test manuali consigliati

Per verificare la corretta gestione dei campi obbligatori nella creazione di una riparazione:

1. Avvia l’applicazione con `flask --app app.py run --reload`.
2. Visita la pagina **Nuova riparazione** (`/repairs/new`) e prova a inviare il modulo senza compilare *Prodotto* o *Descrizione problema*; il browser blocca l’invio e mostra un messaggio di validazione HTML5.
3. (Opzionale) Rimuovi temporaneamente gli attributi `required` dal modulo tramite gli strumenti di sviluppo del browser e ripeti l’invio con campi vuoti: l’applicazione visualizza messaggi di errore e non registra la riparazione.

## Espansioni possibili

Questo gestionale è pensato come base da cui partire.  Alcune idee per evolverlo:

- Implementare l’autenticazione per gli operatori (login e autorizzazioni).
- Aggiungere la gestione dei tecnici e l’assegnazione dei ticket a persone specifiche【212499813267287†L170-L176】.
- Integrare funzioni di ricerca e filtri avanzati per lo stato dei ticket o la cronologia dei clienti.
- Esportare report e statistiche sui tempi di risoluzione, volume di ticket e prestazioni degli operatori【395316353871554†L210-L276】.
- Inviare notifiche automatiche via email quando cambia lo stato di un ticket o una riparazione.

Con questo progetto si ha una base funzionante che può essere adattata alle esigenze specifiche del proprio contesto.