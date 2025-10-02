"""Definizione dei form WTForms per l'applicazione."""

from typing import Iterable, Tuple

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional


TicketChoice = Tuple[int, str]


class AddCustomerForm(FlaskForm):
    """Form per la creazione di un nuovo cliente."""

    name = StringField('Nome', validators=[DataRequired(message='Il nome è obbligatorio.')])
    email = StringField('Email', validators=[Optional(), Email(message='Inserisci un indirizzo email valido.')])
    phone = StringField('Telefono', validators=[Optional()])
    address = TextAreaField('Indirizzo', validators=[Optional()])


class AddTicketForm(FlaskForm):
    """Form per l'apertura di un nuovo ticket di assistenza."""

    customer_id = SelectField('Cliente', coerce=int, validators=[DataRequired(message='Seleziona un cliente.')])
    subject = StringField('Oggetto', validators=[DataRequired(message="L'oggetto è obbligatorio.")])
    description = TextAreaField('Descrizione', validators=[Optional()])

    def set_customer_choices(self, choices: Iterable[TicketChoice]) -> None:
        """Imposta le scelte per la select dei clienti."""

        choice_list = list(choices)
        self.customer_id.choices = [(0, '-- seleziona --')] + choice_list


class TicketStatusForm(FlaskForm):
    """Form per l'aggiornamento dello stato del ticket."""

    status = SelectField('Stato', validators=[DataRequired(message='Seleziona uno stato valido.')])

    def set_status_choices(self, choices: Iterable[Tuple[str, str]]) -> None:
        """Imposta le scelte disponibili per lo stato del ticket."""

        self.status.choices = list(choices)


class RepairForm(FlaskForm):
    """Form per registrare una nuova riparazione associata a un ticket."""

    ticket_id = SelectField('Ticket', coerce=int, validators=[DataRequired(message='Seleziona un ticket.')])
    product = StringField('Prodotto', validators=[Optional()])
    issue_description = TextAreaField('Descrizione problema', validators=[Optional()])
    repair_status = SelectField('Stato riparazione', validators=[DataRequired(message='Seleziona uno stato valido.')])
    date_received = DateField('Data ricezione', validators=[Optional()], default=None, format='%Y-%m-%d')
    date_repaired = DateField('Data riparazione', validators=[Optional()], default=None, format='%Y-%m-%d')
    date_returned = DateField('Data consegna', validators=[Optional()], default=None, format='%Y-%m-%d')

    def set_ticket_choices(self, choices: Iterable[TicketChoice]) -> None:
        """Imposta la lista dei ticket selezionabili."""

        choice_list = list(choices)
        self.ticket_id.choices = [(0, '-- seleziona --')] + choice_list

    def set_repair_status_choices(self, choices: Iterable[Tuple[str, str]]) -> None:
        """Imposta gli stati disponibili per la riparazione."""

        self.repair_status.choices = list(choices)

