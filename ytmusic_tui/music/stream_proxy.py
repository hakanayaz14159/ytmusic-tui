"""Localhost HTTP proxy that applies AudioStream headers VLC cannot send."""

import logging
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ytmusic_tui.music.types import AudioStream
from ytmusic_tui.utils.log import redact_url

logger = logging.getLogger(__name__)

_CLIENT_GONE: tuple[
    type[BrokenPipeError],
    type[ConnectionResetError],
    type[ConnectionAbortedError],
] = (
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
)


class _Writable(Protocol):
    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...


class _HTTPStatusWriter(Protocol):
    def send_response(self, code: int, message: str | None = None) -> None: ...

    def end_headers(self) -> None: ...


_SKIP_HTTP_HEADERS = frozenset(
    {
        "accept-encoding",
        "content-encoding",
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "host",
        "content-length",
    }
)
_FORWARD_RESPONSE_HEADERS: tuple[str, str, str] = (
    "Content-Type",
    "Content-Range",
    "Content-Length",
)
_CHUNK_SIZE = 65536
_UPSTREAM_TIMEOUT = 30.0


def _upstream_headers(
    stream_headers: Mapping[str, str],
    range_header: str | None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in stream_headers.items():
        if name.lower() in _SKIP_HTTP_HEADERS:
            continue
        headers[name] = value
    if range_header:
        headers["Range"] = range_header
    return headers


def _write_body(wfile: _Writable, data: bytes) -> bool:
    try:
        wfile.write(data)
        wfile.flush()
    except _CLIENT_GONE:
        logger.debug("proxy client disconnected")
        return False
    return True


def _send_status(handler: _HTTPStatusWriter, code: int) -> None:
    try:
        handler.send_response(code)
        handler.end_headers()
    except _CLIENT_GONE:
        logger.debug("proxy client disconnected")


def _handler_for(stream: AudioStream) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            self._forward("GET")

        def do_HEAD(self) -> None:
            self._forward("HEAD")

        def handle(self) -> None:
            try:
                super().handle()
            except _CLIENT_GONE:
                logger.debug("proxy client disconnected")

        def _forward(self, method: str) -> None:
            request = Request(
                stream["url"],
                headers=_upstream_headers(
                    stream["http_headers"],
                    self.headers.get("Range"),
                ),
                method=method,
            )
            try:
                with urlopen(request, timeout=_UPSTREAM_TIMEOUT) as upstream:
                    self.send_response(upstream.status)
                    for name in _FORWARD_RESPONSE_HEADERS:
                        value = upstream.headers.get(name)
                        if value:
                            self.send_header(name, value)
                    self.end_headers()
                    if method == "HEAD":
                        return
                    while True:
                        chunk = upstream.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        if not _write_body(self.wfile, chunk):
                            return
            except _CLIENT_GONE:
                logger.debug("proxy client disconnected")
            except HTTPError as err:
                logger.error(
                    "proxy upstream http %s url=%s range=%s",
                    err.code,
                    redact_url(stream["url"]),
                    self.headers.get("Range"),
                )
                _send_status(self, err.code)
            except (URLError, OSError, TimeoutError):
                logger.exception(
                    "proxy upstream failed url=%s",
                    redact_url(stream["url"]),
                )
                _send_status(self, 502)

    return Handler


class AudioStreamProxy:
    """Serves one AudioStream on 127.0.0.1 so libVLC does not fetch the CDN."""

    def __init__(self) -> None:
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self, stream: AudioStream) -> str:
        self.stop()
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(stream))
        thread = Thread(
            target=server.serve_forever,
            daemon=True,
            name="audio-stream-proxy",
        )
        thread.start()
        self._server = server
        self._thread = thread
        local_url = f"http://127.0.0.1:{server.server_port}/"
        logger.info(
            "proxy start url=%s via=%s",
            redact_url(stream["url"]),
            local_url,
        )
        return local_url

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        logger.info("proxy stop")
        Thread(
            target=self._close_server,
            args=(server, thread),
            daemon=True,
            name="audio-stream-proxy-cleanup",
        ).start()

    @staticmethod
    def _close_server(server: ThreadingHTTPServer, thread: Thread | None) -> None:
        server.shutdown()
        server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)
