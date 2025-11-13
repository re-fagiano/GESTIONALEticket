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


def test_calendar_sync_visible_for_any_authenticated_user(client, login):
    login('user', 'userpass')
    response: Response = client.get('/calendar/google')
    assert response.status_code == 200
    assert b'Integrazione Google Calendar' in response.data
    assert b'Accesso limitato' in response.data


def test_calendar_sync_post_requires_admin(client, login):
    login('user', 'userpass')
    response: Response = client.post('/calendar/google', data={'calendar_id': 'primary'})
    assert response.status_code == 403


def test_calendar_sync_available_for_admin(client, login):
    login('admin', 'adminpass')
    response: Response = client.get('/calendar/google')
    assert response.status_code == 200
    assert b'Integrazione Google Calendar' in response.data


def test_navigation_includes_inventory_link(client, login):
    login('user', 'userpass')
    response: Response = client.get('/')
    assert response.status_code == 200
    assert b'href="/magazzino"' in response.data
    assert b'Magazzino' in response.data


def test_navigation_includes_calendar_link_for_admin(client, login):
    login('admin', 'adminpass')
    response: Response = client.get('/')
    assert response.status_code == 200
    assert b'href="/calendar/google"' in response.data
    assert b'Google Calendar' in response.data


def test_navigation_marks_calendar_link_as_admin_only_for_regular_users(client, login):
    login('user', 'userpass')
    response: Response = client.get('/')
    assert response.status_code == 200
    assert b'href="/calendar/google"' in response.data
    assert b'Solo admin' in response.data


def test_navigation_exposes_service_links_even_before_login(client):
    response: Response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'href="/magazzino"' in response.data
    assert b'href="/calendar/google"' in response.data
    assert b'Richiede login' in response.data
