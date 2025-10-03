"""
Applicazione Flask per il gestionale a ticket.

Questo modulo definisce le varie rotte dell'applicazione, gestisce la
connessione al database tramite le funzioni di `database.py` e fornisce
funzionalità per la gestione di clienti, ticket e riparazioni.
"""

import os

from flask import Flask, render_template, request, redirect, url_for, flash
from pathlib import Path
from typing import Optional, Tuple

from database import get_db, init_db, close_db
from flask_login import current_user, login_required

from auth import admin_required, bp as auth_bp, login_manager


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
    # Chiave segreta per il sistema di messaggistica flash
    app.config['SECRET_KEY'] = 'change-me-please'
    # Percorso del database: per default è nella stessa directory del file app
    app.config.setdefault('DATABASE', str(Path(app.root_path) / 'database.db'))

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
                db.commit()
                flash('Ticket creato con successo.', 'success')
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
            current_user_id = int(current_user.id)
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
            ticket_history_field_labels=TICKET_HISTORY_FIELD_LABELS,
        )

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
