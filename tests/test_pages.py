from __future__ import annotations

from flask import Response


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
