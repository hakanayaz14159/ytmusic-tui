"""Tests for SearchService and PlaybackService."""

from unittest.mock import MagicMock

import pytest

from ytmusic_cli.consts import DEFAULT_SUGGEST_LIMIT, PLAYBACK_STALL_TICKS
from ytmusic_cli.exceptions import (
    PlaybackError,
    StreamExtractionError,
    ValidationError,
)
from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import (
    AudioStream,
    PlaybackStatus,
    PlaybackTickAction,
    Song,
)


@pytest.fixture
def sample_song() -> Song:
    return {
        "video_id": "synth101",
        "title": "Ambient Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 240,
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


def test_search_service_suggest_delegates_to_source(mock_youtube: MagicMock) -> None:
    mock_youtube.suggest.return_value = ["beatles", "beatles yesterday"]
    service = SearchService(mock_youtube)

    results = service.suggest("beat", max_results=5)

    mock_youtube.suggest.assert_called_once_with("beat", max_results=5)
    assert results == ["beatles", "beatles yesterday"]


def test_search_service_suggest_strips_query_before_delegate(
    mock_youtube: MagicMock,
) -> None:
    mock_youtube.suggest.return_value = ["lofi hip hop"]
    service = SearchService(mock_youtube)

    results = service.suggest("  lofi  ")

    mock_youtube.suggest.assert_called_once_with(
        "lofi", max_results=DEFAULT_SUGGEST_LIMIT
    )
    assert results == ["lofi hip hop"]


@pytest.mark.parametrize("query", ["", " ", "a", " a "])
def test_search_service_suggest_short_query_skips_adapter(
    mock_youtube: MagicMock,
    query: str,
) -> None:
    service = SearchService(mock_youtube)

    results = service.suggest(query)

    assert results == []
    mock_youtube.suggest.assert_not_called()


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

    mock_youtube.get_stream.assert_called_once_with(sample_song["video_id"])
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


def test_sync_playback_reapplies_volume_when_engine_volume_mismatches(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    mock_player.set_volume.reset_mock()
    mock_player.has_ended.return_value = False
    mock_player.has_failed.return_value = False
    mock_player.is_playing.side_effect = None
    mock_player.is_playing.return_value = True
    mock_player.get_volume.side_effect = None
    mock_player.get_volume.return_value = 0
    mock_player.get_position.return_value = 0.0

    service.sync_playback()

    mock_player.set_volume.assert_called_with(80)


def test_sync_playback_updates_position_while_playing(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    mock_player.has_ended.return_value = False
    mock_player.get_position.return_value = 12.4

    service.sync_playback()

    assert app_state.playback_state.get()["position"] == 12.4
    assert app_state.playback_state.get()["status"] == PlaybackStatus.PLAYING


def test_sync_playback_skips_set_when_whole_second_unchanged(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    mock_player.has_ended.return_value = False
    mock_player.get_position.return_value = 12.4
    service.sync_playback()

    received: list[object] = []
    app_state.playback_state.subscribe(received.append)
    mock_player.get_position.return_value = 12.8
    service.sync_playback()

    assert received == []
    assert app_state.playback_state.get()["position"] == 12.4


def test_sync_playback_ended_before_playing_is_failure(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    mock_player.has_ended.return_value = True
    mock_player.has_failed.return_value = False
    mock_player.is_playing.side_effect = None
    mock_player.is_playing.return_value = False

    tick = service.sync_playback()

    assert tick.action == PlaybackTickAction.FAILED
    assert tick.message is not None
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert app_state.current_song.get() == sample_song
    mock_youtube.get_stream.assert_called_once()


def test_sync_playback_ended_after_playing_stops_and_keeps_song(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    mock_player.has_ended.return_value = False
    mock_player.has_failed.return_value = False
    mock_player.is_playing.side_effect = None
    mock_player.is_playing.return_value = True
    mock_player.get_position.return_value = 12.4
    service.sync_playback()

    mock_player.has_ended.return_value = True
    mock_player.is_playing.return_value = False
    tick = service.sync_playback()

    assert tick.action == PlaybackTickAction.IDLE
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert app_state.current_song.get() == sample_song
    mock_youtube.get_stream.assert_called_once()


def test_sync_playback_ignores_position_when_not_playing(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_song(sample_song)
    service.toggle()
    mock_player.has_ended.return_value = False
    mock_player.get_position.return_value = 99.0

    service.sync_playback()

    assert app_state.playback_state.get()["status"] == PlaybackStatus.PAUSED
    assert app_state.playback_state.get()["position"] == 0.0


def test_toggle_stopped_with_current_song_replays(
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
    current = app_state.playback_state.get()
    app_state.playback_state.set({**current, "status": PlaybackStatus.STOPPED})
    mock_youtube.get_stream.reset_mock()
    mock_player.play.reset_mock()

    service.toggle()

    mock_youtube.get_stream.assert_called_once_with(sample_song["video_id"])
    mock_player.play.assert_called_once_with(expected_stream)
    assert app_state.playback_state.get()["status"] == PlaybackStatus.PLAYING
    assert app_state.current_song.get() == sample_song


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


def test_resolve_stream_does_not_start_player(
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

    stream = service.resolve_stream(sample_song)

    assert stream == expected_stream
    mock_youtube.get_stream.assert_called_once_with(sample_song["video_id"])
    mock_player.play.assert_not_called()
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert app_state.queue.get() == [sample_song]


def test_start_stream_does_not_resolve_source(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    stream: AudioStream = {
        "url": "https://stream.example.com/audio.m4a",
        "http_headers": {
            "User-Agent": "test-agent",
            "Referer": "https://www.youtube.com/",
        },
    }
    service = PlaybackService(mock_player, mock_youtube, app_state)

    service.start_stream(sample_song, stream)

    mock_youtube.get_stream.assert_not_called()
    mock_player.play.assert_called_once_with(stream)
    mock_player.set_volume.assert_called_with(80)
    assert app_state.current_song.get() == sample_song
    assert app_state.playback_state.get()["status"] == PlaybackStatus.PLAYING


def test_sync_playback_engine_error_stops_without_advancing_queue(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    next_song: Song = {
        "video_id": "synth102",
        "title": "Next Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 180,
    }
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_queue([sample_song, next_song], 0)
    mock_youtube.get_stream.reset_mock()
    mock_player.has_failed.return_value = True
    mock_player.has_ended.return_value = False

    tick = service.sync_playback()

    assert tick.action == PlaybackTickAction.FAILED
    assert tick.message is not None
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert app_state.queue_index.get() == 0
    assert app_state.current_song.get() == sample_song
    mock_youtube.get_stream.assert_not_called()


def test_sync_playback_stall_stops_without_advancing_queue(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    app_state: AppState,
    sample_song: Song,
) -> None:
    next_song: Song = {
        "video_id": "synth102",
        "title": "Next Flow",
        "artist": "SynthArtist",
        "album": "Deep Space",
        "duration": 180,
    }
    service = PlaybackService(mock_player, mock_youtube, app_state)
    service.play_queue([sample_song, next_song], 0)
    mock_youtube.get_stream.reset_mock()
    mock_player.is_playing.side_effect = None
    mock_player.is_playing.return_value = False
    mock_player.has_ended.return_value = False
    mock_player.has_failed.return_value = False

    for _ in range(PLAYBACK_STALL_TICKS - 1):
        tick = service.sync_playback()
        assert tick.action == PlaybackTickAction.IDLE
        assert app_state.playback_state.get()["status"] == PlaybackStatus.PLAYING

    tick = service.sync_playback()

    assert tick.action == PlaybackTickAction.FAILED
    assert tick.message is not None
    assert app_state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert app_state.queue_index.get() == 0
    mock_youtube.get_stream.assert_not_called()
