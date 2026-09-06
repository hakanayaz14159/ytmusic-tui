"""Queue playback regressions using an isolated state and silent player."""

from unittest.mock import MagicMock

import pytest

from ytmusic_cli.exceptions import PlaybackError
from ytmusic_cli.music.services import PlaybackService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackStatus, Song


@pytest.fixture
def songs() -> list[Song]:
    return [
        Song(video_id="one", title="First", artist="A", album=None, duration=60),
        Song(video_id="two", title="Second", artist="B", album=None, duration=90),
    ]


@pytest.mark.parametrize("paused", [False, True])
def test_next_after_final_song_stops_audio(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
    paused: bool,
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    song = service.set_queue(songs, 1)
    service.start_stream(song, service.resolve_stream(song))
    if paused:
        service.toggle()

    assert service.advance_to_next() is None

    mock_player.stop.assert_called_once()
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert state.current_song.get() == song


def test_duplicate_song_keeps_selected_queue_occurrence(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.set_queue([songs[0], songs[0], songs[1]], 0)
    service.start_stream(songs[0], service.resolve_stream(songs[0]))

    duplicate = service.advance_to_next()
    assert duplicate is not None
    service.start_stream(duplicate, service.resolve_stream(duplicate))

    assert state.queue_index.get() == 1
    assert service.advance_to_next() == songs[1]


@pytest.mark.parametrize("paused", [False, True])
def test_removing_final_current_song_stops_audio(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
    paused: bool,
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.start_stream(songs[0], service.resolve_stream(songs[0]))
    if paused:
        service.toggle()

    assert service.remove_from_queue(0) is None

    mock_player.stop.assert_called_once()
    assert state.queue.get() == []
    assert state.queue_index.get() == -1
    assert state.current_song.get() is None
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED


def test_removing_current_song_stops_before_resolving_replacement(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    song = service.set_queue(songs)
    service.start_stream(song, service.resolve_stream(song))
    mock_youtube.get_stream.reset_mock()

    assert service.remove_from_queue(0) == songs[1]

    mock_player.stop.assert_called_once()
    mock_youtube.get_stream.assert_not_called()
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED


def test_removing_current_paused_song_does_not_resume_removed_track(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    song = service.set_queue(songs)
    service.start_stream(song, service.resolve_stream(song))
    service.toggle()

    assert service.remove_from_queue(0) is None
    service.toggle()

    assert state.current_song.get() is None
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    mock_player.pause.assert_called_once()


def test_removing_queued_song_preserves_unrelated_current_song(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.set_queue(songs)
    other = Song(video_id="other", title="Other", artist="C", album=None, duration=120)
    service.start_stream(other, service.resolve_stream(other))

    assert service.remove_from_queue(0) is None

    mock_player.stop.assert_not_called()
    assert state.current_song.get() == other
    assert state.playback_state.get()["status"] == PlaybackStatus.PLAYING


def test_failed_play_does_not_select_a_new_queue_entry(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.set_queue(songs)
    mock_player.play.side_effect = PlaybackError("Audio device unavailable")

    with pytest.raises(PlaybackError):
        service.start_stream(songs[1], service.resolve_stream(songs[1]))

    assert state.queue_index.get() == 0
    assert state.current_song.get() is None
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED


def test_preparing_stream_controls_engine_without_publishing_state(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    stream = service.resolve_stream(songs[0])

    service.prepare_stream(stream)

    mock_player.play.assert_called_once_with(stream)
    mock_player.set_volume.assert_called_once_with(80)
    assert state.queue.get() == []
    assert state.current_song.get() is None
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED

    service.commit_stream(songs[0])

    assert state.current_song.get() == songs[0]
    assert state.playback_state.get()["status"] == PlaybackStatus.PLAYING
    assert state.queue.get() == [songs[0]]
    mock_player.play.assert_called_once()


def test_discard_prepared_stream_stops_engine_without_publishing_state(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.prepare_stream(service.resolve_stream(songs[0]))
    original = state.playback_state.get()

    service.discard_stream()

    mock_player.stop.assert_called_once()
    assert state.playback_state.get() == original
    assert state.current_song.get() is None


def test_final_song_ending_releases_engine_resources(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.start_stream(songs[0], service.resolve_stream(songs[0]))
    service.sync_playback()
    mock_player.has_ended.return_value = True

    service.sync_playback()
    service.sync_playback()

    mock_player.stop.assert_called_once()
    assert state.current_song.get() == songs[0]
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED


@pytest.mark.parametrize("operation", ["play", "set_volume"])
@pytest.mark.parametrize("stop_fails", [False, True])
def test_failed_preparation_stops_engine_and_preserves_original_error(
    mock_player: MagicMock,
    mock_youtube: MagicMock,
    songs: list[Song],
    operation: str,
    stop_fails: bool,
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    failure = PlaybackError("Audio preparation failed")
    getattr(mock_player, operation).side_effect = failure
    if stop_fails:
        mock_player.stop.side_effect = PlaybackError("Cleanup failed")

    with pytest.raises(PlaybackError) as exc_info:
        service.prepare_stream(service.resolve_stream(songs[0]))

    assert exc_info.value is failure
    mock_player.stop.assert_called_once()
    assert state.current_song.get() is None
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
