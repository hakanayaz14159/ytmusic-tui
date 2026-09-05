"""Initial verification and TDD baseline tests."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from peewee import SqliteDatabase
from pytest_mock import MockerFixture

import ytmusic_cli.consts as consts_mod
from tests.conftest import make_test_app
from ytmusic_cli import __version__
from ytmusic_cli.consts import DEFAULT_USERNAME
from ytmusic_cli.db.bootstrap import bootstrap
from ytmusic_cli.db.playlist import Playlist
from ytmusic_cli.db.song import Song
from ytmusic_cli.db.user import User
from ytmusic_cli.main import build_production_app, main
from ytmusic_cli.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
    SettingsService,
)
from ytmusic_cli.music.state import AppState


def test_consts_import_does_not_create_app_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = tmp_path / "appdata"
    monkeypatch.setattr(
        "platformdirs.user_data_dir",
        lambda *_args, **_kwargs: str(fake),
    )
    try:
        reloaded = importlib.reload(consts_mod)
        assert not fake.exists()
        assert fake == reloaded.APP_DIR
    finally:
        monkeypatch.undo()
        importlib.reload(consts_mod)


def test_cli_version() -> None:
    """Verify CLI --version outputs the correct version."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help() -> None:
    """Verify CLI --help displays usage information."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "YTMusic CLI" in result.output


@pytest.mark.asyncio
async def test_tui_app_lifecycle() -> None:
    """Verify the Textual app mounts correctly and responds to quit binding."""
    search = MagicMock()
    search.suggest = MagicMock(return_value=[])
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = make_test_app(
        search_service=search,
        playback_service=playback,
        account_service=MagicMock(),
        playlist_service=MagicMock(),
        settings_service=MagicMock(),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.is_running
        await pilot.press("ctrl+q")
    assert not app.is_running


def test_database_in_memory_isolation(test_db: SqliteDatabase) -> None:
    """Verify models can be created and queried in the in-memory test database."""
    user = User.create(username="audiophile")
    song = Song.create(
        video_id="sample1",
        title="Lofi Beat 1",
        artist="Chill Producer",
        album="Beats",
        duration=180,
    )
    playlist = Playlist.create(name="Study Vibes", user=user)
    playlist.songs.add(song)

    assert user.playlists.count() == 1
    assert playlist.songs.count() == 1
    retrieved_user = User.get(User.username == "audiophile")
    assert retrieved_user.username == "audiophile"


def test_mock_youtube_and_player_fixtures(
    mock_youtube: MagicMock,
    mock_player: MagicMock,
) -> None:
    results = mock_youtube.search("lofi", max_results=2)
    assert len(results) == 2
    assert mock_youtube.get_stream("sample1")["url"].startswith("https://")
    assert mock_youtube.suggest("lo") == ["lofi hip hop", "lofi girl"]

    assert mock_player.is_playing() is False
    mock_player.play("https://stream.example.com/audio.m4a")
    assert mock_player.is_playing() is True
    mock_player.pause()
    assert mock_player.is_playing() is False
    mock_player.set_volume(50)
    assert mock_player.get_volume() == 50


def test_bootstrap_creates_default_user(
    test_db: SqliteDatabase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("ytmusic_cli.db.bootstrap.db", test_db)
    monkeypatch.setattr("ytmusic_cli.db.bootstrap.APP_DIR", tmp_path)
    monkeypatch.setattr("ytmusic_cli.db.bootstrap.DB_PATH", tmp_path / "ytmusic.db")
    bootstrap()
    user = AppState().current_user.get()
    assert user is not None
    assert user["username"] == DEFAULT_USERNAME
    assert User.select().count() >= 1


def test_build_production_app_wires_services(mocker: MockerFixture) -> None:
    mocker.patch("ytmusic_cli.main.Youtube")
    mocker.patch("ytmusic_cli.main.VLCPlayer")
    mocker.patch("ytmusic_cli.main.UserRepository")
    mocker.patch("ytmusic_cli.main.SongRepository")
    mocker.patch("ytmusic_cli.main.PlaylistRepository")
    app = build_production_app()
    assert isinstance(app.search_service, SearchService)
    assert isinstance(app.playback_service, PlaybackService)
    assert isinstance(app.account_service, AccountService)
    assert isinstance(app.playlist_service, PlaylistService)
    assert isinstance(app.settings_service, SettingsService)


def test_main_fatal_path_exits_one(mocker: MockerFixture) -> None:
    mocker.patch("ytmusic_cli.main.configure_logging", side_effect=RuntimeError("boom"))
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 1
    assert "boom" in result.output
