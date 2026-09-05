"""Shared pytest fixtures for YTMusic CLI test suite."""

import socket
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from pytest_mock import MockerFixture

from ytmusic_cli.db.playlist import Playlist
from ytmusic_cli.db.song import Song
from ytmusic_cli.db.user import User
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import AudioStream
from ytmusic_cli.music.types import Song as SongType
from ytmusic_cli.utils.log import reset_logging

MODELS = [User, Song, Playlist, Playlist.songs.get_through_model()]


@pytest.fixture(scope="session")
def network_available() -> bool:
    try:
        with socket.create_connection(("www.youtube.com", 443), timeout=5):
            return True
    except OSError:
        return False


@pytest.fixture
def requires_network(network_available: bool) -> None:
    if not network_available:
        pytest.skip("no route to www.youtube.com:443 - live contract test skipped")


@pytest.fixture(autouse=True)
def isolate_logging() -> Generator[None, None, None]:
    reset_logging()
    yield
    reset_logging()


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None, None, None]:
    """Reset the AppState singleton before and after every test."""
    AppState().reset()
    yield
    AppState().reset()


@pytest.fixture
def test_db() -> Generator[SqliteDatabase, None, None]:
    """Provide an isolated in-memory SQLite database for unit tests."""
    db = SqliteDatabase(":memory:")
    with db.bind_ctx(MODELS):
        db.create_tables(MODELS)
        yield db
        db.drop_tables(MODELS)
        db.close()


@pytest.fixture
def mock_youtube(mocker: MockerFixture) -> MagicMock:
    """Provide a mocked YouTube client for fast, deterministic, offline tests."""
    mock = mocker.MagicMock()

    sample_songs: list[SongType] = [
        {
            "video_id": "sample1",
            "title": "Sample Song 1",
            "artist": "Sample Artist 1",
            "album": "Sample Album 1",
            "duration": 210,
        },
        {
            "video_id": "sample2",
            "title": "Sample Song 2",
            "artist": "Sample Artist 2",
            "album": "Sample Album 2",
            "duration": 185,
        },
    ]

    # Explicit attribute assignment so isinstance(..., MusicSourceProtocol) works
    # (getattr_static used by runtime_checkable cannot see MagicMock children).
    mock.search = mocker.MagicMock(return_value=sample_songs)
    mock.get_stream = mocker.MagicMock(
        return_value={
            "url": "https://stream.example.com/audio.m4a",
            "http_headers": {
                "User-Agent": "test-agent",
                "Referer": "https://www.youtube.com/",
            },
        }
    )
    mock.suggest = mocker.MagicMock(return_value=["lofi hip hop", "lofi girl"])
    return mock


@pytest.fixture
def mock_player(mocker: MockerFixture) -> MagicMock:
    """Provide a mocked audio player engine (VLC abstraction) for silent tests."""
    player = mocker.MagicMock()
    state: dict[str, Any] = {
        "is_playing": False,
        "current_url": None,
        "current_stream": None,
        "volume": 80,
        "position": 0.0,
    }

    def _play(stream: AudioStream | str) -> None:
        state["is_playing"] = True
        if isinstance(stream, dict):
            state["current_stream"] = stream
            state["current_url"] = stream.get("url")
        else:
            state["current_url"] = stream
            state["current_stream"] = {"url": stream, "http_headers": {}}

    def _pause() -> None:
        state["is_playing"] = False

    def _stop() -> None:
        state["is_playing"] = False
        state["current_url"] = None
        state["position"] = 0.0

    def _is_playing() -> bool:
        return bool(state["is_playing"])

    def _set_volume(volume: int) -> None:
        state["volume"] = max(0, min(100, volume))

    def _get_volume() -> int:
        return int(state["volume"])

    # Explicit attribute assignment so isinstance(..., AudioPlayerProtocol) works
    # (getattr_static used by runtime_checkable cannot see MagicMock children).
    player.play = mocker.MagicMock(side_effect=_play)
    player.pause = mocker.MagicMock(side_effect=_pause)
    player.stop = mocker.MagicMock(side_effect=_stop)
    player.is_playing = mocker.MagicMock(side_effect=_is_playing)
    player.set_volume = mocker.MagicMock(side_effect=_set_volume)
    player.get_volume = mocker.MagicMock(side_effect=_get_volume)
    player.get_position = mocker.MagicMock(return_value=0.0)
    player.has_ended = mocker.MagicMock(return_value=False)
    player.has_failed = mocker.MagicMock(return_value=False)
    player.engine_state = mocker.MagicMock(return_value="Stopped")
    player.state = state

    return player
