"""Queue behavior for PlaybackService and Queue mode."""

import threading
from typing import Literal
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from pytest_mock import MockerFixture
from textual.pilot import Pilot
from textual.widgets import Input, Label

from tests.conftest import make_test_app
from ytmusic_cli.db.repositories import (
    PlaylistRepository,
    SongRepository,
    UserRepository,
)
from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
)
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import (
    PlaybackStatus,
    PlaybackTickAction,
    Playlist,
    Song,
    User,
)
from ytmusic_cli.tui.modals.add_to_playlist import AddToPlaylistModal
from ytmusic_cli.tui.modals.confirm import ConfirmModal
from ytmusic_cli.tui.modals.prompt import PromptModal
from ytmusic_cli.tui.modes.queue import QueueMode
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.queue_list import QueueList
from ytmusic_cli.tui.widgets.song_table import VimListView


def _make_app(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> tuple[YTMusicApp, AppState]:
    state = AppState()
    app = make_test_app(
        search_service=SearchService(mock_youtube),
        playback_service=PlaybackService(mock_player, mock_youtube, state),
    )
    return app, state


def _queue_list(app: YTMusicApp) -> VimListView:
    return app.query_one("#queue_table", QueueList).query_one(VimListView)


async def _seed_queue_and_open(
    pilot: Pilot[None],
    app: YTMusicApp,
    songs: list[Song],
    *,
    queue_index: int = 0,
    via: Literal["2", "tab"] = "2",
) -> None:
    state = AppState()
    state.queue.set(songs)
    state.queue_index.set(queue_index)
    await pilot.pause()
    if via == "tab":
        await pilot.press("tab")
    else:
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("2")
    await pilot.pause()
    assert app.query_one(AppShell).current_mode == "queue"


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
    service.start_stream(
        sample_songs[0], mock_youtube.get_stream(sample_songs[0]["video_id"])
    )
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
    stream = service.resolve_stream(extra)
    service.start_stream(extra, stream)
    assert state.queue.get() == sample_songs
    assert state.current_song.get() == extra


def test_append_to_queue_plays_when_stopped(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    service.enqueue(sample_songs[0])
    assert state.queue.get()[-1] == sample_songs[0]
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    mock_player.play.assert_not_called()


def test_play_next_advances_and_end_stops(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    first = service.set_queue(sample_songs, 0)
    service.start_stream(first, service.resolve_stream(first))
    nxt = service.advance_to_next()
    if nxt is not None:
        service.start_stream(nxt, service.resolve_stream(nxt))
    assert state.queue_index.get() == 1
    assert state.current_song.get() == sample_songs[1]
    nxt = service.advance_to_next()
    if nxt is not None:
        service.start_stream(nxt, service.resolve_stream(nxt))
    assert state.playback_state.get()["status"] == PlaybackStatus.STOPPED
    assert state.current_song.get() == sample_songs[1]


def test_sync_playback_signals_ended_without_starting_next(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    first = service.set_queue(sample_songs, 0)
    service.start_stream(first, service.resolve_stream(first))
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


def test_load_queue_aligns_index_to_current_song(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    state.current_song.set(sample_songs[1])

    song = service.load_queue(sample_songs)

    assert song == sample_songs[1]
    assert state.queue.get() == sample_songs
    assert state.queue_index.get() == 1
    mock_player.play.assert_not_called()


def test_load_queue_starts_at_zero_when_current_song_absent(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    extra: Song = {
        "video_id": "other",
        "title": "Other",
        "artist": "C",
        "album": None,
        "duration": 90,
    }
    state.current_song.set(extra)

    song = service.load_queue(sample_songs)

    assert song == sample_songs[0]
    assert state.queue_index.get() == 0
    mock_player.play.assert_not_called()


def test_play_previous_moves_back(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    state = AppState()
    service = PlaybackService(mock_player, mock_youtube, state)
    first = service.set_queue(sample_songs, 1)
    service.start_stream(first, service.resolve_stream(first))
    prev = service.advance_to_previous()
    assert prev is not None
    service.start_stream(prev, service.resolve_stream(prev))
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

    app = make_test_app(
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


@pytest.mark.asyncio
async def test_tab_from_search_input_focuses_queue_list(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, _state = _make_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#search_input", Input).has_focus is True
        await _seed_queue_and_open(pilot, app, sample_songs, via="tab")

        assert app.query_one("#search_input", Input).has_focus is False
        assert _queue_list(app).has_focus is True


@pytest.mark.asyncio
async def test_digit_two_focuses_queue_list_at_queue_index(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, _state = _make_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs, queue_index=1)

        queue_list = _queue_list(app)
        assert queue_list.has_focus is True
        assert queue_list.index == 1
        assert (
            app.query_one("#queue_table", QueueList).get_selected_song()
            == (sample_songs[1])
        )


@pytest.mark.asyncio
async def test_switching_to_empty_queue_blurs_search_input(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, _state = _make_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#search_input", Input).has_focus is True
        await pilot.press("tab")
        await pilot.pause()

        assert app.query_one(AppShell).current_mode == "queue"
        assert app.query_one("#search_input", Input).has_focus is False
        assert app.query_one(QueueMode).has_focus is True


@pytest.mark.asyncio
async def test_queue_j_k_moves_highlight(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, _state = _make_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs, queue_index=0)

        queue_list = _queue_list(app)
        assert queue_list.index == 0
        await pilot.press("j")
        await pilot.pause()
        assert queue_list.index == 1
        await pilot.press("k")
        await pilot.pause()
        assert queue_list.index == 0


@pytest.mark.asyncio
async def test_queue_enter_plays_highlighted_song(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
    mocker: MockerFixture,
) -> None:
    app, _state = _make_app(mock_youtube, mock_player)
    play_song = mocker.patch.object(app, "play_song")

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs, queue_index=1)

        await pilot.press("enter")
        await pilot.pause()

        play_song.assert_called_once_with(sample_songs[1], queue_index=1)


@pytest.mark.asyncio
async def test_side_queue_enter_plays_highlighted_song(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
    mocker: MockerFixture,
) -> None:
    app, _state = _make_app(mock_youtube, mock_player)
    play_song = mocker.patch.object(app, "play_song")

    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs, queue_index=1)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()
        pane = app.query_one("#queue_pane")
        assert pane.display is True
        side = app.query_one("#side_queue", QueueList)
        side.activate_list()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        play_song.assert_called_once_with(sample_songs[1], queue_index=1)


@pytest.mark.asyncio
async def test_side_queue_d_removes_highlighted(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, state = _make_app(mock_youtube, mock_player)

    async with app.run_test(size=(120, 24)) as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs, queue_index=1)
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()
        side = app.query_one("#side_queue", QueueList)
        side.activate_list()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.pause()

        assert state.queue.get() == [sample_songs[0]]


@pytest.mark.asyncio
async def test_queue_d_removes_highlighted_and_keeps_focus(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, state = _make_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs, queue_index=1)

        await pilot.press("d")
        await pilot.pause()
        await pilot.pause()

        assert state.queue.get() == [sample_songs[0]]
        assert _queue_list(app).has_focus is True
        assert (
            app.query_one("#queue_table", QueueList).get_selected_song()
            == (sample_songs[0])
        )


def _make_playlist_app(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> tuple[YTMusicApp, PlaylistService, AppState, User]:
    state = AppState()
    accounts = AccountService(UserRepository(), state)
    user = accounts.ensure_default_user()
    accounts.select_user(user["id"])
    playlists = PlaylistService(PlaylistRepository(SongRepository()), AppState())
    app = make_test_app(
        search_service=SearchService(mock_youtube),
        playback_service=PlaybackService(mock_player, mock_youtube, state),
        account_service=accounts,
        playlist_service=playlists,
    )
    return app, playlists, state, user


@pytest.mark.asyncio
async def test_queue_o_loads_playlist_without_playing(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, playlists, state, user = _make_playlist_app(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "Late Night", sample_songs)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, AddToPlaylistModal)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        working = state.current_playlist.get()
        assert working is not None
        assert working["name"] == "Late Night"
        assert [song["video_id"] for song in state.queue.get()] == ["one", "two"]
        mock_player.play.assert_not_called()
        working_label = app.query_one("#queue_working", Label)
        assert "Late Night" in str(working_label.content)


@pytest.mark.asyncio
async def test_queue_o_lists_playlists_off_ui_thread(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
    mocker: MockerFixture,
) -> None:
    app, playlists, _state, user = _make_playlist_app(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "Late Night", sample_songs)
    ui_thread = threading.get_ident()
    list_ids: list[int] = []
    original_list = playlists.list_playlists

    def _list(user_id: int) -> list[Playlist]:
        list_ids.append(threading.get_ident())
        return original_list(user_id)

    mocker.patch.object(playlists, "list_playlists", side_effect=_list)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, AddToPlaylistModal)
        assert list_ids
        assert list_ids[0] != ui_thread


@pytest.mark.asyncio
async def test_queue_n_saves_queue_as_new_playlist(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, playlists, state, user = _make_playlist_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs)
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, PromptModal)
        app.screen.query_one("#prompt_input", Input).value = "From Queue"
        await pilot.press("enter")
        await pilot.pause()

        listed = playlists.list_playlists(user["id"])
        assert len(listed) == 1
        assert listed[0]["name"] == "From Queue"
        assert [song["video_id"] for song in listed[0]["songs"]] == ["one", "two"]
        working = state.current_playlist.get()
        assert working is not None
        assert working["name"] == "From Queue"


@pytest.mark.asyncio
async def test_queue_n_on_empty_queue_does_not_create(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, _state, user = _make_playlist_app(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        assert not isinstance(app.screen, PromptModal)
        assert playlists.list_playlists(user["id"]) == []


@pytest.mark.asyncio
async def test_queue_w_overwrites_working_playlist(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, playlists, state, user = _make_playlist_app(mock_youtube, mock_player)
    created = playlists.create_playlist_from_songs(
        user["id"],
        "Late Night",
        [sample_songs[0]],
    )
    state.current_playlist.set(created)

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs)
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("y")
        await pilot.pause()

        loaded = playlists.get_playlist(created["id"])
        assert [song["video_id"] for song in loaded["songs"]] == ["one", "two"]


@pytest.mark.asyncio
async def test_queue_w_without_working_playlist_does_not_write(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    sample_songs: list[Song],
) -> None:
    app, playlists, _state, user = _make_playlist_app(mock_youtube, mock_player)
    existing = playlists.create_playlist_from_songs(
        user["id"],
        "Keep",
        [sample_songs[0]],
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await _seed_queue_and_open(pilot, app, sample_songs)
        await pilot.press("w")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmModal)
        loaded = playlists.get_playlist(existing["id"])
        assert [song["video_id"] for song in loaded["songs"]] == ["one"]
