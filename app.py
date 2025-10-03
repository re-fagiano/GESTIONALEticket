"""
Applicazione Flask per il gestionale a ticket.

Questo modulo definisce le varie rotte dell'applicazione, gestisce la
connessione al database tramite le funzioni di `database.py` e fornisce
funzionalità per la gestione di clienti, ticket e riparazioni.
"""

import os
import re
import uuid
from pathlib import Path
from typing import List, Optional, Sequence

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from auth import admin_required, bp as auth_bp, login_manager
from database import close_db, get_db, init_db
from flask_login import current_user, login_required


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
    ("preventivo", "Preventivo"),
    ("preventivo_accettato", "Preventivo accettato"),
    ("pronta", "Pronta"),
    ("riconsegnata", "Riconsegnata"),
]
REPAIR_STATUS_LABELS = {value: label for value, label in REPAIR_STATUSES}
REPAIR_STATUS_VALUES = set(REPAIR_STATUS_LABELS)
DEFAULT_REPAIR_STATUS = REPAIR_STATUSES[0][0]

TICKET_HISTORY_FIELD_LABELS = {
    '__created__': 'Creazione ticket',
    'status': 'Stato ticket',
    'product': 'Prodotto',
    'issue_description': 'Descrizione problema',
    'repair_status': 'Stato riparazione',
    'date_received': 'Data ricezione',
    'date_repaired': 'Data riparazione',
    'date_returned': 'Data consegna',
    'attachments': 'Allegati',
}


def _parse_size(value: Optional[str], default: int) -> int:
    """Converte una stringa di dimensione (es. "10MB") in byte."""

    if not value:
        return default
    raw_value = value.strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        match = re.match(r'^(?P<number>\d+)\s*(?P<unit>[KMG]B)?$', raw_value, flags=re.IGNORECASE)
        if not match:
            return default
        number = int(match.group('number'))
        unit = match.group('unit')
        if not unit:
            return number
        unit = unit.upper()
        multipliers = {
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
        }
        return number * multipliers.get(unit, 1)


def _get_allowed_extensions(raw: Optional[str]) -> List[str]:
    """Restituisce la lista delle estensioni consentite normalizzate."""

    if not raw:
        return ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx']
    extensions = []
    for item in raw.split(','):
        normalized = item.strip().lstrip('.').lower()
        if normalized:
            extensions.append(normalized)
    return extensions or ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx']


def _allowed_file(filename: str) -> bool:
    """Verifica se il file ha un'estensione consentita."""

    allowed_extensions = set(current_app.config.get('ALLOWED_EXTENSIONS', []))
    if not allowed_extensions:
        return True
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions


def _save_ticket_attachments(
    ticket_id: int,
    files: Sequence[FileStorage],
    uploaded_by: int,
    db,
) -> List[str]:
    """Salva gli allegati sul filesystem e registra i metadati sul database."""

    saved_names: List[str] = []
    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    max_file_size = current_app.config.get('MAX_FILE_SIZE')

    for file in files:
        if not file or not file.filename:
            continue

        original_name = file.filename
        safe_name = secure_filename(original_name)
        if not safe_name:
            flash('Impossibile caricare un file con nome non valido.', 'error')
            continue

        if not _allowed_file(safe_name):
            flash(f"Il file {original_name} ha un'estensione non consentita.", 'error')
            continue

        file_size = file.content_length
        if file_size is None:
            try:
                file.stream.seek(0, os.SEEK_END)
                file_size = file.stream.tell()
            except (AttributeError, OSError):
                file_size = None
            finally:
                try:
                    file.stream.seek(0)
                except (AttributeError, OSError):
                    pass

        if max_file_size and file_size and file_size > max_file_size:
            max_mb = max_file_size / (1024 * 1024)
            flash(
                f"Il file {original_name} supera la dimensione massima consentita di {max_mb:.1f} MB.",
                'error',
            )
            continue

        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        destination = upload_folder / unique_name

        try:
            file.stream.seek(0)
            file.save(destination)
        except OSError as exc:
            current_app.logger.exception("Errore durante il salvataggio dell'allegato")
            flash(f"Errore nel salvataggio dell'allegato {original_name}: {exc}", 'error')
            continue

        db.execute(
            'INSERT INTO ticket_attachments (ticket_id, file_path, original_name, content_type, uploaded_by) '
            'VALUES (?, ?, ?, ?, ?)',
            (
                ticket_id,
                unique_name,
                original_name,
                file.mimetype or 'application/octet-stream',
                uploaded_by,
            ),
        )
        saved_names.append(original_name)

    return saved_names


def _delete_ticket_files(ticket_id: int, db) -> None:
    """Rimuove dal filesystem gli allegati associati a un ticket."""

    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    attachments = db.execute(
        'SELECT id, file_path FROM ticket_attachments WHERE ticket_id = ?',
        (ticket_id,),
    ).fetchall()

    for attachment in attachments:
        file_path = upload_folder / attachment['file_path']
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError as exc:
            current_app.logger.warning(
                "Impossibile eliminare l'allegato %s: %s",
                file_path,
                exc,
            )

    db.execute('DELETE FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))


def create_app() -> Flask:
    """Factory per creare e configurare l'istanza di Flask."""
    app = Flask(__name__, instance_relative_config=True)
    # Chiave segreta per il sistema di messaggistica flash
    app.config['SECRET_KEY'] = 'change-me-please'
    # Percorso del database: per default è nella stessa directory del file app
    app.config.setdefault('DATABASE', str(Path(app.root_path) / 'database.db'))

    # Configurazione del filesystem per gli upload
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    upload_folder_env = os.environ.get('UPLOAD_FOLDER')
    upload_folder = Path(upload_folder_env) if upload_folder_env else instance_path / 'uploads'
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = str(upload_folder)

    max_content_length = _parse_size(os.environ.get('MAX_CONTENT_LENGTH'), 16 * 1024 * 1024)
    app.config['MAX_CONTENT_LENGTH'] = max_content_length

    max_file_size = _parse_size(os.environ.get('UPLOAD_MAX_FILE_SIZE'), max_content_length)
    if max_file_size > max_content_length:
        max_file_size = max_content_length
    app.config['MAX_FILE_SIZE'] = max_file_size

    allowed_extensions = set(_get_allowed_extensions(os.environ.get('UPLOAD_ALLOWED_EXTENSIONS')))
    app.config['ALLOWED_EXTENSIONS'] = allowed_extensions

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

    # Lista clienti
    @app.route('/customers')
    @login_required
    def customers():
        db = get_db()
        customers = db.execute('SELECT * FROM customers ORDER BY name').fetchall()
        return render_template('customers.html', customers=customers)

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

    # Inserimento nuovo ticket
    @app.route('/tickets/new', methods=['GET', 'POST'])
    @admin_required
    def add_ticket():
        db = get_db()
        if request.method == 'POST':
            current_user_id = int(current_user.id)
            customer_id = request.form.get('customer_id')
            subject = request.form.get('subject', '').strip()
            description = request.form.get('description', '').strip()
            product = request.form.get('product', '').strip()
            issue_description = request.form.get('issue_description', '').strip()
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
                    'customer_id, subject, description, status, product, issue_description, '
                    'repair_status, date_received, date_repaired, date_returned, created_by, last_modified_by'
                    ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        customer_id,
                        subject,
                        description or None,
                        DEFAULT_TICKET_STATUS,
                        product or None,
                        issue_description or None,
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
                    DEFAULT_TICKET_STATUS, DEFAULT_TICKET_STATUS
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
                attachments = request.files.getlist('attachments')
                saved_attachment_names = _save_ticket_attachments(
                    ticket_id,
                    attachments,
                    current_user_id,
                    db,
                )
                if saved_attachment_names:
                    db.execute(
                        'INSERT INTO ticket_history (ticket_id, field, old_value, new_value, changed_by) '
                        'VALUES (?, ?, ?, ?, ?)',
                        (
                            ticket_id,
                            'attachments',
                            None,
                            'Aggiunti allegati: ' + ', '.join(saved_attachment_names),
                            current_user_id,
                        ),
                    )
                db.commit()
                flash('Ticket creato con successo.', 'success')
                return redirect(url_for('tickets'))
        # Per GET (o se form incompleto), recupera elenco clienti per la select
        customers = db.execute('SELECT id, name FROM customers ORDER BY name').fetchall()
        return render_template(
            'add_ticket.html',
            customers=customers,
            repair_statuses=REPAIR_STATUSES,
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
            if not getattr(current_user, 'is_admin', False):
                abort(403)
            current_user_id = int(current_user.id)
            attachments_files = request.files.getlist('attachments')
            attempted_attachments = any(
                file and getattr(file, 'filename', '') for file in attachments_files
            )
            new_status = request.form.get('status', '').strip() or ticket['status']
            if new_status not in TICKET_STATUS_VALUES:
                flash('Stato del ticket non valido.', 'error')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))

            product = request.form.get('product', '').strip() or None
            issue_description = request.form.get('issue_description', '').strip() or None
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
                'repair_status',
                'date_received',
                'date_repaired',
                'date_returned',
            )
            new_values = {
                'status': new_status,
                'product': product,
                'issue_description': issue_description,
                'repair_status': repair_status,
                'date_received': date_received,
                'date_repaired': date_repaired,
                'date_returned': date_returned,
            }
            has_changes = any(
                (ticket[field] or '') != (new_values[field] or '') for field in tracked_fields
            )

            if has_changes:
                db.execute(
                    'UPDATE tickets SET '
                    'status = ?, product = ?, issue_description = ?, repair_status = ?, '
                    'date_received = ?, date_repaired = ?, date_returned = ?, '
                    'last_modified_by = ?, updated_at = CURRENT_TIMESTAMP '
                    'WHERE id = ?',
                    (
                        new_status,
                        product,
                        issue_description,
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

            saved_attachment_names = _save_ticket_attachments(
                ticket_id,
                attachments_files,
                current_user_id,
                db,
            )

            if saved_attachment_names:
                db.execute(
                    'INSERT INTO ticket_history (ticket_id, field, old_value, new_value, changed_by) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (
                        ticket_id,
                        'attachments',
                        None,
                        'Aggiunti allegati: ' + ', '.join(saved_attachment_names),
                        current_user_id,
                    ),
                )

            if not has_changes and not saved_attachment_names:
                if not attempted_attachments:
                    flash('Nessuna modifica rilevata.', 'info')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))

            db.commit()
            if has_changes and saved_attachment_names:
                flash('Ticket aggiornato e allegati caricati con successo.', 'success')
            elif has_changes:
                flash('Ticket aggiornato con successo.', 'success')
            else:
                flash('Allegati caricati con successo.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))

        history_entries = db.execute(
            'SELECT h.field, h.old_value, h.new_value, h.changed_at, '
            'u.username AS changed_by_username '
            'FROM ticket_history h '
            'LEFT JOIN users u ON h.changed_by = u.id '
            'WHERE h.ticket_id = ? '
            'ORDER BY h.changed_at DESC, h.id DESC',
            (ticket_id,),
        ).fetchall()
        attachments = db.execute(
            'SELECT a.*, u.username AS uploaded_by_username '
            'FROM ticket_attachments a '
            'LEFT JOIN users u ON a.uploaded_by = u.id '
            'WHERE a.ticket_id = ? '
            'ORDER BY a.uploaded_at DESC, a.id DESC',
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
            ticket_history_field_labels=TICKET_HISTORY_FIELD_LABELS,
            attachments=attachments,
        )

    @app.route('/tickets/<int:ticket_id>/attachments/<int:attachment_id>')
    @login_required
    def download_ticket_attachment(ticket_id: int, attachment_id: int):
        db = get_db()
        attachment = db.execute(
            'SELECT a.*, t.id AS ticket_id '
            'FROM ticket_attachments a '
            'JOIN tickets t ON a.ticket_id = t.id '
            'WHERE a.id = ? AND a.ticket_id = ?',
            (attachment_id, ticket_id),
        ).fetchone()
        if attachment is None:
            abort(404)

        file_path = Path(current_app.config['UPLOAD_FOLDER']) / attachment['file_path']
        if not file_path.exists():
            current_app.logger.warning(
                "File allegato mancante: ticket %s, attachment %s",
                ticket_id,
                attachment_id,
            )
            abort(404)

        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            attachment['file_path'],
            as_attachment=True,
            download_name=attachment['original_name'],
        )

    @app.route('/tickets/<int:ticket_id>/delete', methods=['POST'])
    @admin_required
    def delete_ticket(ticket_id: int):
        db = get_db()
        ticket = db.execute('SELECT id FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        if ticket is None:
            flash('Ticket non trovato.', 'error')
            return redirect(url_for('tickets'))

        _delete_ticket_files(ticket_id, db)
        db.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
        db.commit()
        flash('Ticket eliminato con successo.', 'success')
        return redirect(url_for('tickets'))

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
