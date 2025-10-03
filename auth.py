"""Blueprint per l'autenticazione e la gestione degli utenti."""

from __future__ import annotations

from functools import wraps
from typing import Optional

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db


login_manager = LoginManager()
login_manager.login_view = 'auth.login'


class User(UserMixin):
    """Semplice rappresentazione dell'utente per Flask-Login."""

    def __init__(self, user_id: int, username: str, role: str) -> None:
        self.id = str(user_id)
        self.username = username
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'


def _row_to_user(row: Optional[dict]) -> Optional[User]:
    if row is None:
        return None
    return User(row['id'], row['username'], row['role'])


def get_user_by_id(user_id: str) -> Optional[User]:
    db = get_db()
    row = db.execute(
        'SELECT id, username, role FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()
    return _row_to_user(row)


def get_user_by_username(username: str) -> Optional[User]:
    db = get_db()
    row = db.execute(
        'SELECT id, username, role FROM users WHERE username = ?',
        (username,),
    ).fetchone()
    return _row_to_user(row)


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    return get_user_by_id(user_id)


def admin_required(view):
    """Decoratore per consentire l'accesso solo agli amministratori."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):  # type: ignore[misc]
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            flash('Non hai i permessi necessari per completare l\'operazione.', 'error')
            return redirect(url_for('index'))
        return view(*args, **kwargs)

    return wrapped


bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Sei già autenticato.', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        row = db.execute(
            'SELECT id, username, password_hash, role FROM users WHERE username = ?',
            (username,),
        ).fetchone()

        if row and check_password_hash(row['password_hash'], password):
            user = User(row['id'], row['username'], row['role'])
            login_user(user)
            flash('Accesso effettuato correttamente.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))

        flash('Credenziali non valide.', 'error')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Disconnessione avvenuta con successo.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    db = get_db()
    admin_exists = bool(
        db.execute(
            "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
    )

    allow_role_selection = (
        current_user.is_authenticated and getattr(current_user, 'is_admin', False)
    )

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')

        errors = []
        if not username:
            errors.append('Il nome utente è obbligatorio.')
        if not password:
            errors.append('La password è obbligatoria.')

        if not admin_exists:
            role = 'admin'
        elif not allow_role_selection or role not in {'admin', 'user'}:
            role = 'user'

        existing = db.execute(
            'SELECT 1 FROM users WHERE username = ?',
            (username,),
        ).fetchone()
        if existing:
            errors.append('Il nome utente è già in uso.')

        if errors:
            for error in errors:
                flash(error, 'error')
        else:
            password_hash = generate_password_hash(password)
            db.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                (username, password_hash, role),
            )
            db.commit()
            flash('Utente registrato con successo.', 'success')
            return redirect(url_for('auth.login'))

    return render_template(
        'register.html',
        allow_role_selection=allow_role_selection,
        admin_exists=admin_exists,
    )

