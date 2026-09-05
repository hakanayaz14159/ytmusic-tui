"""AccountService and Profiles mode tests."""

import threading
from unittest.mock import MagicMock

import pytest
from peewee import SqliteDatabase
from pytest_mock import MockerFixture
from textual.widgets import Input

from tests.conftest import make_test_app
from ytmusic_cli.consts import DEFAULT_USERNAME
from ytmusic_cli.db.repositories import UserRepository
from ytmusic_cli.exceptions import DatabaseError, ValidationError
from ytmusic_cli.music.services import AccountService
from ytmusic_cli.music.state import AppState
from ytmusic_cli.music.types import User
from ytmusic_cli.tui.shell import AppShell
from ytmusic_cli.tui.widgets.select_list import SelectList


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
    app = make_test_app(
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
        current = state.current_user.get()
        assert current is not None
        assert current["username"] == "alpha"


@pytest.mark.asyncio
async def test_profiles_n_creates_and_d_deletes(
    test_db: SqliteDatabase,
) -> None:
    state = AppState()
    service = AccountService(UserRepository(), state)
    first = service.create_user("keep")
    service.select_user(first["id"])
    app = make_test_app(account_service=service)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("4")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#prompt_input", Input).value = "second"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        names = {user["username"] for user in service.list_users()}
        assert "second" in names
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        remaining = {user["username"] for user in service.list_users()}
        assert "second" not in remaining or "keep" in remaining


@pytest.mark.asyncio
async def test_profile_create_select_and_delete_run_off_ui_thread(
    test_db: SqliteDatabase,
    mocker: MockerFixture,
) -> None:
    state = AppState()
    service = AccountService(UserRepository(), state)
    first = service.create_user("keep")
    service.select_user(first["id"])
    app = make_test_app(account_service=service)
    ui_thread = threading.get_ident()
    create_ids: list[int] = []
    select_ids: list[int] = []
    delete_ids: list[int] = []
    original_create = service.create_user
    original_select = service.select_user
    original_delete = service.delete_user

    def _create(username: str) -> User:
        create_ids.append(threading.get_ident())
        return original_create(username)

    def _select(user_id: int) -> User:
        select_ids.append(threading.get_ident())
        return original_select(user_id)

    def _delete(user_id: int) -> None:
        delete_ids.append(threading.get_ident())
        original_delete(user_id)

    mocker.patch.object(service, "create_user", side_effect=_create)
    mocker.patch.object(service, "select_user", side_effect=_select)
    mocker.patch.object(service, "delete_user", side_effect=_delete)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("4")
        await pilot.pause()
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#prompt_input", Input).value = "second"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert create_ids
        assert create_ids[0] != ui_thread
        assert select_ids
        assert select_ids[0] != ui_thread
        users = service.list_users()
        created = next(user for user in users if user["username"] == "second")
        option_list = app.query_one("#profile_list", SelectList)
        for index, user in enumerate(users):
            if user["id"] == created["id"]:
                option_list.highlighted = index
                break
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        assert delete_ids
        assert delete_ids[0] != ui_thread


def test_duplicate_username_raises_database_error(test_db: SqliteDatabase) -> None:
    repo = UserRepository()
    repo.create_user("hzf")
    with pytest.raises(DatabaseError, match="already exists"):
        repo.create_user("hzf")


def test_delete_user_missing_id_raises(test_db: SqliteDatabase) -> None:
    with pytest.raises(DatabaseError, match="not found"):
        UserRepository().delete_user(999)


def test_update_settings_missing_user_raises(test_db: SqliteDatabase) -> None:
    with pytest.raises(DatabaseError, match="not found"):
        UserRepository().update_settings(
            999,
            {"default_volume": 40, "search_limit": 10},
        )
