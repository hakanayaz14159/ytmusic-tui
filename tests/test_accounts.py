"""AccountService and Profiles mode tests."""

from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase

from ytmusic_cli.consts import DEFAULT_USERNAME
from ytmusic_cli.db.repositories import UserRepository
from ytmusic_cli.exceptions import ValidationError
from ytmusic_cli.main import YTMusicApp
from ytmusic_cli.music.services import AccountService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.tui.shell import AppShell


@pytest.fixture
def account_service(test_db: SqliteDatabase) -> AccountService:
    return AccountService(UserRepository(), AppState())


def test_ensure_default_user_creates_local(
    account_service: AccountService,
) -> None:
    user = account_service.ensure_default_user()
    assert user["username"] == DEFAULT_USERNAME
    again = account_service.ensure_default_user()
    assert again["id"] == user["id"]


def test_ensure_default_user_reuses_sole_existing_profile(
    account_service: AccountService,
) -> None:
    created = account_service.create_user("solo")
    user = account_service.ensure_default_user()
    assert user["id"] == created["id"]


def test_select_user_sets_app_state(account_service: AccountService) -> None:
    user = account_service.create_user("hzf")
    selected = account_service.select_user(user["id"])
    assert AppState().current_user.get() == selected
    assert selected["username"] == "hzf"


def test_delete_last_profile_raises(account_service: AccountService) -> None:
    user = account_service.ensure_default_user()
    with pytest.raises(ValidationError, match="last profile"):
        account_service.delete_user(user["id"])


def test_delete_profile_selects_remaining(
    account_service: AccountService,
) -> None:
    first = account_service.create_user("one")
    second = account_service.create_user("two")
    account_service.select_user(first["id"])
    account_service.delete_user(first["id"])
    current = AppState().current_user.get()
    assert current is not None
    assert current["id"] == second["id"]


def test_empty_username_rejected(account_service: AccountService) -> None:
    with pytest.raises(ValidationError, match="empty"):
        account_service.create_user("   ")


@pytest.mark.asyncio
async def test_profiles_mode_lists_users_and_selects(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    service = AccountService(UserRepository(), state)
    first = service.create_user("alpha")
    service.create_user("beta")
    service.select_user(first["id"])

    playback = MagicMock()
    playback.sync_playback = MagicMock()
    app = YTMusicApp(
        search_service=MagicMock(),
        playback_service=playback,
        account_service=service,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("4")
        await pilot.pause()
        assert app.query_one(AppShell).current_mode == "profiles"
        assert state.current_user.get() is not None
        assert state.current_user.get()["username"] == "alpha"  # type: ignore[index]
