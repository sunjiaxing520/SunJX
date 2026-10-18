"""Opt-in recovery for official text hosts intercepted by a local Fake-IP TUN."""

import ipaddress
import socket
from typing import Any

import httpx

OFFICIAL_HOSTS = frozenset({'api.moonshot.cn', 'open.bigmodel.cn'})
FAKE_NETWORK = ipaddress.ip_network('198.18.0.0/15')


def _is_fake(value: str) -> bool:
    return ipaddress.ip_address(value) in FAKE_NETWORK


def _public_ips(host: str) -> list[str]:
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as resolver:
        response = resolver.get('https://1.1.1.1/dns-query', params={'name': host, 'type': 'A'},
                                headers={'accept': 'application/dns-json'})
        response.raise_for_status()
        body = response.json()
    if body.get('Status') != 0:
        raise ValueError('Public DNS resolution failed')
    ips = [answer['data'] for answer in body.get('Answer', []) if answer.get('type') == 1]
    if not ips or any(not ipaddress.IPv4Address(value).is_global
                      or ipaddress.IPv4Address(value).is_multicast
                      or ipaddress.IPv4Address(value).is_reserved for value in ips):
        raise ValueError('Public DNS returned unsafe addresses')
    return list(dict.fromkeys(ips))[:2]


def _local_addresses() -> list[str]:
    addresses = [entry[4][0] for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    return list(dict.fromkeys(value for value in addresses
        if ipaddress.IPv4Address(value).is_private
        and not ipaddress.IPv4Address(value).is_loopback
        and not ipaddress.IPv4Address(value).is_link_local
        and not _is_fake(value)))[:4]


def recover_fake_ip_post(url: str, *, headers: dict[str, str], json: dict[str, Any],
                         timeout: float, original_error: httpx.ConnectError) -> httpx.Response:
    target = httpx.URL(url)
    # Do not forward credentials to arbitrary hosts, custom ports or redirects.
    if target.scheme != 'https' or target.host not in OFFICIAL_HOSTS or target.port not in (None, 443) or target.userinfo:
        raise original_error
    try:
        resolved = [entry[4][0] for entry in socket.getaddrinfo(target.host, 443, socket.AF_INET)]
        if not resolved or not all(_is_fake(value) for value in resolved):
            raise original_error
        public_ips = _public_ips(target.host)
        local_addresses = _local_addresses()
    except (OSError, ValueError, httpx.HTTPError):
        raise original_error
    for local in local_addresses:
        for public in public_ips:
            transport = httpx.HTTPTransport(local_address=local, retries=0)
            try:
                with httpx.Client(transport=transport, trust_env=False, follow_redirects=False,
                                  timeout=httpx.Timeout(timeout, connect=min(timeout, 5))) as client:
                    response = client.post(target.copy_with(host=public),
                        headers={**headers, 'Host': target.host}, json=json,
                        extensions={'sni_hostname': target.host})
                    response.request.url = target
                    return response
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # Only connection setup failures are safe to try on another interface.
                continue
    raise original_error
