from __future__ import annotations

import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / 'test.db'
    upload_path = tmp_path / 'uploads'
    credentials_path = tmp_path / 'google_credentials.json'
    token_path = tmp_path / 'google_token.json'

    app = create_app(
        {
            'TESTING': True,
            'DATABASE': str(db_path),
            'UPLOAD_FOLDER': str(upload_path),
            'GOOGLE_CALENDAR_CREDENTIALS_FILE': str(credentials_path),
            'GOOGLE_CALENDAR_TOKEN_FILE': str(token_path),
        }
    )

    # Assicura che il database di test sia inizializzato e contenga un admin
    with app.app_context():
        init_db()
        db = get_db()
        db.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('admin', generate_password_hash('adminpass'), 'admin'),
        )
        db.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('user', generate_password_hash('userpass'), 'user'),
        )
        db.commit()

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def _login(username: str, password: str, *, follow_redirects: bool = True):
        return client.post(
            '/auth/login',
            data={'username': username, 'password': password},
            follow_redirects=follow_redirects,
        )

    return _login
