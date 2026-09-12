import os
import tempfile
from uuid import uuid4
from copy import deepcopy

os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(suffix='.db')
from fastapi.testclient import TestClient
from backend import main
from backend.schemas import AIReply, Change
from backend.ai import prepare_changes
import pytest

@pytest.fixture
def client():
    main.attempts.clear()
    with TestClient(main.app, headers={'X-Todo-Client': 'web'}) as c:
        assert c.post('/api/auth/register', json={'username': uuid4().hex, 'password': 'test-password'}).status_code == 200
        yield c

def test_auth_isolation_and_revision(client):
    state = client.get('/api/state').json()
    project = state['projects'][0]['id']
    state['tasks'] = [{'id': 'test-task', 'project_id': project, 'title': 'Read a chapter'}]
    saved = client.put('/api/state', json=state)
    assert saved.status_code == 200
    assert client.put('/api/state', json=state).status_code == 409
    with TestClient(main.app, headers={'X-Todo-Client': 'web'}) as other:
        assert other.get('/api/state').status_code == 401
        other.post('/api/auth/register', json={'username': uuid4().hex, 'password': 'test-password'})
        assert other.get('/api/state').json()['tasks'] == []
    assert client.get('/api/state').json()['tasks'][0]['title'] == 'Read a chapter'
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/state').status_code == 401

def test_csrf_and_validation(client):
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/auth/logout', headers={'X-Todo-Client': ''}).status_code == 403
    state = client.get('/api/state').json()
    state['tasks'] = [{'id': 'x', 'project_id': 'missing', 'title': 'x'}]
    assert client.put('/api/state', json=state).status_code == 422

def test_ai_confirm_undo_and_secret_isolation(client, monkeypatch):
    async def fake(*args):
        return AIReply(message='Here is the draft.', changes=[Change(op='add', fields={'title': 'Practice', 'date': '2026-09-12'})])
    monkeypatch.setattr(main, 'call_model', fake)
    state = client.get('/api/state').json()
    payload = {'project_id': state['projects'][0]['id'], 'message': 'Generate tasks', 'today': '2026-09-12', 'request_id': str(uuid4())}
    assert client.post('/api/chat', json=payload).status_code == 400
    secret = 'test-key-never-expose'
    assert client.put('/api/settings/ai', json={'key': secret}).status_code == 200
    assert secret not in client.get('/api/auth/me').text
    reply = client.post('/api/chat', json=payload)
    assert reply.status_code == 200, reply.text
    assert client.get('/api/state').json()['tasks'] == []
    mid = reply.json()['id']
    with TestClient(main.app, headers={'X-Todo-Client': 'web'}) as other:
        other.post('/api/auth/register', json={'username': uuid4().hex, 'password': 'test-password'})
        assert other.post(f'/api/proposals/{mid}/apply').status_code == 404
        assert other.get('/api/auth/me').json()['ai_enabled'] is False
    applied = client.post(f'/api/proposals/{mid}/apply')
    assert applied.status_code == 200, applied.text
    assert len(applied.json()['tasks']) == 1
    assert client.post(f'/api/proposals/{mid}/apply').json()['revision'] == applied.json()['revision']
    assert client.post(f'/api/proposals/{mid}/undo').json()['tasks'] == []
    assert secret not in client.get('/api/export').text
    payload['request_id'] = str(uuid4())
    mid = client.post('/api/chat', json=payload).json()['id']
    latest = client.get('/api/state').json()
    client.put('/api/state', json=latest)
    assert client.post(f'/api/proposals/{mid}/apply').status_code == 409
    assert client.put('/api/settings/ai', json={'key': ''}).json()['ai_enabled'] is False

@pytest.mark.parametrize('flag', ['locked', 'done'])
def test_ai_cannot_change_protected_task(flag):
    from fastapi import HTTPException
    data = {'projects': [{'id': 'p', 'name': 'P'}], 'tasks': [{'id': 't', 'project_id': 'p', 'title': 'Keep', 'done': False, 'locked': False}]}
    data['tasks'][0][flag] = True
    with pytest.raises(HTTPException):
        prepare_changes(data, 'p', [Change(op='delete', id='t')])
