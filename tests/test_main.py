"""Tests for the CLI entry point, bootstrap, and production service wiring."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from peewee import SqliteDatabase
from pytest_mock import MockerFixture

import ytmusic_tui.consts as consts_mod
from tests.conftest import make_test_app
from ytmusic_tui import __version__
from ytmusic_tui.consts import DEFAULT_USERNAME
from ytmusic_tui.db.bootstrap import bootstrap
from ytmusic_tui.db.user import User
from ytmusic_tui.main import build_production_app, main
from ytmusic_tui.music.services import (
    AccountService,
    PlaybackService,
    PlaylistService,
    SearchService,
    SettingsService,
)
from ytmusic_tui.music.state import AppState


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
    assert "YTMusic TUI" in result.output


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


def test_bootstrap_creates_tables_without_users(
    test_db: SqliteDatabase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("ytmusic_tui.db.bootstrap.db", test_db)
    monkeypatch.setattr("ytmusic_tui.db.bootstrap.APP_DIR", tmp_path)
    monkeypatch.setattr("ytmusic_tui.db.bootstrap.DB_PATH", tmp_path / "ytmusic.db")
    bootstrap()
    assert AppState().current_user.get() is None
    assert User.select().count() == 0


def test_build_production_app_ensures_default_user(
    test_db: SqliteDatabase,
    mocker: MockerFixture,
) -> None:
    mocker.patch("ytmusic_tui.main.Youtube")
    mocker.patch("ytmusic_tui.main.VLCPlayer")
    build_production_app()
    assert User.select().count() == 1
    assert User.get().username == DEFAULT_USERNAME
    assert AppState().current_user.get() is None


def test_build_production_app_wires_services(mocker: MockerFixture) -> None:
    mocker.patch("ytmusic_tui.main.Youtube")
    mocker.patch("ytmusic_tui.main.VLCPlayer")
    mocker.patch("ytmusic_tui.main.UserRepository")
    mocker.patch("ytmusic_tui.main.SongRepository")
    mocker.patch("ytmusic_tui.main.PlaylistRepository")
    app = build_production_app()
    assert isinstance(app.search_service, SearchService)
    assert isinstance(app.playback_service, PlaybackService)
    assert isinstance(app.account_service, AccountService)
    assert isinstance(app.playlist_service, PlaylistService)
    assert isinstance(app.settings_service, SettingsService)


def test_main_fatal_path_exits_one(mocker: MockerFixture) -> None:
    mocker.patch("ytmusic_tui.main.configure_logging", side_effect=RuntimeError("boom"))
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 1
    assert "boom" in result.output
