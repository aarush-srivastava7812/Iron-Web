import time

import pytest
from sqlalchemy import select

from test_website import site  # isolated application database fixture
from app.config import settings
from app.models import GoogleIdentity, LoginChallenge, User
from app.routers import google_auth


@pytest.fixture
def google(site, monkeypatch):
    client,*_=site
    monkeypatch.setattr(settings,'google_client_id','123456789-test.apps.googleusercontent.com')
    monkeypatch.setattr(settings,'secret_key','a-test-only-secret-at-least-32-characters')
    monkeypatch.setattr(settings,'cookie_secure',False)
    claims=dict(sub='google-subject-123',email='traveller@gmail.com',email_verified=True,name='Test Traveller')
    nonce=None
    def verified(credential):
        assert credential=='verified-by-google-auth-in-production'
        return dict(claims,nonce=nonce)
    monkeypatch.setattr(google_auth,'verify_google',verified)
    def challenge():
        nonlocal nonce
        config=client.get('/api/auth/google/config')
        assert config.headers['cache-control']=='no-store'
        assert config.json()['client_id']==settings.google_client_id
        nonce=config.json()['nonce']
        return dict(credential='verified-by-google-auth-in-production',nonce=nonce)
    return site,claims,challenge


def test_placeholder_is_explicitly_unconfigured(site,monkeypatch):
    c,*_=site
    monkeypatch.setattr(settings,'google_client_id','YOUR_WEB_CLIENT_ID.apps.googleusercontent.com')
    assert c.get('/api/auth/google/config').json()==dict(configured=False,client_id=None,nonce=None)
    assert c.post('/api/auth/google',json={'credential':'no-token','nonce':'a'*32}).status_code==503


def test_google_session_is_httponly_csrf_protected_and_logs_out(google):
    (c,h,o,sessions),claims,challenge=google
    body=challenge()
    result=c.post('/api/auth/google',json=body)
    assert result.status_code==200,result.text
    assert 'access_token' not in result.json()
    cookies=result.headers.get_list('set-cookie')
    assert any('voyara_session=' in x and 'HttpOnly' in x and 'SameSite=lax' in x for x in cookies)
    assert c.get('/api/auth/me').json()['id']==result.json()['id']
    assert c.post('/api/favorites',json={'item_type':'package','item_id':1}).status_code==403
    csrf={'X-CSRF-Token':c.cookies.get('voyara_csrf')}
    assert c.post('/api/favorites',headers=csrf,json={'item_type':'package','item_id':1}).status_code==201
    assert c.post('/api/auth/logout',headers=csrf).status_code==204
    assert c.get('/api/auth/me').status_code==401
    assert c.post('/api/auth/google',json=body).status_code==401


def test_sub_is_stable_identity_even_if_google_email_changes(google):
    (c,h,o,sessions),claims,challenge=google
    first=c.post('/api/auth/google',json=challenge()).json()
    claims['email']='changed@gmail.com'
    second=c.post('/api/auth/google',json=challenge()).json()
    assert second['id']==first['id']
    with sessions() as db:
        assert len(db.scalars(select(GoogleIdentity)).all())==1


@pytest.mark.parametrize('email,hd,allowed',[
    ('local@gmail.com',None,True),('person@workspace.example','workspace.example',True),
    ('someone@example.com',None,False),
])
def test_linking_existing_account_requires_google_authoritative_email(google,email,hd,allowed):
    (c,h,o,sessions),claims,challenge=google
    registered=c.post('/api/auth/register',json={'email':email,'username':'existing','password':'test-password-123'}).json()
    claims['email']=email
    if hd:claims['hd']=hd
    result=c.post('/api/auth/google',json=challenge())
    assert result.status_code==(200 if allowed else 409),result.text
    if allowed:assert result.json()['id']==registered['user']['id']


def test_different_google_identity_cannot_relink_same_account(google):
    (c,h,o,sessions),claims,challenge=google
    assert c.post('/api/auth/google',json=challenge()).status_code==200
    claims['sub']='different-google-account'
    assert c.post('/api/auth/google',json=challenge()).status_code==409


@pytest.mark.parametrize('change',[{'email_verified':False},{'sub':''},{'email':''}])
def test_unverified_or_missing_identity_is_rejected(google,change):
    (c,h,o,sessions),claims,challenge=google
    claims.update(change)
    assert c.post('/api/auth/google',json=challenge()).status_code==401


def test_wrong_nonce_invalid_token_and_expiry_are_rejected(google,monkeypatch):
    (c,h,o,sessions),claims,challenge=google
    body=challenge()
    assert c.post('/api/auth/google',json=dict(body,nonce='different-nonce-value'*2)).status_code==401
    monkeypatch.setattr(google_auth,'verify_google',lambda _:dict(claims,nonce='wrong-token-nonce'))
    assert c.post('/api/auth/google',json=body).status_code==401
    def invalid(_):raise ValueError('bad signature / audience / issuer / expiry')
    monkeypatch.setattr(google_auth,'verify_google',invalid)
    assert c.post('/api/auth/google',json=body).status_code==401
    with sessions() as db:
        row=db.get(LoginChallenge,google_auth.digest(body['nonce']))
        row.expires_at=int(time.time())-1
        db.commit()
    assert c.post('/api/auth/google',json=body).status_code==401


def test_cookie_binding_is_required(google):
    (c,h,o,sessions),claims,challenge=google
    body=challenge()
    c.cookies.clear()
    assert c.post('/api/auth/google',json=body).status_code==401


def test_google_auth_verifier_receives_exact_configured_audience(google,monkeypatch):
    (c,h,o,sessions),claims,challenge=google
    body=challenge()
    calls=[]
    def verify(token,request,audience):
        calls.append((token,audience))
        return dict(claims,nonce=body['nonce'])
    monkeypatch.setattr(google_auth.id_token,'verify_oauth2_token',verify)
    monkeypatch.setattr(google_auth,'verify_google',lambda token:google_auth.id_token.verify_oauth2_token(
        token,google_auth.GoogleRequest(),settings.google_client_id))
    assert c.post('/api/auth/google',json=body).status_code==200
    assert calls==[(body['credential'],settings.google_client_id)]


def test_inactive_user_and_insecure_server_key_cannot_sign_in(google,monkeypatch):
    (c,h,o,sessions),claims,challenge=google
    first=c.post('/api/auth/google',json=challenge()).json()
    with sessions() as db:
        db.get(User,first['id']).is_active=False
        db.commit()
    assert c.post('/api/auth/google',json=challenge()).status_code==401
    monkeypatch.setattr(settings,'secret_key','dev-only-insecure-key-change-me-0000')
    assert c.post('/api/auth/google',json=challenge()).status_code==503
