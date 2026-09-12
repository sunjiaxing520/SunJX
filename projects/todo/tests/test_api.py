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

def test_balance_requires_own_key(client, monkeypatch):
    assert client.get('/api/settings/ai/balance').status_code == 400
    async def fake(key):
        assert key == 'balance-test-key'
        return {'available_balance': 0, 'cash_balance': -1, 'voucher_balance': 0, 'currency': 'CNY'}
    monkeypatch.setattr(main, 'fetch_balance', fake)
    client.put('/api/settings/ai', json={'key': 'balance-test-key'})
    response = client.get('/api/settings/ai/balance')
    assert response.status_code == 200
    assert response.json()['available_balance'] == 0
    assert 'checked_at' in response.json()
    assert 'balance-test-key' not in response.text
    with TestClient(main.app, headers={'X-Todo-Client': 'web'}) as other:
        other.post('/api/auth/register', json={'username': uuid4().hex, 'password': 'test-password'})
        assert other.get('/api/settings/ai/balance').status_code == 400

@pytest.mark.parametrize('body,valid', [
    ({'code':0,'status':True,'data':{'available_balance':0,'cash_balance':-1,'voucher_balance':0}},True),
    ({'code':0,'status':True,'data':{'available_balance':1}},False),
    ({'code':0,'status':False,'data':{}},False),
    ({'code':0,'status':True,'data':{'available_balance':'NaN','cash_balance':0,'voucher_balance':0}},False),
])
def test_balance_provider_validation(body, valid, monkeypatch):
    import asyncio, httpx
    from backend import ai
    from fastapi import HTTPException
    async def get(self, url, **kwargs):
        assert url == 'https://api.moonshot.cn/v1/users/me/balance'
        return httpx.Response(200, json=body)
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    if valid:
        assert asyncio.run(ai.fetch_balance('test'))['cash_balance'] == -1
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(ai.fetch_balance('test'))
        assert error.value.status_code == 502

def test_memo_binding_tasks_and_kimi(client,monkeypatch):
    snapshot={'progress':{'finished':12,'total':30,'study_time':180000},'words':[],'date':'2026-09-12','checked_at':'2026-09-12T01:00:00Z','list_limited':False}
    async def fetch(key):
        assert key=='memo-test-token'
        return snapshot
    monkeypatch.setattr(main,'read_today',fetch)
    assert client.get('/api/memo/status').json()=={'bound':False}
    assert client.get('/api/memo/today').status_code==400
    state=client.get('/api/state').json()
    state['tasks']=[{'id':'vocab','project_id':state['projects'][0]['id'],'title':'背单词','task_type':'vocabulary'}]
    assert client.put('/api/state',json=state).status_code==400
    result=client.put('/api/memo/key',json={'key':'memo-test-token'})
    assert result.status_code==200
    assert 'memo-test-token' not in result.text
    assert client.put('/api/state',json=state).status_code==200
    with TestClient(main.app,headers={'X-Todo-Client':'web'}) as other:
        other.post('/api/auth/register',json={'username':uuid4().hex,'password':'test-password'})
        assert other.get('/api/memo/status').json()=={'bound':False}
        assert other.get('/api/memo/today').status_code==400
    async def model(key,model,messages):
        assert 'memo-test-token' not in str(messages)
        assert '180000' in str(messages)
        return AIReply(message='已完成12词，还需18词，学习3分钟。')
    monkeypatch.setattr(main,'call_model',model)
    client.put('/api/settings/ai',json={'key':'kimi-test-token'})
    assert client.post('/api/memo/analyze',json={}).status_code==200
    from fastapi import HTTPException
    async def failure(key): raise HTTPException(502,'provider unavailable')
    monkeypatch.setattr(main,'read_today',failure)
    assert client.put('/api/memo/key',json={'key':'another-token'}).status_code==502
    assert client.get('/api/memo/status').json()['bound'] is True
    assert 'memo-test-token' not in client.get('/api/export').text
    assert client.delete('/api/memo/key').status_code==200
    assert client.get('/api/memo/status').json()['bound'] is False
    assert client.get('/api/state').json()['tasks'][0]['task_type']=='vocabulary'

@pytest.mark.parametrize("wrapped", [False, True])
def test_memo_official_contract(monkeypatch, wrapped):
    import asyncio,httpx
    from backend.memo import read_today
    async def post(self,url,**kwargs):
        assert url.startswith('https://open.maimemo.com/open/api/v1/memo/study/')
        assert self.headers['Authorization']=='Bearer token'
        if url.endswith('get_study_progress'):
            body={'progress':{'finished':0,'total':0,'study_time':0}}
            return httpx.Response(200,json={'success':True,'data':body} if wrapped else body)
        assert kwargs['json']=={'limit':1000}
        body={'today_items':[{'voc_id':'1','spelling' if wrapped else 'voc_spelling':'learn','is_new':True,'is_finished':False}]}
        return httpx.Response(200,json={'success':True,'data':body} if wrapped else body)
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    result=asyncio.run(read_today('token'))
    assert result['progress']['total']==0
    assert result['words'][0]['voc_spelling']=='learn'

@pytest.mark.parametrize('upstream,expected', [(401,422),(403,422),(429,424),(500,424)])
def test_memo_provider_errors_keep_json(client,monkeypatch,upstream,expected):
    import httpx
    async def post(self,url,**kwargs):
        return httpx.Response(upstream,text='private provider response')
    monkeypatch.setattr(httpx.AsyncClient,'post',post)
    response=client.put('/api/memo/key',json={'key':'invalid-test-token'})
    assert response.status_code==expected
    assert response.headers['content-type']=='application/json'
    assert isinstance(response.json()['detail'],str)
    assert 'private provider response' not in response.text
    assert client.get('/api/memo/status').json()=={'bound':False}
