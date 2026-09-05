"""Tests for AudioStreamProxy against a local origin (no YouTube)."""

from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

from ytmusic_cli.music.stream_proxy import AudioStreamProxy
from ytmusic_cli.music.types import AudioStream

_AUDIO = b"ID3fake-audio-bytes"
_REQUIRED_HEADER = "Sec-Fetch-Mode"
_REQUIRED_VALUE = "cors"


class _OriginState:
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []


class Origin:
    def __init__(self, url: str, state: _OriginState) -> None:
        self.url = url
        self.requests = state.requests


def _start_origin(state: _OriginState) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            headers = dict(self.headers.items())
            state.requests.append(headers)
            if headers.get(_REQUIRED_HEADER) != _REQUIRED_VALUE:
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Type", "audio/webm")
            self.send_header(
                "Content-Range",
                f"bytes 0-{len(_AUDIO) - 1}/{len(_AUDIO)}",
            )
            self.send_header("Content-Length", str(len(_AUDIO)))
            self.end_headers()
            self.wfile.write(_AUDIO)

        def do_HEAD(self) -> None:
            headers = dict(self.headers.items())
            state.requests.append(headers)
            if headers.get(_REQUIRED_HEADER) != _REQUIRED_VALUE:
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Type", "audio/webm")
            self.send_header("Content-Length", str(len(_AUDIO)))
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@pytest.fixture
def origin() -> Generator[Origin, None, None]:
    state = _OriginState()
    server = _start_origin(state)
    try:
        yield Origin(f"http://127.0.0.1:{server.server_port}/", state)
    finally:
        server.shutdown()
        server.server_close()


def _stream(origin_url: str) -> AudioStream:
    return AudioStream(
        url=origin_url,
        http_headers={
            "User-Agent": "test-agent",
            _REQUIRED_HEADER: _REQUIRED_VALUE,
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        },
    )


def test_origin_rejects_request_without_required_header(origin: Origin) -> None:
    with pytest.raises(HTTPError) as exc_info:
        urlopen(origin.url, timeout=2)
    assert exc_info.value.code == 403


def test_proxy_forwards_required_headers_and_body(origin: Origin) -> None:
    proxy = AudioStreamProxy()
    try:
        local_url = proxy.start(_stream(origin.url))
        with urlopen(local_url, timeout=2) as response:
            assert response.status == 206
            assert response.headers.get_content_type() == "audio/webm"
            assert response.read() == _AUDIO
    finally:
        proxy.stop()

    assert origin.requests
    sent = origin.requests[-1]
    assert sent.get(_REQUIRED_HEADER) == _REQUIRED_VALUE
    assert sent.get("User-Agent") == "test-agent"
    assert sent.get("Accept-Encoding") != "gzip, deflate"
    assert sent.get("Connection") != "keep-alive"


def test_proxy_forwards_range_header(origin: Origin) -> None:
    proxy = AudioStreamProxy()
    try:
        local_url = proxy.start(_stream(origin.url))
        request = Request(local_url, method="GET")
        request.add_header("Range", "bytes=0-1023")
        with urlopen(request, timeout=2) as response:
            assert response.status == 206
            assert response.read() == _AUDIO
    finally:
        proxy.stop()

    assert origin.requests
    assert origin.requests[-1].get("Range") == "bytes=0-1023"


def test_proxy_stop_closes_port(origin: Origin) -> None:
    proxy = AudioStreamProxy()
    local_url = proxy.start(_stream(origin.url))
    proxy.stop()
    with pytest.raises((URLError, OSError, ConnectionError)):
        urlopen(local_url, timeout=1)


def test_proxy_binds_localhost(origin: Origin) -> None:
    proxy = AudioStreamProxy()
    try:
        local_url = proxy.start(_stream(origin.url))
        assert local_url.startswith("http://127.0.0.1:")
    finally:
        proxy.stop()
