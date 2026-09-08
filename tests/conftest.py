"""Shared pytest fixtures for YTMusic TUI test suite."""

import socket
from collections.abc import Generator
from typing import TypedDict, cast
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from pytest_mock import MockerFixture

from ytmusic_tui.db.app_config import AppConfig
from ytmusic_tui.db.playlist import Playlist
from ytmusic_tui.db.song import Song
from ytmusic_tui.db.user import User
from ytmusic_tui.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
    SettingsService,
)
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import AudioStream, default_startup_settings
from ytmusic_tui.music.types import Song as SongType
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.utils.log import reset_logging

MODELS = [User, Song, Playlist, Playlist.songs.get_through_model(), AppConfig]


class MockPlayerState(TypedDict):
    is_playing: bool
    current_url: str | None
    current_stream: AudioStream | None
    volume: int
    position: float


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
def fast_suggest_debounce(monkeypatch: pytest.MonkeyPatch) -> None:
    # Textual Timer rejects interval 0.
    monkeypatch.setattr(
        "ytmusic_tui.tui.modes.search.SUGGEST_DEBOUNCE_SECONDS",
        0.01,
    )


@pytest.fixture(autouse=True)
def isolate_skip_keymap_detection(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if request.module.__name__ == "tests.test_skip_keymap":
        return
    monkeypatch.setattr(
        "ytmusic_tui.tui.skip_keymap.detect_skip_keymap",
        lambda: None,
    )


@pytest.fixture(autouse=True)
def reset_app_state() -> Generator[None, None, None]:
    """Reset the AppState singleton before and after every test."""
    AppState().reset()
    yield
    AppState().reset()


@pytest.fixture
def test_db() -> Generator[SqliteDatabase, None, None]:
    """Provide an isolated in-memory SQLite database for unit tests."""
    db = SqliteDatabase(":memory:", thread_safe=False, check_same_thread=False)
    with db.bind_ctx(MODELS):
        db.create_tables(MODELS)
        yield db
        db.drop_tables(MODELS)
        db.close()


@pytest.fixture
def mock_youtube(mocker: MockerFixture) -> MagicMock:
    """Provide a mocked YouTube client for fast, deterministic, offline tests."""
    mock = MagicMock()

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
    player = MagicMock()
    state: MockPlayerState = {
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

    def _seek(position: float) -> None:
        state["position"] = max(0.0, float(position))

    # Explicit attribute assignment so isinstance(..., AudioPlayerProtocol) works
    # (getattr_static used by runtime_checkable cannot see MagicMock children).
    player.play = mocker.MagicMock(side_effect=_play)
    player.pause = mocker.MagicMock(side_effect=_pause)
    player.stop = mocker.MagicMock(side_effect=_stop)
    player.is_playing = mocker.MagicMock(side_effect=_is_playing)
    player.set_volume = mocker.MagicMock(side_effect=_set_volume)
    player.get_volume = mocker.MagicMock(side_effect=_get_volume)
    player.get_position = mocker.MagicMock(return_value=0.0)
    player.seek = mocker.MagicMock(side_effect=_seek)
    player.has_ended = mocker.MagicMock(return_value=False)
    player.has_failed = mocker.MagicMock(return_value=False)
    player.engine_state = mocker.MagicMock(return_value="Stopped")
    player.state = state

    return player


def make_test_app(
    *,
    search_service: SearchService | MagicMock | None = None,
    playback_service: PlaybackService | MagicMock | None = None,
    account_service: AccountService | MagicMock | None = None,
    playlist_service: PlaylistService | MagicMock | None = None,
    settings_service: SettingsService | MagicMock | None = None,
    mock_youtube: MagicMock | None = None,
    mock_player: MagicMock | None = None,
    show_welcome: bool | None = False,
) -> YTMusicApp:
    if search_service is None:
        if mock_youtube is not None:
            search_service = SearchService(mock_youtube)
        else:
            search_service = MagicMock()
            search_service.search = MagicMock(return_value=[])
            search_service.suggest = MagicMock(return_value=[])
    if playback_service is None:
        if mock_youtube is not None and mock_player is not None:
            playback_service = PlaybackService(mock_player, mock_youtube, AppState())
        else:
            playback_service = MagicMock()
            playback_service.sync_playback = MagicMock()
    if account_service is None:
        account_service = MagicMock()
        account_service.get_startup = MagicMock(return_value=default_startup_settings())
    if playlist_service is None:
        playlist_service = MagicMock()
    if settings_service is None:
        settings_service = MagicMock()
    return YTMusicApp(
        search_service=cast("SearchService", search_service),
        playback_service=cast("PlaybackService", playback_service),
        account_service=cast("AccountService", account_service),
        playlist_service=cast("PlaylistService", playlist_service),
        settings_service=cast("SettingsService", settings_service),
        show_welcome=show_welcome,
    )
