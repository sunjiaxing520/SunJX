from types import SimpleNamespace

import httpx
import pytest

from app.adapters import text_network as network


@pytest.mark.parametrize('url', ['https://evil.example/v1', 'http://api.moonshot.cn/v1',
    'https://api.moonshot.cn:8443/v1', 'https://user:pass@api.moonshot.cn/v1'])
def test_fallback_rejects_non_official_destinations(url, monkeypatch):
    monkeypatch.setattr(network.socket, 'getaddrinfo', lambda *args: pytest.fail('must not resolve rejected host'))
    original = httpx.ConnectError('SSL failed')
    with pytest.raises(httpx.ConnectError) as caught:
        network.recover_fake_ip_post(url, headers={}, json={}, timeout=5, original_error=original)
    assert caught.value is original


def test_fallback_pins_public_ip_and_keeps_tls_identity(monkeypatch):
    monkeypatch.setattr(network.socket, 'getaddrinfo', lambda *args: [(None, None, None, '', ('198.18.0.7', 443))])
    monkeypatch.setattr(network, '_public_ips', lambda _: ['8.8.8.8'])
    monkeypatch.setattr(network, '_local_addresses', lambda: ['192.168.1.4'])
    seen = {}
    class Client:
        def __init__(self, **kwargs): seen['client'] = kwargs
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, **kwargs):
            seen.update(url=url, **kwargs)
            return httpx.Response(200, json={'ok': True}, request=httpx.Request('POST', url))
    monkeypatch.setattr(network.httpx, 'Client', Client)
    response = network.recover_fake_ip_post('https://api.moonshot.cn/v1/chat/completions',
        headers={'Authorization': 'Bearer fixture'}, json={'model': 'fixture'}, timeout=5,
        original_error=httpx.ConnectError('SSL failed'))
    assert seen['url'].host == '8.8.8.8'
    assert seen['headers']['Host'] == 'api.moonshot.cn'
    assert seen['extensions']['sni_hostname'] == 'api.moonshot.cn'
    assert seen['client']['follow_redirects'] is False
    assert 'verify' not in seen['client']
    assert response.request.url.host == 'api.moonshot.cn'


@pytest.mark.parametrize('addresses', [['127.0.0.1'], ['8.8.8.8', '192.168.1.1'], ['224.0.0.1'], []])
def test_public_resolution_rejects_unsafe_or_empty_answers(monkeypatch, addresses):
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args, **kwargs):
            return SimpleNamespace(raise_for_status=lambda: None,
                json=lambda: {'Status': 0, 'Answer': [{'type': 1, 'data': ip} for ip in addresses]})
    monkeypatch.setattr(network.httpx, 'Client', Client)
    with pytest.raises(ValueError): network._public_ips('api.moonshot.cn')


def test_normal_dns_never_uses_fallback(monkeypatch):
    monkeypatch.setattr(network.socket, 'getaddrinfo', lambda *args: [(None, None, None, '', ('8.8.8.8', 443))])
    monkeypatch.setattr(network, '_public_ips', lambda _: pytest.fail('no fallback for normal DNS'))
    with pytest.raises(httpx.ConnectError):
        network.recover_fake_ip_post('https://api.moonshot.cn/v1', headers={}, json={}, timeout=5,
                                     original_error=httpx.ConnectError('SSL failed'))
