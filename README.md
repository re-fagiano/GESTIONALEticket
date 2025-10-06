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

## Configurare le risposte dell'AI

Il pulsante **Chiedi all’AI** invia una richiesta POST all’endpoint `/ai/suggest`. L’applicazione, a sua volta, inoltra i dettagli del ticket a un servizio esterno o a OpenAI per ottenere un consiglio tecnico sintetico e professionale. È possibile configurare l’integrazione in due modi:

1. **Variabili d’ambiente** – impostare i parametri prima di avviare Flask:

   ```bash
   export AI_SUGGESTION_ENDPOINT="https://example.com/api/suggest"
   export AI_SUGGESTION_TOKEN="il-tuo-token-opzionale"
   export AI_SUGGESTION_TIMEOUT=20  # secondi, opzionale
   flask --app app.py run --reload
   ```

2. **File di configurazione** – creare `instance/config.py` (la cartella viene generata automaticamente al primo avvio) con i valori desiderati:

   ```python
   AI_SUGGESTION_ENDPOINT = "https://example.com/api/suggest"
   AI_SUGGESTION_TOKEN = "il-tuo-token-opzionale"
   AI_SUGGESTION_TIMEOUT = 20
   ```

### Utilizzare direttamente OpenAI

Se preferisci sfruttare l’API di OpenAI (chiave in formato `sk-...`) senza dover esporre un servizio intermedio, imposta il provider `openai`. L’applicazione invierà ai modelli di OpenAI il contesto del ticket accompagnato da un prompt di sistema che li istruisce ad agire come "un tecnico di elettrodomestici esperto che fa diagnosi in maniera sintetica e professionale".

```bash
export AI_SUGGESTION_PROVIDER=openai
export AI_SUGGESTION_TOKEN="sk-..."
# facoltativo: esporta OPENAI_API_KEY se preferisci non usare AI_SUGGESTION_TOKEN
# export OPENAI_API_KEY="sk-..."
# facoltativo: scegli un altro modello supportato (es. gpt-4o-mini)
# export AI_SUGGESTION_OPENAI_MODEL="gpt-4o-mini"
flask --app app.py run --reload
```

È possibile personalizzare il messaggio di sistema impostando `AI_SUGGESTION_SYSTEM_PROMPT` via variabile d’ambiente o nel file `instance/config.py`. In questo modo potrai adattare il tono delle risposte alle tue esigenze.

### Payload per servizi personalizzati

Se utilizzi un endpoint personalizzato, il servizio riceve un payload come questo:

```json
{
  "target": "issue_description",
  "subject": "Notebook HP",
  "product": "HP ProBook 450",
  "issue_description": "Schermo che lampeggia in modo intermittente",
  "description": "Il cliente segnala che il problema si presenta dopo qualche minuto di utilizzo.",
  "requested_by": "nome_utente"
}
```

La risposta deve restituire un campo `suggestion`, ad esempio:

```json
{
  "suggestion": "Verificare i driver della scheda video e testare con un monitor esterno." 
}
```

Se l’endpoint non è configurato l’applicazione mostra l’errore “Servizio AI non configurato”.

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

## Pubblicazione su un sito web esistente

L’applicazione è sviluppata con Flask e necessita quindi di un server che possa eseguire codice Python lato backend.  Non può essere caricata direttamente come una semplice pagina HTML statica: per integrarla nel tuo sito devi ospitarla su un servizio che permetta processi Python (ad esempio un VPS, un servizio PaaS come Heroku/Render, oppure un server aziendale interno) e poi collegare il dominio del tuo sito all’istanza dell’applicazione tramite proxy o iframe.【F:app.py†L37-L82】

Una configurazione tipica prevede:

1. Distribuire il codice su un server con Python installato.
2. Installare le dipendenze (`pip install -r requirements.txt`) e inizializzare il database come descritto sopra.
3. Eseguire l’app con un application server (es. `gunicorn "app:create_app()"`) dietro a un reverse proxy Nginx/Apache che risponde al tuo dominio.
4. Collegare dal sito principale un link o un iframe all’indirizzo pubblico dell’applicazione.

Se il tuo sito è ospitato su un provider che offre solo hosting statico (solo HTML/CSS/JS), dovrai affiancare al sito una soluzione separata per il backend e poi integrare l’interfaccia del gestionale tramite link o embed.

## Backup di database e allegati

Il database predefinito è un file SQLite chiamato `database.db` nella cartella principale del progetto.  Gli allegati caricati nei ticket vengono salvati nella cartella `instance/uploads/`, con una sottocartella per ogni ticket, percorso configurabile tramite la variabile `UPLOAD_FOLDER` nell’applicazione.【F:app.py†L37-L118】

Per eseguire un backup completo puoi:

1. Fermare l’applicazione (o assicurarti che non stia scrivendo dati) per evitare file parziali.
2. Copiare il file `database.db` e l’intera cartella `instance/uploads/` in una destinazione sicura (ad esempio un disco esterno, un NAS o un archivio cloud).
3. Ripetere l’operazione periodicamente o automatizzarla con uno script/cron job.

Su sistemi Linux puoi utilizzare un semplice script bash:

```bash
#!/bin/bash
set -euo pipefail
DATA=$(date +%Y%m%d_%H%M)
DEST="/percorso/del/backup/$DATA"
mkdir -p "$DEST"
cp -a database.db "$DEST/"
cp -a instance/uploads "$DEST/uploads"
```

In questo modo manterrai una copia aggiornata sia dei dati strutturati sia dei documenti allegati ai ticket.