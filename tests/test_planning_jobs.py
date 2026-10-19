"""Background planning preserves ownership, deduplicates retries and persists results."""
# ruff: noqa: F811
from threading import Event
import time

from tests.test_application_integration import connected_app, trip, user  # noqa: F401


def wait_job(client, headers, url):
    for _ in range(3000):
        response = client.get('/api' + url, headers=headers)
        assert response.status_code == 200, response.text
        job = response.json()
        if job['status'] not in {'queued', 'running'}:
            return job
        time.sleep(0.02)
    raise AssertionError('Background job did not finish')


def test_job_returns_promptly_deduplicates_and_scopes_results(connected_app, monkeypatch):
    from app.routers import assistant
    client, _ = connected_app
    headers = user(client, 'job_owner')
    path = trip(client, headers)
    released, entered = Event(), Event()
    calls = []

    def slow_reply(*args):
        calls.append(args[0])
        entered.set()
        assert released.wait(10)
        return {'orchestration': {'status': 'ok'}, 'reply': {'content': 'Saved test plan'}}

    monkeypatch.setattr(assistant, 'save_message', slow_reply)
    body = {'content': 'Plan my trip', 'page': 'plan'}
    started = time.monotonic()
    response = client.post(path + '/message-jobs', headers=headers, json=body)
    assert response.status_code == 202 and time.monotonic() - started < 2
    job = response.json()
    try:
        assert entered.wait(2)
        duplicate = client.post(path + '/message-jobs', headers=headers, json=body)
        assert duplicate.json()['job_id'] == job['job_id']
        conflict = client.post(path + '/message-jobs', headers=headers, json={'content': 'Another request'})
        assert conflict.status_code == 409
        stranger = user(client, 'job_stranger')
        assert client.get('/api' + job['status_url'], headers=stranger).status_code == 404
        assert client.get('/api' + job['status_url']).status_code == 401
    finally:
        released.set()
    result = wait_job(client, headers, job['status_url'])
    assert result['status'] == 'completed' and len(calls) == 1
    assert result['result']['reply']['content'] == 'Saved test plan'
    assert client.get('/api' + job['status_url'], headers=headers).json() == result


def test_confirm_job_persists_real_offline_plan_and_handles_stale_revision(connected_app):
    client, _ = connected_app
    headers = user(client, 'job_confirm')
    path = trip(client, headers)
    work = client.get(path + '/workspace', headers=headers).json()
    work = client.put(path + '/workspace', headers=headers, json={
        'expected_revision': work['revision'], 'draft': {
            'destination': 'Jaipur', 'start_date': '2026-12-01', 'end_date': '2026-12-03',
            'traveller_count': 2, 'budget': 90000}}).json()
    response = client.post(path + '/confirm-jobs', headers=headers,
                           json={'expected_revision': work['revision'], 'mode': 'manual'})
    assert response.status_code == 202, response.text
    result = wait_job(client, headers, response.json()['status_url'])
    assert result['status'] == 'completed', result
    assert result['result']['orchestration']['status'] == 'ok', result
    assert result['result']['workspace']['plan_ready']
    assert not client.get(path + '/plan', headers=headers).json()['stale']
    stale = client.post(path + '/confirm-jobs', headers=headers,
                        json={'expected_revision': work['revision'], 'mode': 'manual'})
    assert stale.status_code == 409


def test_restart_marks_jobs_failed_without_replaying_provider_calls(connected_app):
    from app.db import get_db
    from app.main import app
    from app.planning_jobs import PlanningJob, recover
    client, _ = connected_app
    headers = user(client, 'job_restart')
    path = trip(client, headers)
    identity = client.get('/api/auth/me', headers=headers).json()
    with next(app.dependency_overrides[get_db]()) as db:
        db.add(PlanningJob(id='interrupted', user_id=identity['id'], conversation_id=path.split('/')[-1],
                           kind='message', status='running', payload={'content': 'Plan my trip'}))
        db.commit()
        recover(db)
    job = client.get(path + '/planning-jobs/interrupted', headers=headers).json()
    assert job['status'] == 'failed' and 'server restarted' in job['error']
