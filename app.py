"""
Applicazione Flask per il gestionale a ticket.

Questo modulo definisce le varie rotte dell'applicazione, gestisce la
connessione al database tramite le funzioni di `database.py` e fornisce
funzionalità per la gestione di clienti, ticket e riparazioni.
"""

import os

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from pathlib import Path
from typing import Optional

from database import get_db, init_db, close_db
from flask_login import current_user, login_required

from auth import admin_required, bp as auth_bp, login_manager


TICKET_STATUSES = ["Accettazione", "Preventivo", "Riparato", "Chiuso"]


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


    # Rotta principale: mostra un riepilogo dei conteggi
    @app.route('/')
    @login_required
    def index():
        db = get_db()
        ticket_count = db.execute('SELECT COUNT(*) AS count FROM tickets').fetchone()['count']
        customer_count = db.execute('SELECT COUNT(*) AS count FROM customers').fetchone()['count']
        repair_count = db.execute('SELECT COUNT(*) AS count FROM repairs').fetchone()['count']
        return render_template('index.html', ticket_count=ticket_count,
                               customer_count=customer_count, repair_count=repair_count)

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
        if selected_status and selected_status in TICKET_STATUSES:
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
            selected_status=selected_status,
            current_filters=current_filters,
        )

    # Inserimento nuovo ticket
    @app.route('/tickets/new', methods=['GET', 'POST'])
    @admin_required
    def add_ticket():
        db = get_db()
        if request.method == 'POST':
            customer_id = request.form.get('customer_id')
            subject = request.form.get('subject', '').strip()
            description = request.form.get('description', '').strip()
            if not customer_id or not subject:
                flash('Cliente e oggetto sono obbligatori.', 'error')
            else:
                db.execute(
                    'INSERT INTO tickets (customer_id, subject, description, status) '
                    'VALUES (?, ?, ?, ?)',
                    (customer_id, subject, description or None, 'open')
                )
                db.commit()
                flash('Ticket creato con successo.', 'success')
                return redirect(url_for('tickets'))
        # Per GET (o se form incompleto), recupera elenco clienti per la select
        customers = db.execute('SELECT id, name FROM customers ORDER BY name').fetchall()
        return render_template('add_ticket.html', customers=customers)

    # Dettaglio ticket e aggiornamento stato
    @app.route('/tickets/<int:ticket_id>', methods=['GET', 'POST'])
    @login_required
    def ticket_detail(ticket_id: int):
        db = get_db()
        ticket = db.execute(
            'SELECT t.*, c.name AS customer_name '
            'FROM tickets t JOIN customers c ON t.customer_id = c.id '
            'WHERE t.id = ?', (ticket_id,)
        ).fetchone()
        if ticket is None:
            flash('Ticket non trovato.', 'error')
            return redirect(url_for('tickets'))
        if request.method == 'POST':
            if not getattr(current_user, 'is_admin', False):
                abort(403)
            new_status = request.form.get('status')
            if new_status:
                db.execute(
                    'UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (new_status, ticket_id)
                )
                db.commit()
                flash('Stato del ticket aggiornato.', 'success')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        # Recupera le riparazioni associate al ticket
        repairs = db.execute(
            'SELECT * FROM repairs WHERE ticket_id = ? ORDER BY id DESC',
            (ticket_id,)
        ).fetchall()
        return render_template('ticket_detail.html', ticket=ticket, repairs=repairs)

    # Lista delle riparazioni
    @app.route('/repairs')
    @login_required
    def repairs():
        db = get_db()
        repairs = db.execute(
            'SELECT r.*, t.subject AS ticket_subject, c.name AS customer_name '
            'FROM repairs r '
            'JOIN tickets t ON r.ticket_id = t.id '
            'JOIN customers c ON t.customer_id = c.id '
            'ORDER BY r.id DESC'
        ).fetchall()
        return render_template('repairs.html', repairs=repairs)

    # Inserimento nuova riparazione
    @app.route('/repairs/new', methods=['GET', 'POST'])
    @admin_required
    def add_repair():
        db = get_db()
        if request.method == 'POST':
            ticket_id = request.form.get('ticket_id')
            product = request.form.get('product', '').strip()
            issue_description = request.form.get('issue_description', '').strip()
            repair_status = request.form.get('repair_status', 'pending')
            date_received = request.form.get('date_received') or None
            date_repaired = request.form.get('date_repaired') or None
            date_returned = request.form.get('date_returned') or None

            errors = []
            if not ticket_id:
                errors.append('È necessario selezionare un ticket.')
            if not product:
                errors.append('Il prodotto è obbligatorio.')
            if not issue_description:
                errors.append('La descrizione del problema è obbligatoria.')

            if errors:
                for message in errors:
                    flash(message, 'error')
            else:
                db.execute(
                    'INSERT INTO repairs '
                    '(ticket_id, product, issue_description, repair_status, date_received, date_repaired, date_returned) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (ticket_id, product, issue_description, repair_status,
                     date_received, date_repaired, date_returned)
                )
                db.commit()
                flash('Riparazione registrata con successo.', 'success')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        # Per GET, recupera elenco ticket per la select
        tickets = db.execute('SELECT id, subject FROM tickets ORDER BY created_at DESC').fetchall()
        return render_template('add_repair.html', tickets=tickets)

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
