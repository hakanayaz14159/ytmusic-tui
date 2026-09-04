"""Playlist persistence and PlaylistService tests."""

from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase

from ytmusic_cli.db.repositories import PlaylistRepository, UserRepository
from ytmusic_cli.exceptions import ValidationError
from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.services import AccountService, PlaylistService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import Song
from ytmusic_cli.tui.shell import AppShell

SAMPLE_SONG: Song = {
    "video_id": "vid1",
    "title": "Track",
    "artist": "Artist",
    "album": "Album",
    "duration": 120,
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
