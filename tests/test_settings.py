"""SettingsService and wide-layout tests."""

from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase

from tests.conftest import make_test_app
from ytmusic_cli.consts import WIDE_LAYOUT_COLUMNS
from ytmusic_cli.db.repositories import UserRepository
from ytmusic_cli.exceptions import ValidationError
from ytmusic_cli.music.services import AccountService, SettingsService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.tui.modes.settings import SettingsMode
from ytmusic_cli.tui.shell import AppShell


def test_settings_save_round_trip(test_db: SqliteDatabase) -> None:
    state = AppState()
    users = UserRepository()
    accounts = AccountService(users, state)
    settings = SettingsService(users, state)
    user = accounts.create_user("hzf")
    accounts.select_user(user["id"])
    saved = settings.save({"default_volume": 40, "search_limit": 15})
    assert saved["default_volume"] == 40
    assert saved["search_limit"] == 15
    assert settings.get() == saved


def test_settings_reject_out_of_range(test_db: SqliteDatabase) -> None:
    state = AppState()
    users = UserRepository()
    accounts = AccountService(users, state)
    settings = SettingsService(users, state)
    user = accounts.create_user("hzf")
    accounts.select_user(user["id"])
    with pytest.raises(ValidationError, match="Volume"):
        settings.save({"default_volume": 200, "search_limit": 10})
    with pytest.raises(ValidationError, match="Search limit"):
        settings.save({"default_volume": 50, "search_limit": 1})


@pytest.mark.asyncio
async def test_settings_mode_opens() -> None:
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = make_test_app(
        search_service=MagicMock(),
        playback_service=playback,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("5")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "settings"


@pytest.mark.asyncio
async def test_settings_adjust_and_save(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    users = UserRepository()
    accounts = AccountService(users, state)
    user = accounts.create_user("hzf")
    accounts.select_user(user["id"])
    settings = SettingsService(users, state)
    app = make_test_app(account_service=accounts, settings_service=settings)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("5")
        await pilot.pause()
        await pilot.pause()
        app.query_one(SettingsMode).action_adjust_up()
        await pilot.pause()
        app.query_one(SettingsMode).action_save()
        await pilot.pause()
        await pilot.pause()
        saved = settings.get()
        assert saved["default_volume"] == 85


@pytest.mark.asyncio
async def test_wide_layout_shows_queue_pane() -> None:
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = make_test_app(
        search_service=MagicMock(),
        playback_service=playback,
    )
    async with app.run_test(size=(WIDE_LAYOUT_COLUMNS, 24)) as pilot:
        await pilot.pause()
        pane = app.query_one("#queue_pane")
        assert pane.display is True


@pytest.mark.asyncio
async def test_narrow_layout_hides_queue_pane() -> None:
    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = make_test_app(
        search_service=MagicMock(),
        playback_service=playback,
    )
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        pane = app.query_one("#queue_pane")
        assert pane.display is False
