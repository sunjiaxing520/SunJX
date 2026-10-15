import socket

import httpx
import pytest

from app.core.config import settings
from app.services import music_storage


@pytest.fixture
def fake_ip_dns(monkeypatch):
    monkeypatch.setattr(settings, "MUSIC_DOWNLOAD_DOH_FALLBACK", True)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.0.113", 443)),
    ])


def test_fake_ip_download_pins_public_address_and_preserves_tls_identity(fake_ip_dns, monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.host == "cloudflare-dns.com":
            assert dict(request.url.params) == {"name": "audio.test", "type": "A"}
            return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 1, "data": "8.8.8.8"}]})
        assert request.url.host == "8.8.8.8"
        assert request.headers["host"] == "audio.test"
        assert request.extensions["sni_hostname"] == "audio.test"
        return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"audio-fixture")

    original_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    path = music_storage._download_to_temp("https://audio.test/song.mp3?signature=fixture")
    try:
        assert path.read_bytes() == b"audio-fixture"
        assert len(calls) == 2
    finally:
        path.unlink()


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
def test_private_dns_is_still_blocked_with_fallback_enabled(monkeypatch, address):
    monkeypatch.setattr(settings, "MUSIC_DOWNLOAD_DOH_FALLBACK", True)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
    ])
    with pytest.raises(music_storage.MusicStorageError, match="非公网"):
        music_storage._validate_public_https_url("https://audio.test/song.mp3")


@pytest.mark.parametrize("answers", [[], [{"type": 1, "data": "127.0.0.1"}],
                                    [{"type": 1, "data": "8.8.8.8"}, {"type": 1, "data": "10.0.0.1"}]])
def test_doh_empty_private_or_mixed_answers_are_rejected(fake_ip_dns, answers):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json={"Status": 0, "Answer": answers},
    ))) as client:
        with pytest.raises(music_storage.MusicStorageError, match="核验未通过"):
            music_storage._validate_public_https_url("https://audio.test/song.mp3", client=client)


def test_fake_ip_literal_and_disabled_fallback_are_blocked(fake_ip_dns, monkeypatch):
    with pytest.raises(music_storage.MusicStorageError, match="非公网"):
        music_storage._validate_public_https_url("https://198.18.0.113/song.mp3")
    monkeypatch.setattr(settings, "MUSIC_DOWNLOAD_DOH_FALLBACK", False)
    with pytest.raises(music_storage.MusicStorageError, match="非公网"):
        music_storage._validate_public_https_url("https://audio.test/song.mp3")


def test_redirect_to_private_network_is_blocked(fake_ip_dns, monkeypatch):
    original_client = httpx.Client
    contacted_private = False

    def handle(request):
        nonlocal contacted_private
        if request.url.host == "cloudflare-dns.com":
            return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 1, "data": "8.8.8.8"}]})
        if request.url.host == "8.8.8.8":
            return httpx.Response(302, headers={"location": "https://198.18.0.113/private"})
        contacted_private = True
        raise AssertionError("Must not request a private address")

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(music_storage.MusicStorageError, match="非公网"):
        music_storage._download_to_temp("https://audio.test/song.mp3")
    assert not contacted_private
