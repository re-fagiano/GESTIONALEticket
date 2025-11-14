from __future__ import annotations


def test_admin_navigation_shows_restricted_links(client, login):
    login('admin', 'adminpass')
    response = client.get('/')
    html = response.get_data(as_text=True)

    assert 'Magazzino' in html
    assert 'Sync Google Calendar' in html
    assert 'Utenti' in html


def test_non_admin_sees_badges_and_no_admin_users_link(client, login):
    login('user', 'userpass')
    response = client.get('/')
    html = response.get_data(as_text=True)

    assert 'Magazzino' in html
    assert 'Sync Google Calendar' in html
    assert 'Solo admin' in html
    assert 'Utenti' not in html
