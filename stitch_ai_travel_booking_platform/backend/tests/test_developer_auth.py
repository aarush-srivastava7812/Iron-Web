import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from test_website import site
from app.config import settings
from app.main import app
from app.models import User
from app.routers.auth import _developer_available, _DEV_EMAIL, _DEV_USERNAME


@pytest.fixture
def developer(site, monkeypatch):
    monkeypatch.setattr(settings, 'developer_login_enabled', True)
    monkeypatch.setattr(settings, 'cookie_secure', False)
    monkeypatch.setattr(settings, 'secret_key', 'test-only-developer-session-secret-32-plus')
    async def local_app(scope, receive, send):
        scope = dict(scope, client=('127.0.0.1', 12345))
        await app(scope, receive, send)
    return TestClient(local_app, base_url='http://localhost:8088'), site[-1]


def test_developer_session_persists_and_uses_csrf(developer):
    client, sessions = developer
    assert client.get('/api/auth/developer/config').json() == {'enabled': True}
    headers = {'Origin':'http://localhost:8088', 'X-Voyara-Developer':'1'}
    first = client.post('/api/auth/developer', headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()['full_name'] == 'Voyara Developer'
    assert 'HttpOnly' in first.headers.get_list('set-cookie')[0]
    assert client.get('/api/auth/me').json()['id'] == first.json()['id']
    assert client.post('/api/favorites', json={'item_type':'package','item_id':1}).status_code == 403
    csrf = {'X-CSRF-Token':client.cookies.get('voyara_csrf')}
    assert client.post('/api/favorites', headers=csrf, json={'item_type':'package','item_id':1}).status_code == 201
    assert client.post('/api/auth/logout', headers=csrf).status_code == 204
    assert client.get('/api/auth/me').status_code == 401
    again = client.post('/api/auth/developer', headers=headers)
    assert again.json()['id'] == first.json()['id']
    assert len(client.get('/api/favorites').json()) == 1
    with sessions() as db:
        user = db.get(User, first.json()['id'])
        assert user.role == 'user'


def test_developer_disabled_and_cross_origin_rejected(developer, monkeypatch):
    client,_ = developer
    assert client.post('/api/auth/developer').status_code == 403
    assert client.post('/api/auth/developer', headers={'Origin':'https://evil.example','X-Voyara-Developer':'1'}).status_code == 403
    assert client.post('/api/auth/developer', headers={'Origin':'http://localhost:8088'}).status_code == 403
    monkeypatch.setattr(settings, 'developer_login_enabled', False)
    assert client.get('/api/auth/developer/config').json() == {'enabled': False}
    assert client.post('/api/auth/developer').status_code == 404


@pytest.mark.parametrize('peer,host,forwarded,secure',[
    ('203.0.113.12','localhost',False,False),
    ('127.0.0.1','app.example.com',False,False),
    ('127.0.0.1','localhost',True,False),
    ('127.0.0.1','localhost',False,True),
])
def test_local_only_guard(monkeypatch,peer,host,forwarded,secure):
    monkeypatch.setattr(settings,'developer_login_enabled',True)
    monkeypatch.setattr(settings,'cookie_secure',secure)
    headers=[(b'host',host.encode())]
    if forwarded: headers.append((b'x-forwarded-for',b'203.0.113.12'))
    request=Request({'type':'http','scheme':'http','path':'/api/auth/developer',
                     'server':(host,8088),'client':(peer,12345),'headers':headers})
    assert not _developer_available(request)


def test_existing_account_cannot_be_impersonated(developer):
    client,sessions = developer
    with sessions() as db:
        user = User(username=_DEV_USERNAME,email=_DEV_EMAIL,password_hash='another-account-hash',full_name='Existing user')
        db.add(user); db.commit(); uid=user.id
    result = client.post('/api/auth/developer', headers={'Origin':'http://localhost:8088','X-Voyara-Developer':'1'})
    assert result.status_code == 409
    with sessions() as db:
        assert db.get(User,uid).password_hash == 'another-account-hash'


def test_inactive_developer_cannot_sign_in(developer):
    client,sessions = developer
    headers={'Origin':'http://localhost:8088','X-Voyara-Developer':'1'}
    first=client.post('/api/auth/developer',headers=headers).json()
    with sessions() as db:
        db.get(User,first['id']).is_active=False
        db.commit()
    assert client.post('/api/auth/developer',headers=headers).status_code == 409
