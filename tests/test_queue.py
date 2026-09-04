"""Queue behavior for PlaybackService and Queue mode."""

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input

from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.services import PlaybackService, SearchService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import PlaybackStatus, PlaybackTickAction, Song
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.queue_list import QueueList


@pytest.fixture
def sample_songs() -> list[Song]:
    return [
        {
            "video_id": "one",
            "title": "First",
            "artist": "A",
            "album": None,
            "duration": 60,
        },
        {
            "video_id": "two",
            "title": "Second",
            "artist": "B",
            "album": None,
            "duration": 80,
        },
    ]


def test_play_song_seeds_empty_queue(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.play_song(sample_songs[0])
    assert state.queue.get() == [sample_songs[0]]
    assert state.queue_index.get() == 0


def test_play_now_does_not_replace_existing_queue(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    extra: Song = {
        "video_id": "three",
        "title": "Third",
        "artist": "C",
        "album": None,
        "duration": 90,
    }
    state.queue.set(sample_songs)
    state.queue_index.set(0)
    service.play_song(extra)
    assert state.queue.get() == sample_songs
    assert state.current_song.get() == extra


def test_append_to_queue_plays_when_stopped(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.append_to_queue(sample_songs[0])
    assert state.queue.get()[-1] == sample_songs[0]
    assert state.playback_state.get()["status"] == PlaybackStatus.PLAYING


def test_play_next_advances_and_end_stops(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.play_queue(sample_songs, 0)
    service.play_next()
    assert state.queue_index.get() == 1
    assert state.current_song.get() == sample_songs[1]
    service.play_next()
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert state.current_song.get() == sample_songs[1]


def test_sync_playback_signals_ended_without_starting_next(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.play_queue(sample_songs, 0)
    mock_youtube.get_stream.reset_mock()
    mock_player.has_ended.return_value = False
    mock_player.has_failed.return_value = False
    mock_player.is_playing.side_effect = None
    mock_player.is_playing.return_value = True
    mock_player.get_position.return_value = 1.0
    service.sync_playback()
    mock_player.has_ended.return_value = True

    tick = service.sync_playback()

    assert tick.action == PlaybackTickAction.ENDED
    assert state.queue_index.get() == 0
    assert state.current_song.get() == sample_songs[0]
    mock_youtube.get_stream.assert_not_called()


def test_play_previous_moves_back(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.play_queue(sample_songs, 1)
    service.play_previous()
    assert state.queue_index.get() == 0
    assert state.current_song.get() == sample_songs[0]


@pytest.mark.asyncio
async def test_search_a_appends_to_queue_and_queue_mode_lists_it(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    mock_youtube.search.return_value = sample_songs
    state = AppState()

    app = YTMusicApp(
        search_service=SearchService(mock_youtube),
        playback_service=PlaybackService(mock_player, mock_youtube, state),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "x"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.pause()

        assert len(state.queue.get()) >= 1
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "queue"
        queue_table = app.query_one("#queue_table", QueueList)
        assert len(queue_table._songs) >= 1
