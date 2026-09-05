"""Playlist persistence and PlaylistService tests."""

from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from textual.widgets import Input

from ytmusic_cli.db.repositories import PlaylistRepository, UserRepository
from ytmusic_cli.exceptions import DatabaseError, ValidationError
from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
)
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Song, User
from ytmusic_cli.tui.modals.add_to_playlist import AddToPlaylistModal
from ytmusic_cli.tui.shell import AppShell

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
    accounts = AccountService(UserRepository(), AppState())
    playlists = PlaylistService(PlaylistRepository())
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
    repo = PlaylistRepository()
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
    repo = PlaylistRepository()
    playlist = repo.create(user["id"], "Favs")

    replaced = repo.replace_songs(playlist["id"], [SONG_A, SONG_B, SONG_A])

    assert [song["video_id"] for song in replaced["songs"]] == ["a", "b"]


def test_replace_songs_missing_playlist_raises(
    test_db: SqliteDatabase,
) -> None:
    repo = PlaylistRepository()
    with pytest.raises(DatabaseError, match="not found"):
        repo.replace_songs(999, [SONG_A])


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
    accounts = AccountService(UserRepository(), state)
    user = accounts.ensure_default_user()
    accounts.select_user(user["id"])
    playlists = PlaylistService(PlaylistRepository())
    playlists.create_playlist(user["id"], "Study")

    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = YTMusicApp(
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


def _app_with_playlists(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> tuple[YTMusicApp, PlaylistService, AppState, User]:
    state = AppState()
    accounts = AccountService(UserRepository(), state)
    user = accounts.ensure_default_user()
    accounts.select_user(user["id"])
    playlists = PlaylistService(PlaylistRepository())
    app = YTMusicApp(
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

        assert isinstance(app.screen, AddToPlaylistModal)
        await pilot.press("enter")
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

        assert isinstance(app.screen, AddToPlaylistModal)
        await pilot.press("enter")
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
