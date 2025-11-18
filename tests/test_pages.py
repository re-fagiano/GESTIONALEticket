from __future__ import annotations

import json
from pathlib import Path

from flask import Response
from werkzeug.security import generate_password_hash

from database import get_db


def test_magazzino_requires_authentication(client):
    response: Response = client.get('/magazzino')
    assert response.status_code == 302
    assert '/auth/login' in response.headers.get('Location', '')


def test_magazzino_available_for_admin(client, login):
    login('admin', 'adminpass')
    response: Response = client.get('/magazzino')
    assert response.status_code == 200
    assert b'Magazzino' in response.data
    assert b'Nuovo articolo' in response.data


def test_navigation_shows_magazzino_and_calendar_links(client):
    response: Response = client.get('/auth/login')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/magazzino"' in html
    assert 'Magazzino' in html
    assert 'href="/admin/calendar-sync"' in html
    assert 'Sync Google Calendar' in html


def test_calendar_sync_requires_admin_role(client, login):
    login('user', 'userpass')
    response: Response = client.get('/admin/calendar-sync')
    assert response.status_code == 302
    assert response.headers.get('Location', '').endswith('/')


def test_calendar_sync_available_for_admin(client, login):
    login('admin', 'adminpass')
    response: Response = client.get('/admin/calendar-sync')
    assert response.status_code == 200
    assert b'Sincronizzazione clienti da Google Calendar' in response.data


def test_admin_can_upload_calendar_credentials_and_token(client, app, login):
    login('admin', 'adminpass')

    credentials_payload = {
        'installed': {
            'client_id': 'demo.apps.googleusercontent.com',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        }
    }
    response = client.post(
        '/admin/calendar-sync',
        data={
            'action': 'save_credentials',
            'credentials_json': json.dumps(credentials_payload),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        credentials_path = Path(app.config['GOOGLE_CALENDAR_CREDENTIALS_FILE'])
        assert credentials_path.exists()
        assert json.loads(credentials_path.read_text(encoding='utf-8')) == credentials_payload

    token_payload = {
        'token': 'ya29.token',
        'refresh_token': '1//refresh-token',
        'client_id': 'demo.apps.googleusercontent.com',
        'client_secret': 'secret',
        'scopes': ['https://www.googleapis.com/auth/calendar.readonly'],
    }
    response = client.post(
        '/admin/calendar-sync',
        data={
            'action': 'save_token',
            'token_json': json.dumps(token_payload),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with app.app_context():
        token_path = Path(app.config['GOOGLE_CALENDAR_TOKEN_FILE'])
        assert token_path.exists()
        assert json.loads(token_path.read_text(encoding='utf-8')) == token_payload


def test_calendar_sync_requires_token_before_running(client, app, login, monkeypatch):
    login('admin', 'adminpass')

    with app.app_context():
        credentials_path = Path(app.config['GOOGLE_CALENDAR_CREDENTIALS_FILE'])
        credentials_path.parent.mkdir(parents=True, exist_ok=True)
        credentials_path.write_text(
            json.dumps(
                {
                    'installed': {
                        'client_id': 'demo.apps.googleusercontent.com',
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    }
                }
            ),
            encoding='utf-8',
        )

    called = {'run': False}

    def _fake_run_calendar_sync(**_kwargs):
        called['run'] = True
        return {'created': 0, 'updated': 0, 'skipped': 0}, None

    monkeypatch.setattr('app.run_calendar_sync', _fake_run_calendar_sync)

    response = client.post(
        '/admin/calendar-sync',
        data={
            'action': 'run_sync',
            'calendar_id': 'primary',
            'past_days': '30',
            'future_days': '7',
            'max_results': '100',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert not called['run'], 'la sincronizzazione non dovrebbe partire senza token'
    assert b'Completa prima il caricamento di credenziali e token OAuth' in response.data


def test_legacy_admin_role_is_normalized(client, app):
    with app.app_context():
        db = get_db()
        db.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('legacy_admin', generate_password_hash('legacy'), 'Admin'),
        )
        db.commit()

    login_response: Response = client.post(
        '/auth/login',
        data={'username': 'legacy_admin', 'password': 'legacy'},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    magazzino_response: Response = client.get('/magazzino')
    assert magazzino_response.status_code == 200
    assert b'Nuovo articolo' in magazzino_response.data

    calendar_response: Response = client.get('/admin/calendar-sync')
    assert calendar_response.status_code == 200
