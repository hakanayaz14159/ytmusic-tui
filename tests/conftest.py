"""Shared pytest fixtures for YTMusic CLI test suite."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from pytest_mock import MockerFixture

from ytmusic_cli.db.playlist import Playlist
from ytmusic_cli.db.song import Song
from ytmusic_cli.db.user import User
from ytmusic_cli.music.types import Song as SongType

MODELS = [User, Song, Playlist, Playlist.songs.get_through_model()]


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
            "id": 1,
            "title": "Sample Song 1",
            "artist": "Sample Artist 1",
            "album": "Sample Album 1",
            "duration": 210,
            "url": "https://www.youtube.com/watch?v=sample1",
        },
        {
            "id": 2,
            "title": "Sample Song 2",
            "artist": "Sample Artist 2",
            "album": "Sample Album 2",
            "duration": 185,
            "url": "https://www.youtube.com/watch?v=sample2",
        },
    ]

    mock.search.return_value = sample_songs
    mock.get_stream_url.return_value = "https://stream.example.com/audio.m4a"
    mock.stream_sound.return_value = "https://stream.example.com/audio.m4a"
    mock.get_metadata.return_value = {
        "id": "sample1",
        "title": "Sample Song 1",
        "artist": "Sample Artist 1",
        "album": "Sample Album 1",
        "duration": 210,
        "url": "https://www.youtube.com/watch?v=sample1",
        "description": "A sample track description",
        "view_count": 10000,
        "live_status": "not_live",
    }
    mock.download_audio.return_value = "/tmp/downloads/sample1.mp3"
    mock.get_live_stream_info.return_value = {
        "is_live": False,
        "live_status": "not_live",
    }
    return mock


@pytest.fixture
def mock_player(mocker: MockerFixture) -> MagicMock:
    """Provide a mocked audio player engine (VLC abstraction) for silent tests."""
    player = mocker.MagicMock()
    state: dict[str, Any] = {
        "is_playing": False,
        "current_url": None,
        "volume": 80,
        "position": 0.0,
    }

    def _play(url: str) -> None:
        state["is_playing"] = True
        state["current_url"] = url

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

    player.play.side_effect = _play
    player.pause.side_effect = _pause
    player.stop.side_effect = _stop
    player.is_playing.side_effect = _is_playing
    player.set_volume.side_effect = _set_volume
    player.get_volume.side_effect = _get_volume
    player.state = state

    return player
