import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models import Booking, BookingRequestDetails, ContactEnquiry, NewsletterSubscription, TransportRoute
import seed


@pytest.fixture
def site(tmp_path, monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'site.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(seed,'SessionLocal',sessions)
    monkeypatch.setattr(seed,'create_schema',lambda:None)
    seed.run()
    def db():
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db]=db
    client=TestClient(app)
    def register(name):
        result=client.post('/api/auth/register',json={'email':name+'@example.com','username':name,'password':'test-password-123'})
        assert result.status_code==201,result.text
        return {'Authorization':'Bearer '+result.json()['access_token']}
    headers=register('first')
    other=register('other')
    yield client,headers,other,sessions
    app.dependency_overrides.clear()
    engine.dispose()


def tomorrow():
    return (dt.date.today()+dt.timedelta(days=30)).isoformat()


def package_items(client):
    p=client.get('/api/website/catalog').json()['destinations'][0]
    start=dt.date.fromisoformat(tomorrow())
    return p,[dict(item_type='package',item_id=p['id'],quantity=2,start_date=start.isoformat(),
                   end_date=(start+dt.timedelta(days=p['nights'])).isoformat())]


def booking_request(items,total):
    return dict(items=items,request_key=str(uuid.uuid4()),expected_total_inr=total,
                traveler=dict(first='Test',last='Traveller',email='traveler@example.com',phone='+91 9999999999',
                              notes='Quiet room please',consent=True))


def test_catalog_is_seeded_and_idempotent(site):
    c,h,o,sessions=site
    before=c.get('/api/website/catalog').json()
    seed.run()
    assert c.get('/api/website/catalog').json()==before
    assert len(before['destinations'])==10 and len(before['hotels'])>=12 and len(before['experiences'])>=12
    assert {c['name'] for c in before['destination_guides']['Kerala']['cities']} == {'Kochi','Munnar','Alleppey'}
    assert before['destinations'][0]['name']=='Kashmir'
    assert all(x['id'] and x['destination_id'] for k in ['destinations','hotels','experiences'] for x in before[k])


def test_package_quote_confirm_replay_and_owner_isolation(site):
    c,h,o,sessions=site
    p,items=package_items(c)
    assert c.post('/api/website/quote',json={'items':items}).status_code==401
    quote=c.post('/api/website/quote',headers=h,json={'items':items})
    assert quote.status_code==200,quote.text
    total=p['price']*2
    assert quote.json()['total_inr']==total
    body=booking_request(items,total)
    first=c.post('/api/website/bookings',headers=h,json=body)
    assert first.status_code==201,first.text
    replay=c.post('/api/website/bookings',headers=h,json=body)
    assert replay.json()['id']==first.json()['id']
    assert c.post('/api/website/bookings',headers=o,json=body).status_code==409
    assert c.get('/api/bookings',headers=o).json()==[]
    assert c.post(f"/api/bookings/{first.json()['id']}/cancel",headers=o).status_code==404
    with sessions() as db:
        assert len(db.scalars(select(Booking)).all())==1
        details=db.get(BookingRequestDetails,first.json()['id'])
        assert details.traveler['notes']=='Quiet room please'


def test_price_tampering_and_invalid_package_dates(site):
    c,h,o,sessions=site
    p,items=package_items(c)
    assert c.post('/api/website/bookings',headers=h,json=booking_request(items,1)).status_code==409
    items[0]['end_date']=items[0]['start_date']
    assert c.post('/api/website/quote',headers=h,json={'items':items}).status_code==422
    items[0]['start_date']='2000-01-01'
    assert c.post('/api/website/quote',headers=h,json={'items':items}).status_code==422
    with sessions() as db:
        assert not db.scalars(select(Booking)).all()


@pytest.mark.parametrize('kind,key',[('stay','hotels'),('experience','experiences')])
def test_stay_and_experience_requests_use_server_prices(site,kind,key):
    c,h,o,sessions=site
    item=c.get('/api/website/catalog').json()[key][0]
    start=dt.date.fromisoformat(tomorrow())
    payload=dict(item_type=kind,item_id=item['id'],quantity=2,start_date=start.isoformat())
    if kind=='stay':payload['end_date']=(start+dt.timedelta(days=3)).isoformat()
    quote=c.post('/api/website/quote',headers=h,json={'items':[payload]})
    assert quote.status_code==200,quote.text
    assert quote.json()['total_inr']==item['price']*2*(3 if kind=='stay' else 1)
    assert c.post('/api/website/bookings',headers=h,json=booking_request([payload],quote.json()['total_inr'])).status_code==201


def test_flight_search_round_trip_and_cancel_restore_inventory(site):
    c,h,o,sessions=site
    airports=c.get('/api/website/catalog').json()['airports']
    names={x['name']:x['id'] for x in airports}
    params=dict(origin_id=names['New Delhi'],destination_id=names['Kashmir'],depart=tomorrow(),return_date=tomorrow(),travelers=2)
    result=c.get('/api/website/flights',params=params)
    assert result.status_code==200,result.text
    legs=[result.json()['outbound'][0],result.json()['return'][0]]
    items=[dict(item_type='transport',item_id=x['id'],quantity=2,start_date=x['date']) for x in legs]
    quote=c.post('/api/website/quote',headers=h,json={'items':items}).json()
    body=booking_request(items,quote['total_inr'])
    booking=c.post('/api/website/bookings',headers=h,json=body)
    assert booking.status_code==201,booking.text
    assert c.post('/api/website/bookings',headers=h,json=body).json()['id']==booking.json()['id']
    with sessions() as db:
        assert all(db.get(TransportRoute,x['id']).seats_available==x['seats_available']-2 for x in legs)
    assert c.post(f"/api/bookings/{booking.json()['id']}/cancel",headers=h).status_code==200
    assert c.post(f"/api/bookings/{booking.json()['id']}/cancel",headers=h).status_code==409
    with sessions() as db:
        assert all(db.get(TransportRoute,x['id']).seats_available==x['seats_available'] for x in legs)
    assert c.get('/api/website/flights',params=dict(params,cabin='Business')).status_code==422
    assert c.get('/api/website/flights',params=dict(params,return_date='2000-01-01')).status_code==422


def test_same_numeric_package_and_stay_favorites_coexist(site):
    c,h,o,sessions=site
    for kind in ['package','stay']:
        r=c.post('/api/favorites',headers=h,json={'item_type':kind,'item_id':1})
        assert r.status_code==201,r.text
    assert len(c.get('/api/favorites',headers=h).json())==2
    assert not c.get('/api/favorites',headers=o).json()
    assert c.post('/api/favorites',headers=h,json={'item_type':'package','item_id':999999}).status_code==404
    c.delete('/api/favorites/package/1',headers=h)
    assert c.get('/api/favorites',headers=h).json()[0]['item_type']=='stay'


def test_concurrent_favorite_saves_are_idempotent(site):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import event
    from app.models import Favorite

    client, headers, _, sessions = site
    # Hold every insert until all requests have passed the initial lookup.
    # This reliably exercises the unique-key race, rather than sequential retries.
    ready = Barrier(5)
    def before_insert(mapper, connection, target):
        ready.wait(timeout=15)

    event.listen(Favorite, 'before_insert', before_insert)
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            responses = list(pool.map(lambda _: client.post('/api/favorites', headers=headers,
                json={'item_type': 'package', 'item_id': 1}), range(5)))
    finally:
        event.remove(Favorite, 'before_insert', before_insert)
    assert all(response.status_code == 201 for response in responses)
    assert len(client.get('/api/favorites', headers=headers).json()) == 1


def test_contact_and_newsletter_persist_without_exposing_private_data(site):
    c,h,o,sessions=site
    body=dict(name='A Traveller',email='TRAVELER@example.com',phone=None,topic='Planning',message='Tell me more about Kashmir')
    for _ in range(5):assert c.post('/api/website/enquiries',json=body).status_code==201
    assert c.post('/api/website/enquiries',json=body).status_code==429
    for _ in range(2):
        subscribed = c.post('/api/website/newsletter',json={'email':body['email']})
        assert subscribed.status_code==200
        assert subscribed.json()['status']=='subscribed'
    assert c.post('/api/website/newsletter',json={'email':'bad'}).status_code==422
    assert c.get('/api/website/enquiries').status_code==404
    with sessions() as db:
        assert len(db.scalars(select(ContactEnquiry)).all())==5
        assert len(db.scalars(select(NewsletterSubscription)).all())==1


def test_existing_sqlite_favorites_upgrade_preserves_records(tmp_path,monkeypatch):
    from sqlalchemy import inspect
    from app import db as database
    from app.models import User
    engine=create_engine('sqlite:///'+str(tmp_path/'old.db'))
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    with sessions() as db:
        user=User(email='old@example.com',username='old',password_hash='unused')
        db.add(user);db.commit();uid=user.id
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP TABLE favorites')
        connection.exec_driver_sql('CREATE TABLE favorites (user_id VARCHAR(36), item_type VARCHAR(10), item_id INTEGER, created_at DATETIME, PRIMARY KEY (user_id,item_id))')
        connection.exec_driver_sql("INSERT INTO favorites VALUES (?, 'stay', 1, '2026-10-16 00:00:00')",(uid,))
    monkeypatch.setattr(database,'engine',engine)
    database.create_schema()
    database.create_schema()  # upgrade is idempotent
    with engine.begin() as connection:
        assert 'item_type' in inspect(connection).get_pk_constraint('favorites')['constrained_columns']
        assert connection.exec_driver_sql('SELECT user_id,item_type,item_id FROM favorites').all()==[(uid,'stay',1)]
        connection.exec_driver_sql("INSERT INTO favorites VALUES (?, 'package', 1, '2026-10-16 00:00:00')",(uid,))
    engine.dispose()


def test_failed_hosted_review_is_unavailable_and_quote_still_works(site, monkeypatch):
    from app.routers import website
    c, h, _, _ = site
    package, items = package_items(c)
    class Unavailable:
        def chat_json(self, *args, **kwargs):
            return None
    monkeypatch.setattr(website, 'get_nim_client', lambda: Unavailable())
    assert c.post('/api/website/agent-review', json={'items':items}).status_code==401
    response=c.post('/api/website/agent-review', headers=h, json={'items':items,'destination_name':'Kashmir'})
    assert response.status_code==503
    assert 'unavailable' in response.json()['detail']
    assert '9.4' not in response.text and 'agents' not in response.json()
    assert c.post('/api/website/quote', headers=h, json={'items':items}).status_code==200


def test_partial_hosted_review_cannot_fill_missing_roles_with_fake_scores(site, monkeypatch):
    from app.routers import website
    c, h, _, _ = site
    _, items = package_items(c)
    class Partial:
        def chat_json(self, *args, **kwargs):
            return {'trip_consultant':{'verdict':'One observation'}}
    monkeypatch.setattr(website, 'get_nim_client', lambda: Partial())
    assert c.post('/api/website/agent-review', headers=h, json={'items':items}).status_code==503
