"""Playlist persistence and PlaylistService tests."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from pytest_mock import MockerFixture
from textual.widgets import Input

from tests.conftest import make_test_app
from ytmusic_tui.db.repositories import (
    AppConfigRepository,
    PlaylistRepository,
    SongRepository,
    UserRepository,
)
from ytmusic_tui.exceptions import DatabaseError, ValidationError
from ytmusic_tui.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
)
from ytmusic_tui.music.state import AppState
from ytmusic_tui.music.types import Playlist, Song, User
from ytmusic_tui.tui.app import YTMusicApp
from ytmusic_tui.tui.modals.add_to_playlist import AddToPlaylistModal
from ytmusic_tui.tui.modals.confirm import ConfirmModal
from ytmusic_tui.tui.modes.playlists import PlaylistsMode
from ytmusic_tui.tui.shell import AppShell
from ytmusic_tui.tui.widgets.select_list import SelectList
from ytmusic_tui.tui.widgets.song_table import SongRow, SongTable, VimListView

SAMPLE_SONG: Song = {
    "video_id": "vid1",
    "title": "Track",
    "artist": "Artist",
    "album": "Album",
    "duration": 120,
}

SONG_A: Song = {
    "video_id": "a",
    "title": "Alpha",
    "artist": "Artist",
    "album": None,
    "duration": 60,
}

SONG_B: Song = {
    "video_id": "b",
    "title": "Beta",
    "artist": "Artist",
    "album": None,
    "duration": 70,
}

SONG_C: Song = {
    "video_id": "c",
    "title": "Gamma",
    "artist": "Artist",
    "album": None,
    "duration": 80,
}


@pytest.fixture
def playlist_setup(test_db: SqliteDatabase) -> tuple[AccountService, PlaylistService]:
    accounts = AccountService(UserRepository(), AppState(), AppConfigRepository())
    playlists = PlaylistService(PlaylistRepository(SongRepository()), AppState())
    return accounts, playlists


def test_create_and_list_playlists_for_user(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    created = playlists.create_playlist(user["id"], "Late Night")
    listed = playlists.list_playlists(user["id"])
    assert created["name"] == "Late Night"
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_add_song_persists_by_video_id(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist(user["id"], "Favs")
    playlists.add_song(playlist["id"], SAMPLE_SONG)
    loaded = playlists.get_playlist(playlist["id"])
    assert loaded["songs"][0]["video_id"] == "vid1"
    assert loaded["songs"][0]["album"] == "Album"


def test_add_duplicate_song_raises(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist(user["id"], "Favs")
    playlists.add_song(playlist["id"], SAMPLE_SONG)
    with pytest.raises(ValidationError, match="already"):
        playlists.add_song(playlist["id"], SAMPLE_SONG)


def test_rejected_duplicate_preserves_saved_song_metadata(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist_from_songs(user["id"], "Favs", [SONG_A])

    with pytest.raises(ValidationError, match="already"):
        playlists.add_song(playlist["id"], {**SONG_A, "title": "Changed"})

    assert playlists.get_playlist(playlist["id"])["songs"] == [SONG_A]


def test_deleted_playlist_does_not_leave_song_memberships(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    deleted = playlists.create_playlist_from_songs(user["id"], "Old", [SONG_A])

    playlists.delete_playlist(deleted["id"])
    created = playlists.create_playlist(user["id"], "New")

    assert created["songs"] == []
    assert SongRepository().get_by_video_id(SONG_A["video_id"]) == SONG_A


def test_replace_songs_rolls_back_on_persistence_failure(
    test_db: SqliteDatabase,
    mocker: MockerFixture,
) -> None:
    user = UserRepository().create_user("hzf")
    songs = SongRepository()
    repo = PlaylistRepository(songs)
    playlist = repo.create(user["id"], "Favs")
    repo.add_song(playlist["id"], SONG_A)
    repo.add_song(playlist["id"], SONG_B)
    upsert = songs.upsert

    def fail_second_song(song: Song) -> Song:
        if song["video_id"] == SONG_C["video_id"]:
            raise DatabaseError("Cannot persist song")
        return upsert(song)

    mocker.patch.object(songs, "upsert", side_effect=fail_second_song)

    with pytest.raises(DatabaseError, match="Cannot persist"):
        repo.replace_songs(playlist["id"], [{**SONG_B, "title": "Changed"}, SONG_C])

    assert repo.get(playlist["id"]) == {**playlist, "songs": [SONG_A, SONG_B]}


def test_working_playlist_tracks_follow_persisted_edits(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist_from_songs(user["id"], "Favs", [SONG_A])
    playlists.adopt_working_playlist(playlist)

    playlists.add_song(playlist["id"], SONG_B)
    assert AppState().current_playlist.get() == {**playlist, "songs": [SONG_A, SONG_B]}

    playlists.remove_song(playlist["id"], SONG_A["video_id"])
    assert AppState().current_playlist.get() == {**playlist, "songs": [SONG_B]}

    playlists.replace_songs(playlist["id"], [SONG_C])
    assert AppState().current_playlist.get() == {**playlist, "songs": [SONG_C]}


def test_working_playlist_refresh_does_not_restore_previous_profile(
    playlist_setup: tuple[AccountService, PlaylistService],
    mocker: MockerFixture,
) -> None:
    accounts, playlists = playlist_setup
    first = accounts.create_user("first")
    second = accounts.create_user("second")
    accounts.select_user(first["id"])
    working = playlists.create_playlist_from_songs(first["id"], "Original", [SONG_A])
    playlists.adopt_working_playlist(working)
    get_playlist = playlists.get_playlist

    def load_after_profile_switch(playlist_id: int) -> Playlist:
        accounts.select_user(second["id"])
        return get_playlist(playlist_id)

    mocker.patch.object(
        playlists, "get_playlist", side_effect=load_after_profile_switch
    )
    playlists.add_song(working["id"], SONG_B)

    assert AppState().current_user.get() == second
    assert AppState().current_playlist.get() is None


def test_deleting_working_playlist_clears_selection(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist_from_songs(user["id"], "Favs", [SONG_A])
    playlists.adopt_working_playlist(playlist)

    playlists.delete_playlist(playlist["id"])

    assert AppState().current_playlist.get() is None


def test_remove_song_and_delete_playlist(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist(user["id"], "Favs")
    playlists.add_song(playlist["id"], SAMPLE_SONG)
    playlists.remove_song(playlist["id"], "vid1")
    assert playlists.get_playlist(playlist["id"])["songs"] == []
    playlists.delete_playlist(playlist["id"])
    assert playlists.list_playlists(user["id"]) == []


def test_replace_songs_overwrites_membership_and_order(
    test_db: SqliteDatabase,
) -> None:
    user = UserRepository().create_user("hzf")
    repo = PlaylistRepository(SongRepository())
    playlist = repo.create(user["id"], "Favs")
    repo.add_song(playlist["id"], SONG_A)
    repo.add_song(playlist["id"], SONG_B)
    repo.add_song(playlist["id"], SONG_C)

    replaced = repo.replace_songs(playlist["id"], [SONG_C, SONG_A, SONG_B])

    assert [song["video_id"] for song in replaced["songs"]] == ["c", "a", "b"]
    loaded = repo.get(playlist["id"])
    assert loaded is not None
    assert [song["video_id"] for song in loaded["songs"]] == ["c", "a", "b"]


def test_replace_songs_skips_duplicate_video_ids(
    test_db: SqliteDatabase,
) -> None:
    user = UserRepository().create_user("hzf")
    repo = PlaylistRepository(SongRepository())
    playlist = repo.create(user["id"], "Favs")

    replaced = repo.replace_songs(playlist["id"], [SONG_A, SONG_B, SONG_A])

    assert [song["video_id"] for song in replaced["songs"]] == ["a", "b"]


def test_replace_songs_missing_playlist_raises(
    test_db: SqliteDatabase,
) -> None:
    repo = PlaylistRepository(SongRepository())
    with pytest.raises(ValidationError, match="not found"):
        repo.replace_songs(999, [SONG_A])


def test_get_playlist_missing_returns_none(test_db: SqliteDatabase) -> None:
    assert PlaylistRepository(SongRepository()).get(999) is None


def test_get_by_video_id_miss_returns_none(test_db: SqliteDatabase) -> None:
    assert SongRepository().get_by_video_id("missing") is None


def test_create_playlist_from_songs_persists_name_and_order(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")

    created = playlists.create_playlist_from_songs(
        user["id"],
        "Late Night",
        [SONG_C, SONG_A, SONG_B],
    )

    assert created["name"] == "Late Night"
    assert [song["video_id"] for song in created["songs"]] == ["c", "a", "b"]
    loaded = playlists.get_playlist(created["id"])
    assert [song["video_id"] for song in loaded["songs"]] == ["c", "a", "b"]


def test_create_playlist_from_songs_dedupes_first_seen_order(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")

    created = playlists.create_playlist_from_songs(
        user["id"],
        "Mix",
        [SONG_A, SONG_B, SONG_A],
    )

    assert [song["video_id"] for song in created["songs"]] == ["a", "b"]


def test_create_playlist_from_songs_rejects_empty_list(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    with pytest.raises(ValidationError, match="empty"):
        playlists.create_playlist_from_songs(user["id"], "Empty", [])


def test_create_playlist_from_songs_rejects_empty_name(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    with pytest.raises(ValidationError, match="empty"):
        playlists.create_playlist_from_songs(user["id"], "  ", [SONG_A])


def test_service_replace_songs_overwrites_playlist(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    playlist = playlists.create_playlist_from_songs(
        user["id"], "Favs", [SONG_A, SONG_B]
    )

    updated = playlists.replace_songs(playlist["id"], [SONG_C, SONG_A])

    assert [song["video_id"] for song in updated["songs"]] == ["c", "a"]


def test_empty_playlist_name_rejected(
    playlist_setup: tuple[AccountService, PlaylistService],
) -> None:
    accounts, playlists = playlist_setup
    user = accounts.create_user("hzf")
    with pytest.raises(ValidationError, match="empty"):
        playlists.create_playlist(user["id"], "  ")


@pytest.mark.asyncio
async def test_playlists_mode_opens(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    accounts = AccountService(UserRepository(), state, AppConfigRepository())
    user = accounts.ensure_default_user()
    accounts.select_user(user["id"])
    playlists = PlaylistService(PlaylistRepository(SongRepository()), AppState())
    playlists.create_playlist(user["id"], "Study")

    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = make_test_app(
        search_service=MagicMock(),
        playback_service=playback,
        account_service=accounts,
        playlist_service=playlists,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "playlists"


def test_load_playlist_play_skips_duplicate_set_queue(
    test_db: SqliteDatabase,
    mocker: MockerFixture,
) -> None:
    state = AppState()
    accounts = AccountService(UserRepository(), state, AppConfigRepository())
    user = accounts.ensure_default_user()
    accounts.select_user(user["id"])
    playlists = PlaylistService(PlaylistRepository(SongRepository()), AppState())
    created = playlists.create_playlist_from_songs(user["id"], "Study", [SONG_A])
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = make_test_app(
        search_service=MagicMock(),
        playback_service=playback,
        account_service=accounts,
        playlist_service=playlists,
    )
    play_playlist = mocker.patch.object(app, "play_playlist")
    playlist = playlists.get_playlist(created["id"])

    app._on_playlist_loaded(playlist, True, 0)

    playback.set_queue.assert_not_called()
    play_playlist.assert_called_once()
    songs, start_index = play_playlist.call_args.args
    assert start_index == 0
    assert songs[0]["video_id"] == "a"


def test_loading_empty_playlist_does_not_replace_playback_queue(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    app.playback_service.load_queue([SONG_A])
    empty = playlists.create_playlist(user["id"], "Empty")
    notify = mocker.patch.object(app, "notify")

    app._on_playlist_loaded(empty, False, 0)

    assert state.queue.get() == [SONG_A]
    assert state.current_playlist.get() is None
    notify.assert_called_once()


def _app_with_playlists(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> tuple[YTMusicApp, PlaylistService, AppState, User]:
    state = AppState()
    accounts = AccountService(UserRepository(), state, AppConfigRepository())
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
async def test_playlists_enter_sets_working_playlist(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "Study", [SONG_A, SONG_B])

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        working = state.current_playlist.get()
        assert working is not None
        assert working["name"] == "Study"
        assert state.queue.get()[0]["video_id"] == "a"


@pytest.mark.asyncio
async def test_playlists_reload_preserves_selected_playlist(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "First", [SONG_A])
    second = playlists.create_playlist_from_songs(user["id"], "Second", [SONG_B])

    async with app.run_test() as pilot:
        app.query_one(AppShell).switch_mode("playlists")
        await app.workers.wait_for_complete()
        await pilot.pause()
        app.query_one("#playlist_list", SelectList).highlighted = 1
        await pilot.pause()

        app.query_one(PlaylistsMode).reload()
        await app.workers.wait_for_complete()
        await pilot.pause()

        mode = app.query_one(PlaylistsMode)
        assert mode._current_playlist() == second
        assert mode.query_one("#playlist_list", SelectList).highlighted == 1


@pytest.mark.asyncio
async def test_playlists_tracks_follow_current_song_without_reload(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "Study", [SONG_A, SONG_B])

    async with app.run_test() as pilot:
        app.query_one(AppShell).switch_mode("playlists")
        await app.workers.wait_for_complete()
        await pilot.pause()

        tracks = app.query_one("#playlist_tracks", SongTable)

        def playing_id() -> str | None:
            return tracks._playing_id

        assert playing_id() is None

        state.current_song.set(SONG_B)
        await pilot.pause()
        assert playing_id() == "b"

        state.current_song.set(None)
        await pilot.pause()
        assert playing_id() is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("forward", "back"), [("right", "left"), ("l", "h")])
async def test_playlist_tracks_are_reachable_with_keyboard(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
    *,
    forward: str,
    back: str,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlist = playlists.create_playlist_from_songs(
        user["id"], "Study", [SONG_A, SONG_B]
    )
    play = mocker.patch.object(app, "load_playlist_into_queue")

    async with app.run_test() as pilot:
        app.query_one(AppShell).switch_mode("playlists")
        await app.workers.wait_for_complete()
        await pilot.pause()

        await pilot.press(forward)

        tracks = app.query_one("#playlist_tracks", SongTable)
        assert tracks.query_one(VimListView).has_focus
        await pilot.press("j", "enter")
        play.assert_called_once_with(playlist["id"], play=True, start_index=1)

        await pilot.press(back)
        assert app.query_one("#playlist_list", SelectList).has_focus


@pytest.mark.asyncio
async def test_playlist_delete_confirms_original_selection(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist(user["id"], "First")
    second = playlists.create_playlist(user["id"], "Second")

    async with app.run_test() as pilot:
        app.query_one(AppShell).switch_mode("playlists")
        await app.workers.wait_for_complete()
        await pilot.pause()
        mode = app.query_one(PlaylistsMode)
        mode.action_delete_focused()
        await pilot.pause()
        mode.query_one("#playlist_list", SelectList).highlighted = 1
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        app.screen.action_accept()
        await pilot.pause()
        await app.workers.wait_for_complete()

        assert playlists.list_playlists(user["id"]) == [second]


@pytest.mark.asyncio
async def test_playlist_reload_failure_notifies_without_crashing(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, _state, _user = _app_with_playlists(mock_youtube, mock_player)
    mocker.patch.object(
        playlists,
        "list_playlists",
        side_effect=DatabaseError("Cannot load playlists"),
    )

    async with app.run_test() as pilot:
        mode = app.query_one(PlaylistsMode)
        notify = mocker.patch.object(mode, "notify")
        app.query_one(AppShell).switch_mode("playlists")
        await app.workers.wait_for_complete()
        await pilot.pause()

        notify.assert_called_once_with("Cannot load playlists", severity="error")


@pytest.mark.asyncio
async def test_playlist_load_completion_preserves_new_profile(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    original = playlists.create_playlist_from_songs(user["id"], "Old", [SONG_A])
    second = app.account_service.create_user("second")
    current = playlists.create_playlist_from_songs(second["id"], "New", [SONG_B])
    app.playback_service.load_queue([SONG_C])
    started = asyncio.Event()
    release = threading.Event()
    get_playlist = playlists.get_playlist

    def delayed_load(playlist_id: int) -> Playlist:
        loaded = get_playlist(playlist_id)
        app.call_from_thread(started.set)
        assert release.wait(timeout=2)
        return loaded

    mocker.patch.object(playlists, "get_playlist", side_effect=delayed_load)

    async with app.run_test() as pilot:
        try:
            app.load_playlist_into_queue(original["id"], play=False)
            await asyncio.wait_for(started.wait(), timeout=2)
            app.account_service.select_user(second["id"])
            playlists.adopt_working_playlist(current)
        finally:
            release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert state.current_user.get() == second
        assert state.current_playlist.get() == current
        assert state.queue.get() == [SONG_C]


@pytest.mark.asyncio
async def test_playlist_save_completion_preserves_new_profile(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    second = app.account_service.create_user("second")
    current = playlists.create_playlist_from_songs(second["id"], "New", [SONG_B])
    app.playback_service.load_queue([SONG_A])
    started = asyncio.Event()
    release = threading.Event()
    create_playlist = playlists.create_playlist_from_songs

    def delayed_save(user_id: int, name: str, songs: list[Song]) -> Playlist:
        created = create_playlist(user_id, name, songs)
        app.call_from_thread(started.set)
        assert release.wait(timeout=2)
        return created

    mocker.patch.object(
        playlists, "create_playlist_from_songs", side_effect=delayed_save
    )

    async with app.run_test() as pilot:
        try:
            app.save_queue_as_playlist("Saved")
            await asyncio.wait_for(started.wait(), timeout=2)
            app.account_service.select_user(second["id"])
            playlists.adopt_working_playlist(current)
        finally:
            release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert state.current_user.get() == second
        assert state.current_playlist.get() == current
        saved = playlists.list_playlists(user["id"])
        assert len(saved) == 1
        assert saved[0]["name"] == "Saved"
        assert saved[0]["songs"] == [SONG_A]


@pytest.mark.asyncio
async def test_playlist_reload_ignores_stale_profile_results(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "Old", [SONG_A])
    second = app.account_service.create_user("second")
    playlists.create_playlist_from_songs(second["id"], "New", [SONG_B])
    started = asyncio.Event()
    release = threading.Event()
    list_playlists = playlists.list_playlists

    def delayed_list(user_id: int) -> list[Playlist]:
        loaded = list_playlists(user_id)
        app.call_from_thread(started.set)
        assert release.wait(timeout=2)
        return loaded

    mocker.patch.object(playlists, "list_playlists", side_effect=delayed_list)

    async with app.run_test() as pilot:
        mode = app.query_one(PlaylistsMode)
        try:
            app.query_one(AppShell).switch_mode("playlists")
            await asyncio.wait_for(started.wait(), timeout=2)
            app.account_service.select_user(second["id"])
        finally:
            release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert state.current_user.get() == second
        assert [playlist["name"] for playlist in mode._playlists] != ["Old"]


@pytest.mark.asyncio
async def test_adding_song_refreshes_visible_playlist_tracks(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlist = playlists.create_playlist_from_songs(user["id"], "Study", [SONG_A])

    async with app.run_test() as pilot:
        app.query_one(AppShell).switch_mode("playlists")
        await app.workers.wait_for_complete()
        await pilot.pause()
        app.add_song_to_playlist(SONG_B)
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, AddToPlaylistModal)

        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert playlists.get_playlist(playlist["id"])["songs"] == [SONG_A, SONG_B]
        tracks = app.query_one("#playlist_tracks", SongTable)
        assert [row.song for row in tracks.query(SongRow)] == [SONG_A, SONG_B]


@pytest.mark.asyncio
async def test_capital_a_on_search_result_opens_playlist_picker(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    mock_youtube.search.return_value = [SAMPLE_SONG]
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist(user["id"], "Favs")

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, AddToPlaylistModal)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        loaded = playlists.list_playlists(user["id"])[0]
        assert loaded["songs"][0]["video_id"] == "vid1"


@pytest.mark.asyncio
async def test_capital_a_without_list_adds_current_song(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist(user["id"], "Favs")
    state.current_song.set(SAMPLE_SONG)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, AddToPlaylistModal)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        loaded = playlists.list_playlists(user["id"])[0]
        assert loaded["songs"][0]["video_id"] == "vid1"


@pytest.mark.asyncio
async def test_capital_a_in_search_input_does_not_open_picker(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist(user["id"], "Favs")

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()

        assert not isinstance(app.screen, AddToPlaylistModal)
        assert "A" in app.query_one("#search_input", Input).value


@pytest.mark.asyncio
async def test_playlists_n_creates_and_d_deletes(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#prompt_input", Input).value = "Fresh"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        listed = playlists.list_playlists(user["id"])
        assert any(item["name"] == "Fresh" for item in listed)
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert playlists.list_playlists(user["id"]) == []


@pytest.mark.asyncio
async def test_playlist_create_and_delete_run_off_ui_thread(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, _state, _user = _app_with_playlists(mock_youtube, mock_player)
    ui_thread = threading.get_ident()
    create_ids: list[int] = []
    delete_ids: list[int] = []
    original_create = playlists.create_playlist
    original_delete = playlists.delete_playlist

    def _create(user_id: int, name: str) -> Playlist:
        create_ids.append(threading.get_ident())
        return original_create(user_id, name)

    def _delete(playlist_id: int) -> None:
        delete_ids.append(threading.get_ident())
        original_delete(playlist_id)

    mocker.patch.object(playlists, "create_playlist", side_effect=_create)
    mocker.patch.object(playlists, "delete_playlist", side_effect=_delete)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#prompt_input", Input).value = "Fresh"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert create_ids
        assert create_ids[0] != ui_thread
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert delete_ids
        assert delete_ids[0] != ui_thread


@pytest.mark.asyncio
async def test_playlist_remove_song_runs_off_ui_thread(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist_from_songs(user["id"], "Study", [SONG_A, SONG_B])
    ui_thread = threading.get_ident()
    remove_ids: list[int] = []
    original_remove = playlists.remove_song

    def _remove(playlist_id: int, video_id: str) -> None:
        remove_ids.append(threading.get_ident())
        original_remove(playlist_id, video_id)

    mocker.patch.object(playlists, "remove_song", side_effect=_remove)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        await pilot.pause()
        app.query_one("#playlist_tracks", SongTable).focus_list()
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert remove_ids
        assert remove_ids[0] != ui_thread


@pytest.mark.asyncio
async def test_add_song_to_playlist_lists_and_adds_off_ui_thread(
    test_db: SqliteDatabase,
    mock_youtube: MagicMock,
    mock_player: MagicMock,
    mocker: MockerFixture,
) -> None:
    mock_youtube.search.return_value = [SAMPLE_SONG]
    app, playlists, _state, user = _app_with_playlists(mock_youtube, mock_player)
    playlists.create_playlist(user["id"], "Favs")
    ui_thread = threading.get_ident()
    list_ids: list[int] = []
    add_ids: list[int] = []
    original_list = playlists.list_playlists
    original_add = playlists.add_song

    def _list(user_id: int) -> list[Playlist]:
        list_ids.append(threading.get_ident())
        return original_list(user_id)

    def _add(playlist_id: int, song: Song) -> None:
        add_ids.append(threading.get_ident())
        original_add(playlist_id, song)

    mocker.patch.object(playlists, "list_playlists", side_effect=_list)
    mocker.patch.object(playlists, "add_song", side_effect=_add)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#search_input", Input).value = "ambient"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("A")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, AddToPlaylistModal)
        assert list_ids
        assert list_ids[0] != ui_thread
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert add_ids
        assert add_ids[0] != ui_thread
