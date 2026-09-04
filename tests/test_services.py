"""Tests for SearchService and PlaybackService."""

from unittest.mock import MagicMock

import pytest

from ytmusic_cli.exceptions import (
    PlaybackError,
    StreamExtractionError,
    ValidationError,
)
from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import AudioStream, PlaybackStatus, Song


@pytest.fixture
def sample_song() -> Song:
    return {
        "id": 101,
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 240,
        "url": "https://www.youtube.com/watch?v=synth101",
    }


@pytest.fixture
def app_state() -> AppState:
    state = AppState()
    state.reset()
    return state


def test_search_service_delegates_to_source(mock_youtube: MagicMock) -> None:
    service = SearchService(mock_youtube)
    results = service.search("lofi", max_results=5)
    mock_youtube.search.assert_called_once_with("lofi", max_results=5)
    assert len(results) == 2


def test_search_service_blank_query_raises_validation_error(
    mock_youtube: MagicMock,
) -> None:
    service = SearchService(mock_youtube)
    with pytest.raises(ValidationError, match="empty"):
        service.search("   ")
    mock_youtube.search.assert_not_called()


def test_playback_service_play_song_updates_state(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    expected_stream: AudioStream = {
        "url": "https://stream.example.com/audio.m4a",
        "http_headers": {
            "User-Agent": "test-agent",
            "Referer": "https://www.youtube.com/",
        },
    }
    mock_youtube.get_stream.return_value = expected_stream

    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)

    mock_youtube.get_stream.assert_called_once_with(sample_song["url"])
    mock_player.play.assert_called_once_with(expected_stream)
    mock_player.set_volume.assert_called_with(80)
    assert app_state.current_song.get() == sample_song
    playback = app_state.playback_state.get()
    assert playback["status"] == PlaybackStatus.PLAYING
    assert playback["duration"] == sample_song["duration"]


def test_playback_service_toggle_playing_to_paused(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    service.toggle()

    mock_player.pause.assert_called()
    assert app_state.playback_state.get()["status"] == PlaybackStatus.PAUSED


def test_playback_service_toggle_paused_to_playing(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    service.toggle()
    assert app_state.playback_state.get()["status"] == PlaybackStatus.PAUSED
    service.toggle()

    assert app_state.playback_state.get()["status"] == PlaybackStatus.PLAYING
    assert mock_player.pause.call_count == 2


def test_playback_service_stop(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    service.stop()

    mock_player.stop.assert_called()
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert app_state.current_song.get() is None


def test_playback_service_volume_up_and_down(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    assert app_state.playback_state.get()["volume"] == 80

    service.volume_up()
    assert app_state.playback_state.get()["volume"] == 85
    mock_player.set_volume.assert_called_with(85)

    service.volume_down()
    assert app_state.playback_state.get()["volume"] == 80
    mock_player.set_volume.assert_called_with(80)


def test_playback_service_volume_clamped_0_100(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    for _ in range(30):
        service.volume_up()
    assert app_state.playback_state.get()["volume"] == 100

    for _ in range(30):
        service.volume_down()
    assert app_state.playback_state.get()["volume"] == 0


def test_playback_service_source_failure_leaves_state_stopped(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    mock_youtube.get_stream.side_effect = StreamExtractionError("boom")
    service = PlaybackService(mock_player, mock_youtube, app_state)

    with pytest.raises(StreamExtractionError):
        service.play_song(sample_song)

    mock_player.play.assert_not_called()
    assert app_state.current_song.get() is None
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED


def test_playback_service_player_failure_leaves_state_stopped(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    mock_player.play.side_effect = PlaybackError("VLC failed")
    service = PlaybackService(mock_player, mock_youtube, app_state)

    with pytest.raises(PlaybackError):
        service.play_song(sample_song)

    assert app_state.current_song.get() is None
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
