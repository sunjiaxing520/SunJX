import logging
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.adapters.music_generation import MusicGenerationInput, MusicProviderError, SunoApiOrgMusicProvider
from app.core.config import music_execution_timeout_seconds, settings
from app.core.credential_crypto import decrypt_credential, encrypt_credential
from app.core.logging import CallbackAccessLogFilter, JsonLogFormatter, TextLogFormatter
from app.core.time import utc_now
from app.models import MusicResult, MusicTask
from app.schemas.music import SunoApiOrgCallbackRequest
from app.services import music
from app.services.task_recovery import recover_stale_music_tasks
from tests.test_music import MusicContext, _headers, _lyrics_version_id, music_context


def configure(context: MusicContext, **changes):
    return context.client.put('/api/v1/music/settings', headers=_headers(context), json={
        'active_implementation': 'sunoapi_org', 'active_model': 'v4.5',
        'sunoapi_org_token': 'test-token-one',
        'sunoapi_org_callback_base_url': 'https://music.example.com', **changes,
    })


def new_task(context: MusicContext, **values) -> int:
    with context.session_factory() as db:
        music._get_or_create_music_settings(db)
        task = MusicTask(
            title='Test song', lyrics='Test lyrics', style_prompt='pop', negative_tags=[],
            **({'provider_implementation': 'sunoapi_org', 'model': 'v4.5',
                'provider_token_encrypted': encrypt_credential('test-token-one')} | values),
        )
        db.add(task)
        db.commit()
        return task.id


def due(context: MusicContext, task_id: int) -> None:
    with context.session_factory() as db:
        db.get(MusicTask, task_id).next_attempt_at = utc_now() - timedelta(seconds=1)
        db.commit()


def callback(context: MusicContext, task_id: int, stage='complete', external='job-1', code=200):
    with context.session_factory() as db:
        signature = music._sunoapi_org_callback_signature(music._get_or_create_music_settings(db), task_id)
        return music.handle_sunoapi_org_callback(db, task_id, signature,
            SunoApiOrgCallbackRequest.model_validate({
                'code': code, 'msg': 'notification',
                'data': {'task_id': external, 'callbackType': stage},
            }))


def provider_factory(monkeypatch, handler):
    monkeypatch.setattr(music, 'get_music_provider', lambda _implementation, **kwargs:
        SunoApiOrgMusicProvider(**kwargs, transport=httpx.MockTransport(handler)))


def success_body():
    return {'code': 200, 'data': {'taskId': 'job-1', 'status': 'SUCCESS', 'response': {
        'sunoData': [{'id': f'track-{i}', 'audioUrl': f'https://audio.test/{i}.mp3',
                     'title': f'Test {i}', 'duration': 120} for i in [1, 2]],
    }}}


@pytest.mark.parametrize('failure', ['read_timeout', 'write_error', 'server_error', 'invalid_json', 'missing_id'])
def test_ambiguous_submission_is_never_automatically_retried(failure):
    def handler(request):
        if failure == 'read_timeout':
            raise httpx.ReadTimeout('timeout', request=request)
        if failure == 'write_error':
            raise httpx.WriteError('write failed', request=request)
        if failure == 'server_error':
            return httpx.Response(502)
        if failure == 'invalid_json':
            return httpx.Response(200, text='unreadable')
        return httpx.Response(200, json={'code': 200, 'data': {}})
    provider = SunoApiOrgMusicProvider(api_key='test', callback_url='https://music.example.com/callback',
        transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MusicProviderError) as exc:
            provider.generate(MusicGenerationInput('Song', 'lyrics', 'pop', False, [], None))
        assert exc.value.code == 'SUNOAPI_SUBMISSION_UNKNOWN'
        assert not exc.value.retryable
    finally:
        provider.close()


@pytest.mark.parametrize(('status', 'body', 'code', 'retryable'), [
    (429, None, 'SUNOAPI_RATE_LIMITED', True),
    (200, {'code': 429}, 'SUNOAPI_QUOTA_EXHAUSTED', False),
    (401, None, 'SUNOAPI_AUTH_FAILED', False),
    (503, None, 'SUNOAPI_UPSTREAM_ERROR', True),
    (200, {'code': 455}, 'SUNOAPI_UPSTREAM_ERROR', True),
])
def test_poll_errors_distinguish_rate_limit_and_credits(status, body, code, retryable):
    provider = SunoApiOrgMusicProvider(api_key='test', transport=httpx.MockTransport(
        lambda _: httpx.Response(status, json=body)))
    try:
        with pytest.raises(MusicProviderError) as exc:
            provider.get_quota()
        assert exc.value.code == code
        assert exc.value.retryable is retryable
    finally:
        provider.close()


def test_callbacks_and_polling_produce_two_results_once(music_context, monkeypatch):
    context = music_context
    assert configure(context).status_code == 200
    requests = []
    ready = False
    task_id = new_task(context)

    def handler(request):
        requests.append(request)
        if request.method == 'POST':
            # Notification can arrive before the submission response.
            callback(context, task_id)
            with context.session_factory() as db:
                assert db.get(MusicTask, task_id).status == 'running'
                assert music.execute_music_task_in_session(db, task_id).status == 'ignored'
            return httpx.Response(200, json={'code': 200, 'data': {'taskId': 'job-1'}})
        if request.url.path.endswith('/credit'):
            return httpx.Response(200, json={'code': 200, 'data': 80})
        return httpx.Response(200, json=success_body() if ready else
            {'code': 200, 'data': {'taskId': 'job-1', 'status': 'PENDING'}})

    provider_factory(monkeypatch, handler)
    with context.session_factory() as db:
        outcome = music.execute_music_task_in_session(db, task_id)
        assert outcome.status == 'waiting_provider'
        assert outcome.retry_delay_seconds >= 5
        assert music.execute_music_task_in_session(db, task_id).status == 'ignored'
    assert callback(context, task_id)[1] is False
    assert callback(context, task_id, stage='text')[1] is False
    due(context, task_id)
    with context.session_factory() as db:
        assert music.execute_music_task_in_session(db, task_id).status == 'waiting_provider'
        assert db.get(MusicTask, task_id).attempt_count == 1
    ready = True
    due(context, task_id)
    with context.session_factory() as db:
        assert music.execute_music_task_in_session(db, task_id).status == 'completed'
        assert music.execute_music_task_in_session(db, task_id).status == 'ignored'
        assert db.scalar(select(func.count(MusicResult.id))) == 2
        assert len(music.get_music_task(db, task_id).api_usage) == 2
    assert callback(context, task_id, stage='error', code=500)[1] is False
    assert sum(req.method == 'POST' for req in requests) == 1


def test_callback_error_must_be_verified_with_provider(music_context, monkeypatch):
    context = music_context
    configure(context)
    task_id = new_task(context, external_task_id='job-1')
    assert callback(context, task_id, stage='error', code=500)[1] is True
    with context.session_factory() as db:
        assert db.get(MusicTask, task_id).status == 'pending'
    provider_factory(monkeypatch, lambda request: httpx.Response(200, json=(
        {'code': 200, 'data': 80} if request.url.path.endswith('/credit') else success_body())))
    with context.session_factory() as db:
        assert music.execute_music_task_in_session(db, task_id).status == 'completed'


def test_upstream_pending_job_holds_capacity(music_context, monkeypatch):
    context = music_context
    configure(context)
    monkeypatch.setattr(settings, 'MUSIC_MAX_CONCURRENCY', 1)
    first = new_task(context, external_task_id='job-1', provider_submitted_at=utc_now())
    second = new_task(context)
    with context.session_factory() as db:
        assert music.execute_music_task_in_session(db, second).status == 'waiting_capacity'
        assert db.get(MusicTask, second).attempt_count == 0
        db.get(MusicTask, first).status = 'completed'
        db.commit()
    due(context, second)
    with context.session_factory() as db:
        assert music.execute_music_task_in_session(db, second).status == 'completed'


def test_atomic_claim_rejects_stale_session(music_context):
    task_id = new_task(music_context, provider_implementation='official')
    with music_context.session_factory() as first, music_context.session_factory() as second:
        stale = second.get(MusicTask, task_id)
        current = first.get(MusicTask, task_id)
        assert music._claim_music_task(first, current) is None
        assert music._claim_music_task(second, stale).status == 'ignored'


def test_timeout_preserves_id_and_manual_retry_only_queries(music_context, monkeypatch):
    context = music_context
    configure(context)
    task_id = new_task(context, external_task_id='job-1', attempt_count=1,
        provider_submitted_at=utc_now() - timedelta(seconds=settings.SUNO_GENERATION_TIMEOUT_SECONDS + 1))
    methods = []
    def handler(request):
        methods.append(request.method)
        return httpx.Response(200, json={'code': 200, 'data': {'taskId': 'job-1', 'status': 'PENDING'}})
    provider_factory(monkeypatch, handler)
    with context.session_factory() as db:
        assert music.execute_music_task_in_session(db, task_id).status == 'failed'
        task = db.get(MusicTask, task_id)
        assert task.error_code == 'SUNO_GENERATION_TIMEOUT'
        assert task.external_task_id == 'job-1'
        assert task.attempt_count == 1
        monkeypatch.setattr(music, 'dispatch_music_task', lambda db, ident: music.get_music_task(db, ident))
        music.retry_music_task(db, task_id)
        assert music.execute_music_task_in_session(db, task_id).status == 'waiting_provider'
    assert methods == ['GET', 'GET']


def test_interrupted_submit_pauses_and_late_callback_can_recover(music_context):
    context = music_context
    configure(context)
    started = utc_now() - timedelta(seconds=music_execution_timeout_seconds() + 1)
    unknown = new_task(context, status='running', started_at=started)
    known = new_task(context, status='running', started_at=started, external_task_id='job-2')
    with context.session_factory() as db:
        assert recover_stale_music_tasks(db) == 2
        assert db.get(MusicTask, unknown).error_code == 'SUNOAPI_SUBMISSION_UNKNOWN'
        assert db.get(MusicTask, known).status == 'pending'
    retry = context.client.post(f'/api/v1/music/tasks/{unknown}/retry', headers=_headers(context))
    assert retry.status_code == 409
    assert callback(context, unknown)[1] is True
    with context.session_factory() as db:
        assert db.get(MusicTask, unknown).external_task_id == 'job-1'
        assert db.get(MusicTask, unknown).status == 'pending'


@pytest.mark.parametrize('url', ['http://example.com', 'https://localhost', 'https://127.0.0.1',
    'https://10.0.0.2', 'https://example.com/api/v1', 'https://example.com?token=secret',
    'https://[invalid', 'https://example.com:invalid'])
def test_reject_invalid_callback_origin(music_context, url):
    response = configure(music_context, sunoapi_org_callback_base_url=url)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'SUNOAPI_CALLBACK_URL_INVALID'


def test_clear_token_and_hot_switch_preserve_old_job_credential(music_context, monkeypatch):
    context = music_context
    configure(context)
    monkeypatch.setattr('app.api.v1.routes.music.dispatch_music_task', lambda db, ident: music.get_music_task(db, ident))
    created = context.client.post('/api/v1/music/tasks', headers=_headers(context),
        json={'lyrics_version_id': _lyrics_version_id(context)})
    task_id = created.json()['id']
    assert configure(context, sunoapi_org_token='test-token-two').status_code == 200
    with context.session_factory() as db:
        task = db.get(MusicTask, task_id)
        assert decrypt_credential(task.provider_token_encrypted) == 'test-token-one'
        assert 'provider_token_encrypted' not in created.text
    monkeypatch.setattr(settings, 'SUNOAPI_ORG_API_KEY', 'environment-fallback')
    cleared = context.client.put('/api/v1/music/settings', headers=_headers(context),
        json={'clear_sunoapi_org_token': True})
    assert cleared.status_code == 200
    assert cleared.json()['sunoapi_org_token_configured'] is False
    with context.session_factory() as db:
        assert music._sunoapi_org_token(music._get_or_create_music_settings(db)) == ''
        assert decrypt_credential(db.get(MusicTask, task_id).provider_token_encrypted) == 'test-token-one'


def test_member_cannot_read_or_update_credentials(music_context):
    context = music_context
    configure(context)
    member = context.client.post('/api/v1/users', headers=_headers(context),
        json={'username': 'music.member', 'password': 'member-password', 'music_quota_remaining': 1}).json()
    context.client.put(f"/api/v1/users/{member['id']}/agent-permissions", headers=_headers(context),
        json={'agents': ['music']})
    login = context.client.post('/api/v1/auth/login', json={'username': 'music.member', 'password': 'member-password'})
    headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
    response = context.client.get('/api/v1/music/settings', headers=headers)
    assert response.json()['sunoapi_org_token_hint'] is None
    assert response.json()['sunoapi_org_callback_base_url'] is None
    assert 'test-token-one' not in response.text
    assert context.client.put('/api/v1/music/settings', headers=headers,
        json={'active_model': 'v5'}).status_code == 403


def test_callback_secret_redacted_in_app_and_access_logs():
    signature = 'a' * 64
    path = f'/api/v1/music/callbacks/sunoapi-org/1/{signature}'
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 1,
        '%s - "%s %s HTTP/%s" %d', ('client', 'POST', path, '1.1', 200), None)
    assert CallbackAccessLogFilter().filter(record)
    assert signature not in record.getMessage()
    record.path = path
    for formatter in [JsonLogFormatter(), TextLogFormatter()]:
        assert signature not in formatter.format(record)


@pytest.mark.parametrize('model', ['v3.5', 'invalid'])
def test_invalid_model_rolls_back_settings(music_context, model):
    assert configure(music_context).status_code == 200
    response = configure(music_context, active_model=model)
    assert response.status_code == 422
    assert music_context.client.get('/api/v1/music/settings', headers=_headers(music_context)).json()['active_model'] == 'v4.5'


def test_late_callback_after_submit_timeout_prevents_duplicate_post(music_context, monkeypatch):
    context = music_context
    configure(context)
    task_id = new_task(context)
    def handler(request):
        callback(context, task_id)
        raise httpx.ReadTimeout('lost response', request=request)
    provider_factory(monkeypatch, handler)
    with context.session_factory() as db:
        result = music.execute_music_task_in_session(db, task_id)
        assert result.status == 'waiting_provider'
        assert db.get(MusicTask, task_id).external_task_id == 'job-1'


@pytest.mark.parametrize(('model', 'title', 'lyrics', 'style'), [
    ('v4', 'x' * 81, 'lyrics', 'pop'),
    ('v4.5', 'x' * 101, 'lyrics', 'pop'),
    ('v4.5all', 'x' * 81, 'lyrics', 'pop'),
    ('v4.5', 'song', 'x' * 5001, 'pop'),
    ('v4', 'song', 'lyrics', 'x' * 201),
])
def test_parameter_limits_reject_before_sending(model, title, lyrics, style):
    provider = SunoApiOrgMusicProvider(api_key='test', model=model,
        callback_url='https://music.example.com/callback',
        transport=httpx.MockTransport(lambda _: pytest.fail('must not submit')))
    try:
        with pytest.raises(MusicProviderError) as exc:
            provider.generate(MusicGenerationInput(title, lyrics, style, False, [], None))
        assert exc.value.code == 'SUNOAPI_PARAMETER_TOO_LONG'
    finally:
        provider.close()


def test_unsupported_operations_reject_before_charging_quota(music_context, monkeypatch):
    context = music_context
    with context.session_factory() as db:
        source_id = new_task(context, provider_implementation='official')
        music.execute_music_task_in_session(db, source_id)
        result_id = music.get_music_task(db, source_id).results[0].id
    configure(context)
    monkeypatch.setattr(music, '_consume_music_task_quota', lambda *_: pytest.fail('must not charge quota'))
    for operation, payload in [('extend', {}), ('adapt', {'adaptation_mode': 'recreate', 'rights_confirmed': True})]:
        response = context.client.post(f'/api/v1/music/results/{result_id}/{operation}',
            headers=_headers(context), json=payload)
        assert response.status_code == 422
        assert response.json()['error']['code'] == 'SUNOAPI_OPERATION_NOT_SUPPORTED'


def test_callback_cannot_change_external_task_id(music_context):
    configure(music_context)
    task_id = new_task(music_context, external_task_id='original')
    from app.core.exceptions import AppException
    with pytest.raises(AppException) as exc:
        callback(music_context, task_id, external='other-job')
    assert exc.value.code == 'SUNOAPI_CALLBACK_TASK_CONFLICT'
