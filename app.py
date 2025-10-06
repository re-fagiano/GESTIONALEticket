"""
Applicazione Flask per il gestionale a ticket.

Questo modulo definisce le varie rotte dell'applicazione, gestisce la
connessione al database tramite le funzioni di `database.py` e fornisce
funzionalità per la gestione di clienti, ticket e riparazioni.
"""

import os
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify

from database import get_db, init_db, close_db
from flask_login import current_user, login_required

from auth import admin_required, bp as auth_bp, login_manager
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


TICKET_STATUSES = [
    ("open", "Aperto"),
    ("in_progress", "In lavorazione"),
    ("closed", "Chiuso"),
]
TICKET_STATUS_LABELS = {value: label for value, label in TICKET_STATUSES}
TICKET_STATUS_VALUES = set(TICKET_STATUS_LABELS)
DEFAULT_TICKET_STATUS = TICKET_STATUSES[0][0]

REPAIR_STATUSES = [
    ("accettazione", "Accettazione"),
    ("diagnosticato", "Diagnosticato"),
    ("preventivo_pronto", "Preventivo pronto"),
    ("preventivo_accettato", "Preventivo accettato"),
    ("intervento_completato", "Intervento completato"),
]
REPAIR_STATUS_LABELS = {value: label for value, label in REPAIR_STATUSES}
REPAIR_STATUS_VALUES = set(REPAIR_STATUS_LABELS)
DEFAULT_REPAIR_STATUS = REPAIR_STATUSES[0][0]


def _extract_openai_responses_text(data: dict) -> str:
    """Estrae il testo utile dalla risposta dell'endpoint /responses di OpenAI."""

    fragments: List[str] = []

    def _push(value: Optional[str]) -> None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                fragments.append(stripped)

    output = data.get('output')
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue

            _push(item.get('text'))
            _push(item.get('output_text'))

            content = item.get('content')
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_type = (block.get('type') or '').lower()
                        if block_type in {'output_text', 'text'}:
                            _push(block.get('text'))
                        elif block_type == 'message':
                            _push(block.get('content'))
                        elif block_type == 'input_text':
                            nested = block.get('content')
                            if isinstance(nested, list):
                                for nested_block in nested:
                                    if isinstance(nested_block, dict):
                                        _push(nested_block.get('text') or nested_block.get('content'))
                                    else:
                                        _push(str(nested_block))
                            else:
                                _push(nested)
                        else:
                            _push(block.get('content'))
                    else:
                        _push(str(block))
            else:
                _push(content)

    _push(data.get('output_text'))

    return '\n'.join(fragments).strip()


def _build_ai_prompts(
    system_prompt: Optional[str],
    subject: str,
    product: str,
    issue_description: str,
    description: str,
) -> Tuple[str, str]:
    """Costruisce il prompt di sistema e dell'utente per i suggerimenti AI."""

    effective_system_prompt = (
        system_prompt
        or 'Sei un tecnico di elettrodomestici esperto. '
        'Fornisci diagnosi sintetiche e professionali in italiano '
        'sulla base delle informazioni del ticket.'
    )

    details: List[str] = []
    if subject:
        details.append(f"Oggetto: {subject}")
    if product:
        details.append(f"Prodotto: {product}")
    if issue_description:
        details.append(f"Problema segnalato: {issue_description}")
    if description:
        details.append(f"Dettagli aggiuntivi: {description}")
    if not details:
        details.append('Non sono disponibili informazioni aggiuntive.')

    user_prompt = (
        'Fornisci una diagnosi sintetica e professionale per il seguente ticket.'
        '\n' + '\n'.join(details)
    )

    return effective_system_prompt, user_prompt


TICKET_HISTORY_FIELD_LABELS = {
    '__created__': 'Creazione ticket',
    'status': 'Stato ticket',
    'product': 'Prodotto',
    'issue_description': 'Descrizione problema',
    'payment_info': 'Informazioni pagamento',
    'repair_status': 'Stato riparazione',
    'date_received': 'Data ricezione',
    'date_repaired': 'Data riparazione',
    'date_returned': 'Data consegna',
}


def create_app() -> Flask:
    """Factory per creare e configurare l'istanza di Flask."""
    app = Flask(__name__, instance_relative_config=True)
    # Configurazione di default caricata direttamente nell'applicazione
    app.config.from_mapping(
        SECRET_KEY='change-me-please',
        DATABASE=str(Path(app.root_path) / 'database.db'),
        UPLOAD_FOLDER=str(Path(app.instance_path) / 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        AI_SUGGESTION_ENDPOINT=None,
        AI_SUGGESTION_TOKEN=None,
        AI_SUGGESTION_TIMEOUT=15,
        AI_SUGGESTION_PROVIDER='generic',
        AI_SUGGESTION_SYSTEM_PROMPT=(
            'Sei un tecnico di elettrodomestici esperto. '
            'Fornisci diagnosi sintetiche e professionali in italiano '
            'sulla base delle informazioni del ticket.'
        ),
        AI_SUGGESTION_OPENAI_MODEL='gpt-3.5-turbo',
        AI_SUGGESTION_DEEPSEEK_MODEL='deepseek-chat',
        AI_SUGGESTION_DEEPSEEK_ENDPOINT='https://api.deepseek.com/v1/chat/completions',
    )

    # Consente di sovrascrivere i valori tramite instance/config.py
    app.config.from_pyfile('config.py', silent=True)

    # Le variabili d'ambiente hanno la precedenza finale
    if 'AI_SUGGESTION_ENDPOINT' in os.environ:
        app.config['AI_SUGGESTION_ENDPOINT'] = os.environ['AI_SUGGESTION_ENDPOINT']
    if 'AI_SUGGESTION_TOKEN' in os.environ:
        app.config['AI_SUGGESTION_TOKEN'] = os.environ['AI_SUGGESTION_TOKEN']
    if 'AI_SUGGESTION_TIMEOUT' in os.environ:
        try:
            app.config['AI_SUGGESTION_TIMEOUT'] = int(os.environ['AI_SUGGESTION_TIMEOUT'])
        except (TypeError, ValueError):
            pass
    if 'AI_SUGGESTION_PROVIDER' in os.environ:
        app.config['AI_SUGGESTION_PROVIDER'] = os.environ['AI_SUGGESTION_PROVIDER']
    if 'AI_SUGGESTION_SYSTEM_PROMPT' in os.environ:
        app.config['AI_SUGGESTION_SYSTEM_PROMPT'] = os.environ['AI_SUGGESTION_SYSTEM_PROMPT']
    if 'AI_SUGGESTION_OPENAI_MODEL' in os.environ:
        app.config['AI_SUGGESTION_OPENAI_MODEL'] = os.environ['AI_SUGGESTION_OPENAI_MODEL']
    if 'AI_SUGGESTION_DEEPSEEK_MODEL' in os.environ:
        app.config['AI_SUGGESTION_DEEPSEEK_MODEL'] = os.environ['AI_SUGGESTION_DEEPSEEK_MODEL']
    if 'AI_SUGGESTION_DEEPSEEK_ENDPOINT' in os.environ:
        app.config['AI_SUGGESTION_DEEPSEEK_ENDPOINT'] = os.environ['AI_SUGGESTION_DEEPSEEK_ENDPOINT']

    # Garantisce che le directory per i file di istanza e gli upload esistano.
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

    login_manager.init_app(app)

    # Chiude la connessione al database alla fine di ogni richiesta
    @app.teardown_appcontext
    def _close_database(exception: Optional[BaseException] = None):
        close_db(exception)

    # Inizializza il database una volta all’avvio utilizzando il contesto dell’applicazione.
    # In Flask 3.x il decorator before_first_request non è più disponibile.
    with app.app_context():
        init_db()

    app.register_blueprint(auth_bp)


    def _store_ticket_attachments(
        ticket_id: int,
        files: Iterable[FileStorage],
        uploaded_by: Optional[int],
    ) -> Tuple[int, List[str]]:
        """Salva gli allegati ricevuti per un ticket restituendo numero e errori."""

        saved = 0
        errors: List[str] = []
        upload_root = Path(app.config['UPLOAD_FOLDER'])
        upload_root.mkdir(parents=True, exist_ok=True)
        ticket_folder = upload_root / str(ticket_id)
        ticket_folder.mkdir(parents=True, exist_ok=True)

        db = get_db()

        for storage in files:
            if storage is None:
                continue
            original_filename = (storage.filename or '').strip()
            if not original_filename:
                continue

            safe_name = secure_filename(original_filename)
            if not safe_name:
                errors.append(
                    f'Impossibile caricare il file "{original_filename}": nome non valido.'
                )
                continue

            extension = Path(safe_name).suffix
            stored_filename = f"{uuid.uuid4().hex}{extension}"
            destination = ticket_folder / stored_filename

            try:
                storage.save(destination)
            except Exception:
                errors.append(
                    f'Errore durante il salvataggio del file "{original_filename}".'
                )
                if destination.exists():
                    destination.unlink()
                continue

            file_size = destination.stat().st_size
            db.execute(
                'INSERT INTO ticket_attachments ('
                'ticket_id, original_filename, stored_filename, content_type, file_size, uploaded_by'
                ') VALUES (?, ?, ?, ?, ?, ?)',
                (
                    ticket_id,
                    original_filename,
                    stored_filename,
                    storage.mimetype or None,
                    file_size,
                    uploaded_by,
                ),
            )
            saved += 1

        return saved, errors


    def _delete_ticket_record(ticket_id: int) -> Tuple[bool, Optional[str]]:
        """Elimina il ticket specificato restituendo l'esito e l'oggetto."""
        db = get_db()
        ticket = db.execute(
            'SELECT subject FROM tickets WHERE id = ?',
            (ticket_id,),
        ).fetchone()
        if ticket is None:
            return False, None
        db.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
        db.commit()
        return True, ticket['subject']


    # Rotta principale: mostra un riepilogo dei conteggi
    @app.route('/')
    @login_required
    def index():
        db = get_db()
        ticket_count = db.execute('SELECT COUNT(*) AS count FROM tickets').fetchone()['count']
        customer_count = db.execute('SELECT COUNT(*) AS count FROM customers').fetchone()['count']
        repair_count = db.execute(
            'SELECT COUNT(*) AS count FROM tickets '
            'WHERE product IS NOT NULL OR issue_description IS NOT NULL'
        ).fetchone()['count']
        return render_template('index.html', ticket_count=ticket_count,
                               customer_count=customer_count, repair_count=repair_count)

    @app.route('/admin/users')
    @admin_required
    def admin_users():
        db = get_db()
        users = db.execute(
            'SELECT id, username, role, created_at FROM users ORDER BY username'
        ).fetchall()
        return render_template('admin_users.html', users=users)

    @app.route('/admin/users/<int:user_id>/promote', methods=['POST'])
    @admin_required
    def promote_user(user_id: int):
        db = get_db()
        user = db.execute(
            'SELECT id, username, role FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()

        if user is None:
            flash('Utente non trovato.', 'error')
        elif user['role'] == 'admin':
            flash(f"L'utente \"{user['username']}\" è già un amministratore.", 'info')
        else:
            db.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
            db.commit()
            flash(
                f"L'utente \"{user['username']}\" è stato promosso ad amministratore.",
                'success',
            )

        return redirect(url_for('admin_users'))

    # Lista clienti
    @app.route('/customers')
    @login_required
    def customers():
        db = get_db()
        customers = db.execute('SELECT * FROM customers ORDER BY name').fetchall()
        return render_template('customers.html', customers=customers)

    @app.route('/customers/<int:customer_id>/delete', methods=['POST'])
    @admin_required
    def delete_customer(customer_id: int):
        db = get_db()
        customer = db.execute(
            'SELECT name FROM customers WHERE id = ?',
            (customer_id,),
        ).fetchone()
        if customer is None:
            flash('Cliente non trovato.', 'error')
        else:
            db.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
            db.commit()
            customer_name = customer['name']
            if customer_name:
                flash(f'Cliente "{customer_name}" eliminato con successo.', 'success')
            else:
                flash('Cliente eliminato con successo.', 'success')
        return redirect(url_for('customers'))

    # Inserimento nuovo cliente
    @app.route('/customers/new', methods=['GET', 'POST'])
    @admin_required
    def add_customer():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            if not name:
                flash('Il nome è obbligatorio.', 'error')
            else:
                db = get_db()
                db.execute(
                    'INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)',
                    (name, email or None, phone or None, address or None)
                )
                db.commit()
                flash('Cliente aggiunto con successo.', 'success')
                return redirect(url_for('customers'))
        return render_template('add_customer.html')

    # Lista ticket
    @app.route('/tickets')
    @login_required
    def tickets():
        db = get_db()
        selected_status = request.args.get('status', '').strip()
        query = (
            'SELECT t.*, c.name AS customer_name '
            'FROM tickets t JOIN customers c ON t.customer_id = c.id '
        )
        params = ()
        if selected_status:
            if selected_status in TICKET_STATUS_VALUES:
                query += 'WHERE t.status = ? '
                params = (selected_status,)
            else:
                selected_status = None
        query += 'ORDER BY t.created_at DESC'
        tickets = db.execute(query, params).fetchall()
        current_filters = {'status': selected_status} if selected_status else {}
        return render_template(
            'tickets.html',
            tickets=tickets,
            statuses=TICKET_STATUSES,
            ticket_status_labels=TICKET_STATUS_LABELS,
            selected_status=selected_status,
            current_filters=current_filters,
        )

    @app.route('/tickets/<int:ticket_id>/delete', methods=['POST'])
    @admin_required
    def delete_ticket(ticket_id: int):
        deleted, subject = _delete_ticket_record(ticket_id)
        if not deleted:
            flash('Ticket non trovato.', 'error')
        else:
            if subject:
                flash(f'Ticket "{subject}" eliminato con successo.', 'success')
            else:
                flash('Ticket eliminato con successo.', 'success')

        allowed_filters = {'status'}
        filters = {
            key[len('filter_'):]: value
            for key, value in request.form.items()
            if key.startswith('filter_') and value
        }
        filters = {key: value for key, value in filters.items() if key in allowed_filters}
        redirect_url = url_for('tickets', **filters) if filters else url_for('tickets')
        return redirect(redirect_url)

    # Inserimento nuovo ticket
    @app.route('/tickets/new', methods=['GET', 'POST'])
    @login_required
    def add_ticket():
        db = get_db()
        if request.method == 'POST':
            current_user_id = int(current_user.id)
            customer_id = request.form.get('customer_id')
            subject = request.form.get('subject', '').strip()
            description = request.form.get('description', '').strip()
            ticket_status = request.form.get('ticket_status', DEFAULT_TICKET_STATUS)
            if ticket_status not in TICKET_STATUS_VALUES:
                ticket_status = DEFAULT_TICKET_STATUS
            product = request.form.get('product', '').strip()
            issue_description = request.form.get('issue_description', '').strip()
            payment_info = request.form.get('payment_info', '').strip()
            repair_status = request.form.get('repair_status', DEFAULT_REPAIR_STATUS)
            if repair_status not in REPAIR_STATUS_VALUES:
                repair_status = DEFAULT_REPAIR_STATUS
            date_received = request.form.get('date_received') or None
            date_repaired = request.form.get('date_repaired') or None
            date_returned = request.form.get('date_returned') or None
            if not customer_id or not subject:
                flash('Cliente e oggetto sono obbligatori.', 'error')
            else:
                cursor = db.execute(
                    'INSERT INTO tickets ('
                    'customer_id, subject, description, status, product, issue_description, payment_info, '
                    'repair_status, date_received, date_repaired, date_returned, created_by, last_modified_by'
                    ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        customer_id,
                        subject,
                        description or None,
                        ticket_status,
                        product or None,
                        issue_description or None,
                        payment_info or None,
                        repair_status,
                        date_received,
                        date_repaired,
                        date_returned,
                        current_user_id,
                        current_user_id,
                    )
                )
                ticket_id = cursor.lastrowid
                initial_status_label = TICKET_STATUS_LABELS.get(
                    ticket_status, ticket_status
                )
                db.execute(
                    'INSERT INTO ticket_history (ticket_id, field, old_value, new_value, changed_by) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (
                        ticket_id,
                        '__created__',
                        None,
                        f'Ticket creato (stato iniziale: {initial_status_label})',
                        current_user_id,
                    ),
                )
                files = request.files.getlist('attachments')
                saved_attachments, attachment_errors = _store_ticket_attachments(
                    ticket_id,
                    files,
                    current_user_id,
                )
                for error in attachment_errors:
                    flash(error, 'error')
                db.commit()
                success_message = 'Ticket creato con successo.'
                if saved_attachments:
                    success_message += f' {saved_attachments} allegato/i aggiunti.'
                flash(success_message, 'success')
                return redirect(url_for('tickets'))
        # Per GET (o se form incompleto), recupera elenco clienti per la select
        customers = db.execute('SELECT id, name FROM customers ORDER BY name').fetchall()
        return render_template(
            'add_ticket.html',
            customers=customers,
            repair_statuses=REPAIR_STATUSES,
            ticket_statuses=TICKET_STATUSES,
        )

    # Dettaglio ticket e aggiornamento stato
    @app.route('/tickets/<int:ticket_id>', methods=['GET', 'POST'])
    @login_required
    def ticket_detail(ticket_id: int):
        db = get_db()
        ticket = db.execute(
            'SELECT t.*, c.name AS customer_name, '
            'creator.username AS created_by_username, '
            'modifier.username AS last_modified_by_username '
            'FROM tickets t '
            'JOIN customers c ON t.customer_id = c.id '
            'LEFT JOIN users creator ON t.created_by = creator.id '
            'LEFT JOIN users modifier ON t.last_modified_by = modifier.id '
            'WHERE t.id = ?', (ticket_id,)
        ).fetchone()
        if ticket is None:
            flash('Ticket non trovato.', 'error')
            return redirect(url_for('tickets'))
        if request.method == 'POST':
            form_name = request.form.get('form_name', 'details')
            current_user_id = int(current_user.id)

            if form_name == 'attachments':
                files = request.files.getlist('attachments')
                saved_attachments, attachment_errors = _store_ticket_attachments(
                    ticket_id,
                    files,
                    current_user_id,
                )
                for error in attachment_errors:
                    flash(error, 'error')
                if saved_attachments:
                    db.commit()
                    success_message = (
                        'Allegato caricato con successo.'
                        if saved_attachments == 1
                        else 'Allegati caricati con successo.'
                    )
                    flash(success_message, 'success')
                elif not attachment_errors:
                    flash('Nessun file selezionato.', 'info')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))

            new_status = request.form.get('status', '').strip() or ticket['status']
            if new_status not in TICKET_STATUS_VALUES:
                flash('Stato del ticket non valido.', 'error')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))

            product = request.form.get('product', '').strip() or None
            issue_description = request.form.get('issue_description', '').strip() or None
            payment_info = request.form.get('payment_info', '').strip() or None
            repair_status = request.form.get(
                'repair_status',
                ticket['repair_status'] or DEFAULT_REPAIR_STATUS,
            )
            if repair_status not in REPAIR_STATUS_VALUES:
                repair_status = DEFAULT_REPAIR_STATUS
            date_received = request.form.get('date_received') or None
            date_repaired = request.form.get('date_repaired') or None
            date_returned = request.form.get('date_returned') or None

            tracked_fields = (
                'status',
                'product',
                'issue_description',
                'payment_info',
                'repair_status',
                'date_received',
                'date_repaired',
                'date_returned',
            )
            new_values = {
                'status': new_status,
                'product': product,
                'issue_description': issue_description,
                'payment_info': payment_info,
                'repair_status': repair_status,
                'date_received': date_received,
                'date_repaired': date_repaired,
                'date_returned': date_returned,
            }
            has_changes = any(
                (ticket[field] or '') != (new_values[field] or '') for field in tracked_fields
            )
            if not has_changes:
                flash('Nessuna modifica rilevata.', 'info')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))

            db.execute(
                'UPDATE tickets SET '
                'status = ?, product = ?, issue_description = ?, payment_info = ?, repair_status = ?, '
                'date_received = ?, date_repaired = ?, date_returned = ?, '
                'last_modified_by = ?, updated_at = CURRENT_TIMESTAMP '
                'WHERE id = ?',
                (
                    new_status,
                    product,
                    issue_description,
                    payment_info,
                    repair_status,
                    date_received,
                    date_repaired,
                    date_returned,
                    current_user_id,
                    ticket_id,
                ),
            )

            def _format_value(key: str, value):
                if value is None:
                    return None
                if key == 'status':
                    return TICKET_STATUS_LABELS.get(value, value)
                if key == 'repair_status':
                    return REPAIR_STATUS_LABELS.get(value, value)
                return str(value)

            for field in tracked_fields:
                old_raw = ticket[field]
                new_raw = new_values[field]
                if (old_raw or '') == (new_raw or ''):
                    continue

                db.execute(
                    'INSERT INTO ticket_history (ticket_id, field, old_value, new_value, changed_by) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (
                        ticket_id,
                        field,
                        _format_value(field, old_raw),
                        _format_value(field, new_raw),
                        current_user_id,
                    ),
                )
            db.commit()
            flash('Ticket aggiornato con successo.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))

        attachments = db.execute(
            'SELECT a.id, a.original_filename, a.stored_filename, a.content_type, a.file_size, '
            'a.uploaded_at, u.username AS uploaded_by_username '
            'FROM ticket_attachments a '
            'LEFT JOIN users u ON a.uploaded_by = u.id '
            'WHERE a.ticket_id = ? '
            'ORDER BY a.uploaded_at DESC, a.id DESC',
            (ticket_id,),
        ).fetchall()

        history_entries = db.execute(
            'SELECT h.field, h.old_value, h.new_value, h.changed_at, '
            'u.username AS changed_by_username '
            'FROM ticket_history h '
            'LEFT JOIN users u ON h.changed_by = u.id '
            'WHERE h.ticket_id = ? '
            'ORDER BY h.changed_at DESC, h.id DESC',
            (ticket_id,),
        ).fetchall()
        return render_template(
            'ticket_detail.html',
            ticket=ticket,
            ticket_statuses=TICKET_STATUSES,
            ticket_status_labels=TICKET_STATUS_LABELS,
            repair_statuses=REPAIR_STATUSES,
            repair_status_labels=REPAIR_STATUS_LABELS,
            history_entries=history_entries,
            attachments=attachments,
            ticket_history_field_labels=TICKET_HISTORY_FIELD_LABELS,
        )

    @app.route('/tickets/<int:ticket_id>/attachments/<int:attachment_id>/download')
    @login_required
    def download_ticket_attachment(ticket_id: int, attachment_id: int):
        db = get_db()
        attachment = db.execute(
            'SELECT id, original_filename, stored_filename, content_type '
            'FROM ticket_attachments WHERE id = ? AND ticket_id = ?',
            (attachment_id, ticket_id),
        ).fetchone()
        if attachment is None:
            flash('Allegato non trovato.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))

        file_path = Path(app.config['UPLOAD_FOLDER']) / str(ticket_id) / attachment['stored_filename']
        if not file_path.exists():
            flash('File allegato non trovato sul server.', 'error')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))

        return send_file(
            file_path,
            as_attachment=True,
            download_name=attachment['original_filename'],
            mimetype=attachment['content_type'] or 'application/octet-stream',
        )

    @app.route('/ai/suggest', methods=['POST'])
    @login_required
    def ai_suggest():
        if not request.is_json:
            return jsonify({'error': 'Richiesta non valida.'}), 400

        payload = request.get_json(silent=True) or {}
        target = (payload.get('target') or '').strip()
        if target != 'issue_description':
            return jsonify({'error': 'Campo non supportato.'}), 400

        subject = (payload.get('subject') or '').strip()
        product = (payload.get('product') or '').strip()
        issue_description = (payload.get('issue_description') or '').strip()
        description = (payload.get('description') or '').strip()

        if not any([subject, product, issue_description, description]):
            return jsonify({'error': 'Fornire almeno un dettaglio per generare un suggerimento.'}), 400

        provider = (app.config.get('AI_SUGGESTION_PROVIDER') or 'generic').lower()

        if provider == 'openai':
            api_key = (
                app.config.get('AI_SUGGESTION_TOKEN')
                or os.environ.get('OPENAI_API_KEY')
            )
            if not api_key:
                return jsonify({'error': 'API key OpenAI non configurata.'}), 503

            system_prompt, user_prompt = _build_ai_prompts(
                app.config.get('AI_SUGGESTION_SYSTEM_PROMPT'),
                subject,
                product,
                issue_description,
                description,
            )

            payload = {
                'model': app.config.get('AI_SUGGESTION_OPENAI_MODEL', 'gpt-3.5-turbo'),
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.2,
            }

            try:
                response = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}',
                    },
                    timeout=app.config.get('AI_SUGGESTION_TIMEOUT', 15),
                )
                response.raise_for_status()
            except requests.exceptions.Timeout:
                return jsonify({'error': 'Il servizio AI non ha risposto in tempo.'}), 504
            except requests.exceptions.RequestException:
                return jsonify({'error': 'Errore nella comunicazione con il servizio AI.'}), 502

            try:
                data = response.json()
            except ValueError:
                return jsonify({'error': 'Risposta non valida dal servizio AI.'}), 502

            if data.get('error'):
                message = data['error'].get('message') if isinstance(data['error'], dict) else str(data['error'])
                return jsonify({'error': message or 'Errore dal servizio OpenAI.'}), 502

            choices = data.get('choices') or []
            if not choices:
                return jsonify({'error': 'Nessun suggerimento disponibile dal servizio AI.'}), 502

            suggestion = (choices[0].get('message', {}).get('content') or '').strip()
        elif provider == 'deepseek':
            api_key = (
                app.config.get('AI_SUGGESTION_TOKEN')
                or os.environ.get('DEEPSEEK_API_KEY')
            )
            if not api_key:
                return jsonify({'error': 'API key DeepSeek non configurata.'}), 503

            system_prompt, user_prompt = _build_ai_prompts(
                app.config.get('AI_SUGGESTION_SYSTEM_PROMPT'),
                subject,
                product,
                issue_description,
                description,
            )

            payload = {
                'model': app.config.get('AI_SUGGESTION_DEEPSEEK_MODEL', 'deepseek-chat'),
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.2,
            }

            endpoint = (
                app.config.get('AI_SUGGESTION_DEEPSEEK_ENDPOINT')
                or 'https://api.deepseek.com/v1/chat/completions'
            )

            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}',
                    },
                    timeout=app.config.get('AI_SUGGESTION_TIMEOUT', 15),
                )
                response.raise_for_status()
            except requests.exceptions.Timeout:
                return jsonify({'error': 'Il servizio AI non ha risposto in tempo.'}), 504
            except requests.exceptions.RequestException:
                return jsonify({'error': 'Errore nella comunicazione con il servizio AI.'}), 502

            try:
                data = response.json()
            except ValueError:
                return jsonify({'error': 'Risposta non valida dal servizio AI.'}), 502

            if data.get('error'):
                message = data['error'].get('message') if isinstance(data['error'], dict) else str(data['error'])
                return jsonify({'error': message or 'Errore dal servizio DeepSeek.'}), 502

            choices = data.get('choices') or []
            if not choices:
                return jsonify({'error': 'Nessun suggerimento disponibile dal servizio AI.'}), 502

            suggestion = (choices[0].get('message', {}).get('content') or '').strip()
        else:
            endpoint = app.config.get('AI_SUGGESTION_ENDPOINT')
            if not endpoint:
                return jsonify({'error': 'Servizio AI non configurato.'}), 503

            headers = {'Content-Type': 'application/json'}
            token = app.config.get('AI_SUGGESTION_TOKEN')
            if token:
                headers['Authorization'] = f'Bearer {token}'

            external_payload = {
                'target': target,
                'subject': subject,
                'product': product,
                'issue_description': issue_description,
                'description': description,
                'requested_by': getattr(current_user, 'username', None),
            }

            try:
                response = requests.post(
                    endpoint,
                    json=external_payload,
                    headers=headers,
                    timeout=app.config.get('AI_SUGGESTION_TIMEOUT', 15),
                )
                response.raise_for_status()
            except requests.exceptions.Timeout:
                return jsonify({'error': 'Il servizio AI non ha risposto in tempo.'}), 504
            except requests.exceptions.RequestException:
                return jsonify({'error': 'Errore nella comunicazione con il servizio AI.'}), 502

            try:
                data = response.json()
            except ValueError:
                return jsonify({'error': 'Risposta non valida dal servizio AI.'}), 502

            suggestion = (data.get('suggestion') or data.get('content') or '').strip()
        if not suggestion:
            return jsonify({'error': 'Nessun suggerimento disponibile dal servizio AI.'}), 502

        return jsonify({'suggestion': suggestion})

    # Lista delle riparazioni
    @app.route('/repairs')
    @login_required
    def repairs():
        db = get_db()

        selected_status = request.args.get('status', '').strip() or None
        from_date = request.args.get('from_date', '').strip() or None
        to_date = request.args.get('to_date', '').strip() or None

        filters = ['(t.product IS NOT NULL OR t.issue_description IS NOT NULL)']
        params = []

        if selected_status and selected_status not in REPAIR_STATUS_VALUES:
            selected_status = None

        if selected_status:
            filters.append('t.repair_status = ?')
            params.append(selected_status)

        date_expression = 'DATE(COALESCE(t.date_returned, t.date_repaired, t.date_received, t.updated_at))'

        if from_date:
            filters.append(f"{date_expression} >= DATE(?)")
            params.append(from_date)

        if to_date:
            filters.append(f"{date_expression} <= DATE(?)")
            params.append(to_date)

        where_clause = ' WHERE ' + ' AND '.join(filters) if filters else ''

        query = (
            'SELECT t.*, c.name AS customer_name '
            'FROM tickets t '
            'JOIN customers c ON t.customer_id = c.id '
            f'{where_clause} '
            'ORDER BY COALESCE(t.date_returned, t.updated_at) DESC, t.id DESC'
        )
        repairs = db.execute(query, params).fetchall()

        current_filters = {
            'status': selected_status,
            'from_date': from_date,
            'to_date': to_date,
        }

        return render_template(
            'repairs.html',
            repairs=repairs,
            repair_status_labels=REPAIR_STATUS_LABELS,
            repair_statuses=REPAIR_STATUSES,
            current_filters=current_filters,
        )

    @app.route('/repairs/<int:ticket_id>/delete', methods=['POST'])
    @admin_required
    def delete_repair(ticket_id: int):
        deleted, subject = _delete_ticket_record(ticket_id)
        if not deleted:
            flash('Ticket di riparazione non trovato.', 'error')
        else:
            if subject:
                flash(f'Ticket "{subject}" eliminato con successo.', 'success')
            else:
                flash('Ticket eliminato con successo.', 'success')

        allowed_filters = {'status', 'from_date', 'to_date'}
        filters = {
            key[len('filter_'):]: value
            for key, value in request.form.items()
            if key.startswith('filter_') and value
        }
        filters = {key: value for key, value in filters.items() if key in allowed_filters}
        redirect_url = url_for('repairs', **filters) if filters else url_for('repairs')
        return redirect(redirect_url)

    # Gestione errori HTTP comuni con template dedicati.
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template('errors/500.html'), 500

    return app


app = create_app()


if __name__ == '__main__':
    # Avvia il server di sviluppo
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=True,
    )
