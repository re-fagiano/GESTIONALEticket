"""
Applicazione Flask per il gestionale a ticket.

Questo modulo definisce le varie rotte dell'applicazione, gestisce la
connessione al database tramite le funzioni di `database.py` e fornisce
funzionalità per la gestione di clienti, ticket e riparazioni.
"""

import os

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf import CSRFProtect
from pathlib import Path
from typing import Optional

from database import get_db, init_db, close_db
from forms import AddCustomerForm, AddTicketForm, TicketStatusForm, RepairForm


TICKET_STATUSES = ["Accettazione", "Preventivo", "Riparato", "Chiuso"]
TICKET_STATUS_CHOICES = [
    ("open", "Aperto"),
    ("in_progress", "In lavorazione"),
    ("closed", "Chiuso"),
]
REPAIR_STATUS_CHOICES = [
    ("pending", "In attesa"),
    ("in_progress", "In lavorazione"),
    ("completed", "Completata"),
]


csrf = CSRFProtect()


def create_app() -> Flask:
    """Factory per creare e configurare l'istanza di Flask."""
    app = Flask(__name__, instance_relative_config=True)
    # Chiave segreta per il sistema di messaggistica flash
    app.config['SECRET_KEY'] = 'change-me-please'
    # Percorso del database: per default è nella stessa directory del file app
    app.config.setdefault('DATABASE', str(Path(app.root_path) / 'database.db'))

    csrf.init_app(app)

    # Chiude la connessione al database alla fine di ogni richiesta
    @app.teardown_appcontext
    def _close_database(exception: Optional[BaseException] = None):
        close_db(exception)

    # Inizializza il database una volta all’avvio utilizzando il contesto dell’applicazione.
    # In Flask 3.x il decorator before_first_request non è più disponibile.
    with app.app_context():
        init_db()


    # Rotta principale: mostra un riepilogo dei conteggi
    @app.route('/')
    def index():
        db = get_db()
        ticket_count = db.execute('SELECT COUNT(*) AS count FROM tickets').fetchone()['count']
        customer_count = db.execute('SELECT COUNT(*) AS count FROM customers').fetchone()['count']
        repair_count = db.execute('SELECT COUNT(*) AS count FROM repairs').fetchone()['count']
        return render_template('index.html', ticket_count=ticket_count,
                               customer_count=customer_count, repair_count=repair_count)

    # Lista clienti
    @app.route('/customers')
    def customers():
        db = get_db()
        customers = db.execute('SELECT * FROM customers ORDER BY name').fetchall()
        return render_template('customers.html', customers=customers)

    # Inserimento nuovo cliente
    @app.route('/customers/new', methods=['GET', 'POST'])
    def add_customer():
        form = AddCustomerForm()
        if form.validate_on_submit():
            db = get_db()
            db.execute(
                'INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)',
                (
                    form.name.data.strip(),
                    form.email.data.strip() if form.email.data else None,
                    form.phone.data.strip() if form.phone.data else None,
                    form.address.data.strip() if form.address.data else None,
                )
            )
            db.commit()
            flash('Cliente aggiunto con successo.', 'success')
            return redirect(url_for('customers'))
        return render_template('add_customer.html', form=form)

    # Lista ticket
    @app.route('/tickets')
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
    def add_ticket():
        db = get_db()
        customers = db.execute('SELECT id, name FROM customers ORDER BY name').fetchall()
        customer_choices = [(customer['id'], customer['name']) for customer in customers]
        form = AddTicketForm()
        form.set_customer_choices(customer_choices)
        if form.validate_on_submit():
            db.execute(
                'INSERT INTO tickets (customer_id, subject, description, status) '
                'VALUES (?, ?, ?, ?)',
                (
                    form.customer_id.data,
                    form.subject.data.strip(),
                    form.description.data.strip() if form.description.data else None,
                    'open',
                )
            )
            db.commit()
            flash('Ticket creato con successo.', 'success')
            return redirect(url_for('tickets'))
        return render_template('add_ticket.html', form=form)

    # Dettaglio ticket e aggiornamento stato
    @app.route('/tickets/<int:ticket_id>', methods=['GET', 'POST'])
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
        form = TicketStatusForm()
        form.set_status_choices(TICKET_STATUS_CHOICES)
        if request.method == 'GET':
            form.status.data = ticket['status']
        if form.validate_on_submit():
            db.execute(
                'UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (form.status.data, ticket_id)
            )
            db.commit()
            flash('Stato del ticket aggiornato.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        # Recupera le riparazioni associate al ticket
        repairs = db.execute(
            'SELECT * FROM repairs WHERE ticket_id = ? ORDER BY id DESC',
            (ticket_id,)
        ).fetchall()
        return render_template('ticket_detail.html', ticket=ticket, repairs=repairs, form=form)

    # Lista delle riparazioni
    @app.route('/repairs')
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
    def add_repair():
        db = get_db()
        tickets = db.execute('SELECT id, subject FROM tickets ORDER BY created_at DESC').fetchall()
        ticket_choices = [(ticket['id'], f"{ticket['id']:04d} - {ticket['subject']}") for ticket in tickets]
        form = RepairForm()
        form.set_ticket_choices(ticket_choices)
        form.set_repair_status_choices(REPAIR_STATUS_CHOICES)
        if request.method == 'GET':
            preselected_ticket_id = request.args.get('ticket_id', type=int)
            if preselected_ticket_id and any(choice[0] == preselected_ticket_id for choice in ticket_choices):
                form.ticket_id.data = preselected_ticket_id
        if form.validate_on_submit():
            db.execute(
                'INSERT INTO repairs '
                '(ticket_id, product, issue_description, repair_status, date_received, date_repaired, date_returned) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    form.ticket_id.data,
                    form.product.data.strip() if form.product.data else None,
                    form.issue_description.data.strip() if form.issue_description.data else None,
                    form.repair_status.data,
                    form.date_received.data.isoformat() if form.date_received.data else None,
                    form.date_repaired.data.isoformat() if form.date_repaired.data else None,
                    form.date_returned.data.isoformat() if form.date_returned.data else None,
                )
            )
            db.commit()
            flash('Riparazione registrata con successo.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=form.ticket_id.data))
        return render_template('add_repair.html', form=form)

    return app


app = create_app()


if __name__ == '__main__':
    # Avvia il server di sviluppo
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=True,
    )
