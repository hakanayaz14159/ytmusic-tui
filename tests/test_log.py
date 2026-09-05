"""Tests for env-gated file logging."""

import logging
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ytmusic_cli.music.services import PlaybackService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackTickAction, Song
from ytmusic_cli.utils.log import (
    LOGGER_NAME,
    configure_logging,
    log_file_path,
    redact_headers,
    redact_url,
    reset_logging,
    vlc_log_file_path,
)


def _flush_app_log() -> None:
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()


@pytest.fixture(autouse=True)
def _reset_logging() -> Generator[None, None, None]:
    reset_logging()
    yield
    reset_logging()


def test_configure_logging_unset_creates_no_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("YTMUSIC_LOG", raising=False)
    monkeypatch.delenv("YTMUSIC_LOG_FILE", raising=False)
    monkeypatch.setattr("ytmusic_cli.utils.log.APP_DIR", tmp_path)

    path = configure_logging()

    assert path is None
    assert log_file_path() is None
    assert vlc_log_file_path() is None
    assert list(tmp_path.glob("ytmusic-*.log")) == []


def test_configure_logging_not_one_creates_no_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YTMUSIC_LOG", "0")
    monkeypatch.setenv("YTMUSIC_LOG_FILE", str(tmp_path / "ytmusic.log"))

    path = configure_logging()

    assert path is None
    assert not (tmp_path / "ytmusic.log").exists()


def test_configure_logging_writes_info_line_to_override_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "ytmusic.log"
    monkeypatch.setenv("YTMUSIC_LOG", "1")
    monkeypatch.setenv("YTMUSIC_LOG_FILE", str(log_path))

    path = configure_logging()
    assert path == log_path
    assert log_file_path() == log_path
    assert vlc_log_file_path() == tmp_path / "ytmusic.vlc.log"

    logging.getLogger(LOGGER_NAME).info("hello-from-test")
    _flush_app_log()

    text = log_path.read_text()
    assert "INFO" in text
    assert "hello-from-test" in text
    assert "ytmusic_cli" in text


def test_configure_logging_default_path_uses_start_datetime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("YTMUSIC_LOG", "1")
    monkeypatch.delenv("YTMUSIC_LOG_FILE", raising=False)
    monkeypatch.setattr("ytmusic_cli.utils.log.APP_DIR", tmp_path)
    started = datetime(2026, 9, 5, 3, 15, 0)

    path = configure_logging(started_at=started)

    assert path == tmp_path / "ytmusic-20260905-031500.log"
    assert path is not None
    assert path.exists()


def test_redact_url_strips_query_string() -> None:
    assert (
        redact_url("https://googlevideo.com/videoplayback?expire=1&sig=secret")
        == "https://googlevideo.com/videoplayback"
    )


def test_redact_headers_masks_cookie_and_authorization() -> None:
    redacted = redact_headers(
        {
            "User-Agent": "test-agent",
            "Cookie": "SID=abc",
            "Authorization": "Bearer tok",
        }
    )
    assert redacted["User-Agent"] == "test-agent"
    assert redacted["Cookie"] == "redacted"
    assert redacted["Authorization"] == "redacted"


def test_logged_message_does_not_include_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "ytmusic.log"
    monkeypatch.setenv("YTMUSIC_LOG", "1")
    monkeypatch.setenv("YTMUSIC_LOG_FILE", str(log_path))
    configure_logging()

    url = "https://googlevideo.com/videoplayback?sig=secret"
    headers = {"Cookie": "SID=abc", "User-Agent": "test-agent"}
    logging.getLogger(LOGGER_NAME).info(
        "stream url=%s headers=%s",
        redact_url(url),
        redact_headers(headers),
    )
    _flush_app_log()

    text = log_path.read_text()
    assert "sig=secret" not in text
    assert "SID=abc" not in text
    assert "redacted" in text
    assert "User-Agent" in text


def test_configure_logging_invalid_path_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    monkeypatch.setenv("YTMUSIC_LOG", "1")
    monkeypatch.setenv("YTMUSIC_LOG_FILE", str(blocker / "nested" / "ytmusic.log"))

    assert configure_logging() is None


def test_fail_playback_logs_engine_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    log_path = tmp_path / "ytmusic.log"
    monkeypatch.setenv("YTMUSIC_LOG", "1")
    monkeypatch.setenv("YTMUSIC_LOG_FILE", str(log_path))
    configure_logging()

    song: Song = {
        "video_id": "synth101",
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 240,
    }
    mock_player.has_ended.return_value = True
    mock_player.has_failed.return_value = False
    mock_player.is_playing.side_effect = None
    mock_player.is_playing.return_value = False
    mock_player.engine_state.return_value = "Ended"

    service = PlaybackService(mock_player, mock_youtube, AppState())
    service.play_song(song)
    tick = service.sync_playback()

    assert tick.action == PlaybackTickAction.FAILED
    _flush_app_log()
    text = log_path.read_text()
    assert "engine_state=Ended" in text
    assert "engine_started=False" in text
    assert "synth101" in text
